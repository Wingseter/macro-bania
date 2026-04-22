"""Mode A — Faithful Replay.

기록된 타임스탬프대로 재생. 각 Step 실행 전 precondition 확인(optional),
실행 후 postcondition 확인(optional). Verifier가 없으면 스킵.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from macrobania.agent.verifier import Verifier
from macrobania.capture import CaptureBackend, open_backend
from macrobania.inputio.failsafe import FailSafeTripped
from macrobania.inputio.injector import execute_action
from macrobania.logging import get_logger
from macrobania.models import Step
from macrobania.player.base import PlayResult, PlaySession, StepOutcome
from macrobania.recording.builder import load_steps

log = get_logger(__name__)


@dataclass
class FaithfulPlayer:
    """Mode A 재생기."""

    session: PlaySession
    rec_dir: Path
    verifier: Verifier | None = None
    speed: float = 1.0
    max_retries: int = 2
    retry_wait_ms: int = 500
    capture: CaptureBackend | None = None  # 제공 안 되면 Verifier 호출 시 열기

    def play(self) -> PlayResult:
        session = self.session
        session.open()
        steps = load_steps(session.db, session.recording_id)
        log.info("mode_a.start", rec=session.recording_id, steps=len(steps))

        result = PlayResult(
            session_id=session.session_id,
            recording_id=session.recording_id,
            mode="a",
            dry_run=session.injector.dry_run,
        )

        prev_end_ns: int | None = None
        try:
            for step in steps:
                # 타임스탬프 간격을 지킨다 (speed 배율)
                if prev_end_ns is not None:
                    gap_ms = (step.ts_start_ns - prev_end_ns) / 1_000_000
                    scaled = max(0.0, gap_ms / max(0.01, self.speed))
                    if scaled > 0:
                        self._sleep(scaled / 1000.0)
                prev_end_ns = step.ts_end_ns

                outcome = self._play_step(step)
                result.outcomes.append(outcome)
                session.audit_step_end(outcome)
                if outcome.status == "failed":
                    result.failed = True
                    result.failure_reason = outcome.reason
                    break
        except FailSafeTripped as e:
            session.audit_kill_switch(str(e))
            result.failed = True
            result.failure_reason = f"failsafe: {e}"

        status = "success" if not result.failed else "failed"
        session.close(outcome=status, reason=result.failure_reason)
        log.info("mode_a.end", outcomes=len(result.outcomes), failed=result.failed)
        return result

    # --- internals ---

    def _play_step(self, step: Step) -> StepOutcome:
        self.session.audit_step_start(step)

        # 프로세스 allowlist 체크
        try:
            self.session.check_allowlist()
        except Exception as e:  # ProcessNotAllowedError
            return StepOutcome(
                step_index=step.index,
                status="failed",
                reason=f"allowlist: {e}",
            )

        # precondition 확인
        if step.precondition and self.verifier is not None:
            ok = self._check_condition(step.precondition)
            if not ok:
                for _ in range(self.max_retries):
                    self._sleep(self.retry_wait_ms / 1000.0)
                    ok = self._check_condition(step.precondition)
                    if ok:
                        break
                if not ok:
                    return StepOutcome(
                        step_index=step.index,
                        status="failed",
                        reason=f"precondition unmet: {step.precondition}",
                    )

        # 실행
        try:
            self._execute(step)
        except FailSafeTripped:
            raise
        except Exception as e:
            return StepOutcome(
                step_index=step.index,
                status="failed",
                reason=f"inject error: {e}",
            )

        # postcondition 확인
        if step.postcondition and self.verifier is not None:
            ok = self._check_condition(step.postcondition)
            if not ok:
                return StepOutcome(
                    step_index=step.index,
                    status="failed",
                    reason=f"postcondition unmet: {step.postcondition}",
                )

        return StepOutcome(step_index=step.index, status="success")

    def _execute(self, step: Step) -> None:
        # Mode A는 기록 당시 hint_bbox 중심을 그대로 클릭
        center = None
        if step.action.target_bbox_hint is not None:
            center = step.action.target_bbox_hint.center
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

    def _check_condition(self, question: str) -> bool:
        assert self.verifier is not None
        shot = self._grab()
        result = self.verifier.yesno(shot, question)
        return result.answer == "yes"

    def _grab(self) -> Image.Image:
        if self.capture is None:
            self.capture = open_backend()
        return self.capture.grab().image

    def _sleep(self, seconds: float) -> None:
        if seconds <= 0:
            return
        # 틱 단위 failsafe 체크
        end = time.monotonic() + seconds
        while True:
            remaining = end - time.monotonic()
            if remaining <= 0:
                return
            if self.session.failsafe.tripped:
                raise FailSafeTripped("kill_switch")
            time.sleep(min(0.1, remaining))
