"""재생 세션 공통 기반.

session row 생성/마감, audit logging, failsafe 연결.
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from macrobania.inputio.failsafe import FailSafe
from macrobania.inputio.injector import Injector
from macrobania.logging import get_audit_logger, get_logger
from macrobania.models import Step
from macrobania.storage import Database

log = get_logger(__name__)


@dataclass(frozen=True)
class StepOutcome:
    step_index: int
    status: Literal["success", "failed", "skipped"]
    reason: str = ""


@dataclass
class PlayResult:
    session_id: str
    recording_id: str
    mode: Literal["a", "b", "c"]
    dry_run: bool
    outcomes: list[StepOutcome] = field(default_factory=list)
    failed: bool = False
    failure_reason: str = ""


@dataclass
class PlaySession:
    """실행 1회(1 recording 재생).

    - audit_log 테이블과 audit.log 파일에 이중 기록
    - FailSafe로 kill-switch 연결
    """

    db: Database
    recording_id: str
    mode: Literal["a", "b", "c"]
    injector: Injector
    failsafe: FailSafe
    session_id: str = field(default_factory=lambda: f"ses_{uuid.uuid4().hex[:12]}")
    _started_at: float = field(default_factory=time.time, init=False, repr=False)
    _file_logger: object | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self._file_logger = get_audit_logger()

    # --- lifecycle ---

    def open(self) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO sessions (id, recording_id, started_at, mode, dry_run)
                VALUES (?,?,?,?,?)
                """,
                (
                    self.session_id,
                    self.recording_id,
                    datetime.now().astimezone().isoformat(),
                    self.mode,
                    1 if self.injector.dry_run else 0,
                ),
            )
        self._audit(
            "play_start",
            dry_run=self.injector.dry_run,
            failsafe_enabled=self.failsafe.enabled,
        )

    def close(self, *, outcome: Literal["success", "failed", "aborted"], reason: str = "") -> None:
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE sessions SET ended_at = ?, outcome = ?, failure_reason = ? "
                "WHERE id = ?",
                (datetime.now().astimezone().isoformat(), outcome, reason, self.session_id),
            )
        self._audit("play_end", outcome=outcome, reason=reason)

    # --- audit ---

    def _audit(self, kind: str, *, step_index: int | None = None, **details: object) -> None:
        ts_ns = time.monotonic_ns()
        payload_json = json.dumps(details, default=str, ensure_ascii=False)
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO audit_log
                    (ts_ns, event_kind, recording_id, step_index, details_json)
                VALUES (?,?,?,?,?)
                """,
                (ts_ns, kind, self.recording_id, step_index, payload_json),
            )
        assert self._file_logger is not None
        self._file_logger.info(
            json.dumps(
                {
                    "ts_ns": ts_ns,
                    "session": self.session_id,
                    "rec": self.recording_id,
                    "kind": kind,
                    "step": step_index,
                    **details,
                },
                default=str,
                ensure_ascii=False,
            )
        )

    # --- step hooks (subclass가 사용) ---

    def audit_step_start(self, step: Step) -> None:
        self._audit("step_start", step_index=step.index, action=step.action.type.value)

    def audit_step_end(self, outcome: StepOutcome) -> None:
        self._audit(
            "step_end",
            step_index=outcome.step_index,
            status=outcome.status,
            reason=outcome.reason,
        )

    def audit_kill_switch(self, reason: str) -> None:
        self._audit("kill_switch", reason=reason)
