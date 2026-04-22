"""Mode C — Autonomous Goal Mode (P6 기초).

녹화 없이 자연어 goal만으로 ReAct 루프:
    observe → plan → (ground) → inject → observe → …

V1 스코프:
- 최대 ``max_steps`` 안에 planner 가 ``done`` 을 리턴하면 성공
- 각 step 실패 시 retry N회, 이후 중단
- 녹화 데이터는 RAG로 주입 가능하지만 기본은 없음

Phase 7+에서 state graph / 광범위 RAG / 병행 도구 추가.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

from macrobania.agent.grounder import Grounder
from macrobania.agent.planner import Planner, PlannerDecision
from macrobania.agent.verifier import Verifier
from macrobania.capture import CaptureBackend, open_backend
from macrobania.inputio.failsafe import FailSafeTripped
from macrobania.inputio.injector import execute_action
from macrobania.logging import get_logger
from macrobania.models import ActionType, NormBBox, PixelBBox
from macrobania.perception import (
    MatcherConfig,
    UIASnapshotter,
    find_candidates,
)
from macrobania.perception.ocr import OCREngine
from macrobania.player.base import PlayResult, PlaySession, StepOutcome
from macrobania.player.frame_cache import GroundingCache

log = get_logger(__name__)


@dataclass
class AutonomousPlayer:
    session: PlaySession
    planner: Planner
    grounder: Grounder
    goal: str
    verifier: Verifier | None = None
    uia: UIASnapshotter | None = None
    ocr: OCREngine | None = None
    capture: CaptureBackend | None = None
    cache: GroundingCache = field(default_factory=GroundingCache)
    matcher_cfg: MatcherConfig = field(default_factory=MatcherConfig)
    max_steps: int = 20
    inter_step_ms: int = 300
    max_consecutive_fails: int = 3
    rec_dir: Path | None = None  # 미사용이지만 인터페이스 통일
    history: list[str] = field(default_factory=list)
    few_shot_steps: list[str] = field(default_factory=list)

    def play(self) -> PlayResult:
        self.session.open()
        log.info("mode_c.start", goal=self.goal[:80], max_steps=self.max_steps)

        result = PlayResult(
            session_id=self.session.session_id,
            recording_id=self.session.recording_id,
            mode="c",
            dry_run=self.session.injector.dry_run,
        )

        consecutive_fail = 0
        try:
            for step_idx in range(self.max_steps):
                self.session.check_allowlist()

                shot = self._grab()
                decision = self.planner.plan(
                    goal=self.goal,
                    screenshot=shot,
                    history=self.history,
                    few_shot_steps=self.few_shot_steps,
                )
                log.info(
                    "mode_c.decision",
                    step=step_idx,
                    type=decision.type,
                    target=(decision.target_description or "")[:60],
                )
                self.session._audit(  # type: ignore[attr-defined]
                    "planner_decision",
                    step_index=step_idx,
                    decision_type=decision.type,
                    target=decision.target_description,
                    rationale=decision.rationale,
                )

                if decision.is_terminal:
                    result.outcomes.append(
                        StepOutcome(step_index=step_idx, status="success", reason="done")
                    )
                    break

                try:
                    self._execute(decision, shot)
                    outcome = StepOutcome(step_index=step_idx, status="success")
                    consecutive_fail = 0
                except FailSafeTripped:
                    raise
                except Exception as e:
                    outcome = StepOutcome(
                        step_index=step_idx, status="failed", reason=f"exec: {e}"
                    )
                    consecutive_fail += 1

                result.outcomes.append(outcome)
                self.session.audit_step_end(outcome)
                self.history.append(
                    f"step {step_idx}: {decision.type} → {outcome.status}"
                )

                if consecutive_fail >= self.max_consecutive_fails:
                    result.failed = True
                    result.failure_reason = (
                        f"aborted: {consecutive_fail} consecutive failures"
                    )
                    break

                self._sleep(self.inter_step_ms / 1000.0)
            else:
                result.failed = True
                result.failure_reason = f"max_steps reached: {self.max_steps}"
        except FailSafeTripped as e:
            self.session.audit_kill_switch(str(e))
            result.failed = True
            result.failure_reason = f"failsafe: {e}"

        status = "success" if not result.failed else "failed"
        self.session.close(outcome=status, reason=result.failure_reason)
        log.info("mode_c.end", outcomes=len(result.outcomes), failed=result.failed)
        return result

    # --- internals ---

    def _execute(self, decision: PlannerDecision, screenshot: Image.Image) -> None:
        action_type = decision.to_action_type()
        center: tuple[int, int] | None = None

        if action_type in (
            ActionType.CLICK,
            ActionType.DOUBLE_CLICK,
            ActionType.DRAG,
            ActionType.SCROLL,
        ):
            if not decision.target_description:
                raise RuntimeError("target_description required for coord action")
            center = self._resolve_target(decision.target_description, screenshot)

        execute_action(
            self.session.injector,
            action_type=action_type,
            center=center,
            value=decision.value,
            wait_ms=1000 if action_type is ActionType.WAIT else None,
        )

    def _resolve_target(self, target: str, screenshot: Image.Image) -> tuple[int, int]:
        # 캐시
        cached = self.cache.lookup(target, screenshot)
        if cached is not None:
            px = PixelBBox.from_norm(cached, *screenshot.size)
            return px.center

        uia_snap = None
        ocr_blocks: list[object] = []
        if self.uia is not None and self.uia.available():
            try:
                uia_snap = self.uia.snapshot_foreground()
            except Exception:
                uia_snap = None
        if self.ocr is not None and self.ocr.available():
            try:
                ocr_blocks = list(self.ocr.read(screenshot))
            except Exception:
                ocr_blocks = []

        match = find_candidates(
            target,
            uia=uia_snap,  # type: ignore[arg-type]
            ocr=ocr_blocks or None,  # type: ignore[arg-type]
            cfg=self.matcher_cfg,
        )
        unambiguous = match.unambiguous(self.matcher_cfg)
        if unambiguous is not None:
            bbox = unambiguous.candidate.bbox_pixel
            w, h = screenshot.size
            self.cache.insert(
                target,
                screenshot,
                NormBBox(
                    x1=max(0, min(1000, int(bbox[0] * 1000 / w))),
                    y1=max(0, min(1000, int(bbox[1] * 1000 / h))),
                    x2=max(0, min(1000, int(bbox[2] * 1000 / w))),
                    y2=max(0, min(1000, int(bbox[3] * 1000 / h))),
                ),
            )
            return ((bbox[0] + bbox[2]) // 2, (bbox[1] + bbox[3]) // 2)

        # Grounder
        gr = self.grounder.locate(
            screenshot=screenshot,
            target_description=target,
            candidates=match.candidates or None,
        )
        self.cache.insert(target, screenshot, gr.bbox)
        return PixelBBox.from_norm(gr.bbox, *screenshot.size).center

    def _grab(self) -> Image.Image:
        if self.capture is None:
            self.capture = open_backend()
        return self.capture.grab().image

    def _sleep(self, seconds: float) -> None:
        if seconds <= 0:
            return
        end = time.monotonic() + seconds
        while True:
            remaining = end - time.monotonic()
            if remaining <= 0:
                return
            if self.session.failsafe.tripped:
                raise FailSafeTripped("kill_switch")
            time.sleep(min(0.1, remaining))
