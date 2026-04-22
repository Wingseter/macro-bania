"""Mode B — Grounded Replay (★ V1 핵심).

각 Step 실행 전:
  1. 현재 화면 캡처 + UIA + OCR 스냅샷
  2. Hybrid matcher로 후보 감축
  3. 유일 후보 → 그대로 사용 / 다중 → Grounder VLM로 disambiguation
  4. 주입
  5. postcondition 검증
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

from macrobania.agent.grounder import Grounder
from macrobania.agent.verifier import Verifier
from macrobania.capture import CaptureBackend, open_backend
from macrobania.inputio.failsafe import FailSafeTripped
from macrobania.inputio.injector import execute_action
from macrobania.logging import get_logger
from macrobania.models import ActionType, NormBBox, PixelBBox, Step
from macrobania.perception import (
    MatcherConfig,
    UIASnapshotter,
    UIAUnavailableError,
    find_candidates,
)
from macrobania.perception.ocr import OCREngine, OCRUnavailableError
from macrobania.player.base import PlayResult, PlaySession, StepOutcome
from macrobania.player.frame_cache import GroundingCache
from macrobania.recording.builder import load_steps

log = get_logger(__name__)


@dataclass
class PerceptionSources:
    """현재 시점의 hybrid perception 스냅샷."""

    screenshot: Image.Image
    uia_snapshot: object | None = None  # UIASnapshot | None
    ocr_blocks: list[object] = field(default_factory=list)


@dataclass
class GroundedPlayer:
    session: PlaySession
    rec_dir: Path
    grounder: Grounder
    verifier: Verifier | None = None
    uia: UIASnapshotter | None = None
    ocr: OCREngine | None = None
    capture: CaptureBackend | None = None
    cache: GroundingCache = field(default_factory=GroundingCache)
    matcher_cfg: MatcherConfig = field(default_factory=MatcherConfig)
    inter_step_ms: int = 200
    max_retries: int = 2
    retry_wait_ms: int = 600

    def play(self) -> PlayResult:
        session = self.session
        session.open()
        steps = load_steps(session.db, session.recording_id)
        log.info("mode_b.start", rec=session.recording_id, steps=len(steps))

        result = PlayResult(
            session_id=session.session_id,
            recording_id=session.recording_id,
            mode="b",
            dry_run=session.injector.dry_run,
        )

        try:
            for step in steps:
                outcome = self._play_step(step)
                result.outcomes.append(outcome)
                session.audit_step_end(outcome)
                if outcome.status == "failed":
                    result.failed = True
                    result.failure_reason = outcome.reason
                    break
                self._sleep(self.inter_step_ms / 1000.0)
        except FailSafeTripped as e:
            session.audit_kill_switch(str(e))
            result.failed = True
            result.failure_reason = f"failsafe: {e}"

        status = "success" if not result.failed else "failed"
        session.close(outcome=status, reason=result.failure_reason)
        log.info("mode_b.end", outcomes=len(result.outcomes), failed=result.failed)
        return result

    # --- per-step ---

    def _play_step(self, step: Step) -> StepOutcome:
        self.session.audit_step_start(step)

        try:
            self.session.check_allowlist()
        except Exception as e:  # ProcessNotAllowedError
            return StepOutcome(
                step_index=step.index,
                status="failed",
                reason=f"allowlist: {e}",
            )

        # precondition 확인
        if (
            step.precondition
            and self.verifier is not None
            and not self._check_condition(step.precondition)
        ):
            for _ in range(self.max_retries):
                self._sleep(self.retry_wait_ms / 1000.0)
                if self._check_condition(step.precondition):
                    break
            else:
                return StepOutcome(
                    step_index=step.index,
                    status="failed",
                    reason=f"precondition unmet: {step.precondition}",
                )

        # Grounding은 좌표 필요 액션만
        try:
            center = self._resolve_center(step)
        except _GroundingFailed as e:
            return StepOutcome(
                step_index=step.index, status="failed", reason=f"grounding: {e}"
            )

        # 주입
        try:
            to_center = step.action.to_bbox.center if step.action.to_bbox else None
            execute_action(
                self.session.injector,
                action_type=step.action.type,
                center=center,
                to_center=to_center,
                value=step.action.value,
                modifiers=step.action.modifiers,
                wait_ms=step.action.wait_ms,
            )
        except FailSafeTripped:
            raise
        except Exception as e:
            return StepOutcome(
                step_index=step.index, status="failed", reason=f"inject error: {e}"
            )

        # postcondition
        if (
            step.postcondition
            and self.verifier is not None
            and not self._check_condition(step.postcondition)
        ):
            return StepOutcome(
                step_index=step.index,
                status="failed",
                reason=f"postcondition unmet: {step.postcondition}",
            )

        return StepOutcome(step_index=step.index, status="success")

    # --- grounding 결정 ---

    def _resolve_center(self, step: Step) -> tuple[int, int] | None:
        needs_coord = step.action.type in (
            ActionType.CLICK,
            ActionType.DOUBLE_CLICK,
            ActionType.DRAG,
            ActionType.SCROLL,
        )
        if not needs_coord:
            return None

        target = step.action.target_description
        if not target:
            # 타깃 서술이 없으면 hint 좌표를 그대로 사용 (rule-based Step)
            if step.action.target_bbox_hint is None:
                raise _GroundingFailed("no target description and no hint bbox")
            return step.action.target_bbox_hint.center

        sources = self._perceive()

        # 1) 캐시 조회
        cached = self.cache.lookup(target, sources.screenshot)
        if cached is not None:
            px = PixelBBox.from_norm(cached, *sources.screenshot.size)
            return px.center

        # 2) Hybrid matcher
        match = find_candidates(
            target,
            uia=sources.uia_snapshot,  # type: ignore[arg-type]
            ocr=sources.ocr_blocks or None,  # type: ignore[arg-type]
            hint_bbox_pixel=_px(step.action.target_bbox_hint),
            cfg=self.matcher_cfg,
        )
        unambiguous = match.unambiguous(self.matcher_cfg)
        if unambiguous is not None:
            log.info(
                "mode_b.matcher_hit",
                source=unambiguous.candidate.source,
                reason=unambiguous.match_reason,
                score=unambiguous.score,
            )
            bbox = unambiguous.candidate.bbox_pixel
            center = ((bbox[0] + bbox[2]) // 2, (bbox[1] + bbox[3]) // 2)
            # 캐시 저장 (norm 좌표)
            w, h = sources.screenshot.size
            self.cache.insert(
                target,
                sources.screenshot,
                NormBBox(
                    x1=max(0, min(1000, int(bbox[0] * 1000 / w))),
                    y1=max(0, min(1000, int(bbox[1] * 1000 / h))),
                    x2=max(0, min(1000, int(bbox[2] * 1000 / w))),
                    y2=max(0, min(1000, int(bbox[3] * 1000 / h))),
                ),
            )
            return center

        # 3) Grounder VLM
        log.info(
            "mode_b.grounder_call",
            candidates=len(match.candidates),
            target=target[:60],
        )
        result = self.grounder.locate(
            screenshot=sources.screenshot,
            target_description=target,
            hint_bbox_pixel=_px(step.action.target_bbox_hint),
            hint_resolution=_hint_resolution_from_hint(step.action.target_bbox_hint),
            candidates=match.candidates or None,
        )
        self.cache.insert(target, sources.screenshot, result.bbox)
        px = PixelBBox.from_norm(result.bbox, *sources.screenshot.size)
        return px.center

    # --- perception / verify ---

    def _perceive(self) -> PerceptionSources:
        if self.capture is None:
            self.capture = open_backend()
        shot = self.capture.grab().image

        uia_snap = None
        if self.uia is not None and self.uia.available():
            try:
                uia_snap = self.uia.snapshot_foreground()
            except UIAUnavailableError:
                uia_snap = None

        ocr_blocks: list[object] = []
        if self.ocr is not None and self.ocr.available():
            try:
                ocr_blocks = list(self.ocr.read(shot))
            except OCRUnavailableError:
                ocr_blocks = []
            except Exception as e:
                log.warning("mode_b.ocr_failed", error=str(e))

        return PerceptionSources(
            screenshot=shot, uia_snapshot=uia_snap, ocr_blocks=ocr_blocks
        )

    def _check_condition(self, question: str) -> bool:
        assert self.verifier is not None
        shot = self._perceive().screenshot
        return self.verifier.yesno(shot, question).answer == "yes"

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


class _GroundingFailed(Exception):
    pass


def _px(bbox: PixelBBox | None) -> tuple[int, int, int, int] | None:
    if bbox is None:
        return None
    return (bbox.x1, bbox.y1, bbox.x2, bbox.y2)


def _hint_resolution_from_hint(
    bbox: PixelBBox | None,
) -> tuple[int, int] | None:
    # hint 해상도는 모르므로 None. 추후 Recording.platform.resolution 참조로 개선
    _ = bbox
    return None
