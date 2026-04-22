from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

from macrobania.agent.verifier import Verifier
from macrobania.capture.backend import FrameData
from macrobania.inputio import DryRunInjector, FailSafe
from macrobania.models import (
    Action,
    ActionType,
    EventKind,
    PixelBBox,
    Platform,
    RawEvent,
    VerifierResult,
)
from macrobania.player import FaithfulPlayer, PlaySession
from macrobania.recording.builder import semanticize
from macrobania.recording.writer import RecordingWriter
from macrobania.storage import open_db


@dataclass
class FakeCapture:
    """실제 화면 안 건드리는 테스트용 캡처."""

    image: Image.Image = field(default_factory=lambda: Image.new("RGB", (100, 100), (0, 0, 0)))
    name: str = "fake"

    def grab(self, monitor: int = 0) -> FrameData:
        return FrameData(image=self.image, ts_ns=0, monitor=monitor, resolution=self.image.size)

    def close(self) -> None:
        pass


@dataclass
class FakeVerifier(Verifier):
    always: str = "yes"

    def __post_init__(self) -> None:
        pass  # skip client creation

    def yesno(self, screenshot, question: str) -> VerifierResult:  # type: ignore[override]
        return VerifierResult(answer=self.always, reason="fake")


def _prep(tmp_path: Path):
    db = open_db(tmp_path / "db.sqlite")
    db.connect()
    rec_id = "rec_mode_a"
    rec_dir = tmp_path / rec_id
    writer = RecordingWriter(
        db=db,
        rec_dir=rec_dir,
        rec_id=rec_id,
        task_name="t",
        platform=Platform(os="Windows", resolution=(800, 600)),
    )
    writer.create()
    writer.write_frame(
        FrameData(image=Image.new("RGB", (100, 100), (0, 0, 0)), ts_ns=0, monitor=0, resolution=(100, 100)),
        is_keyframe=True,
    )
    writer.write_events(
        [
            RawEvent(ts_ns=100_000_000, kind=EventKind.MOUSE_DOWN, x=30, y=30, button="left"),
            RawEvent(ts_ns=200_000_000, kind=EventKind.MOUSE_UP, x=30, y=30, button="left"),
            RawEvent(ts_ns=2_000_000_000, kind=EventKind.MOUSE_DOWN, x=60, y=60, button="left"),
            RawEvent(ts_ns=2_050_000_000, kind=EventKind.MOUSE_UP, x=60, y=60, button="left"),
        ]
    )
    writer.finalize()
    semanticize(db=db, rec_id=rec_id, rec_dir=rec_dir, use_vlm=False)

    # hint_bbox 수동 주입 — rule-based는 target_bbox_hint 비워둠
    with db.transaction() as conn:
        bbox_json = Action(
            type=ActionType.CLICK,
            target_bbox_hint=PixelBBox(x1=25, y1=25, x2=35, y2=35),
        ).model_dump_json()
        conn.execute(
            "UPDATE steps SET action_json = ? WHERE recording_id = ? AND step_index = 0",
            (bbox_json, rec_id),
        )
        bbox_json2 = Action(
            type=ActionType.CLICK,
            target_bbox_hint=PixelBBox(x1=55, y1=55, x2=65, y2=65),
        ).model_dump_json()
        conn.execute(
            "UPDATE steps SET action_json = ? WHERE recording_id = ? AND step_index = 1",
            (bbox_json2, rec_id),
        )

    return db, rec_id, rec_dir


def test_mode_a_plays_dry_run(tmp_path: Path) -> None:
    db, rec_id, rec_dir = _prep(tmp_path)
    injector = DryRunInjector()
    failsafe = FailSafe(enabled=False)
    session = PlaySession(
        db=db, recording_id=rec_id, mode="a", injector=injector, failsafe=failsafe
    )
    player = FaithfulPlayer(
        session=session, rec_dir=rec_dir, verifier=None, speed=100.0, capture=FakeCapture()
    )
    result = player.play()
    assert not result.failed
    assert len(result.outcomes) == 2
    assert all(o.status == "success" for o in result.outcomes)
    # 두 번의 click 주입
    click_calls = [c for c in injector.calls if c[0] == "click"]
    assert len(click_calls) == 2
    assert click_calls[0][1] == (30, 30)
    assert click_calls[1][1] == (60, 60)


def test_mode_a_session_persisted(tmp_path: Path) -> None:
    db, rec_id, rec_dir = _prep(tmp_path)
    injector = DryRunInjector()
    session = PlaySession(
        db=db, recording_id=rec_id, mode="a", injector=injector, failsafe=FailSafe(enabled=False)
    )
    FaithfulPlayer(session=session, rec_dir=rec_dir, speed=100.0, capture=FakeCapture()).play()
    conn = db.connect()
    row = conn.execute(
        "SELECT mode, dry_run, outcome FROM sessions WHERE id = ?",
        (session.session_id,),
    ).fetchone()
    assert row["mode"] == "a"
    assert row["dry_run"] == 1
    assert row["outcome"] == "success"


def test_mode_a_precondition_fails(tmp_path: Path) -> None:
    db, rec_id, rec_dir = _prep(tmp_path)
    # precondition을 'no'로 검증
    with db.transaction() as conn:
        conn.execute(
            "UPDATE steps SET precondition = 'is the moon full?' "
            "WHERE recording_id = ? AND step_index = 0",
            (rec_id,),
        )
    injector = DryRunInjector()
    session = PlaySession(
        db=db, recording_id=rec_id, mode="a", injector=injector,
        failsafe=FailSafe(enabled=False)
    )
    player = FaithfulPlayer(
        session=session,
        rec_dir=rec_dir,
        verifier=FakeVerifier(always="no"),
        speed=100.0,
        max_retries=1,
        retry_wait_ms=1,
        capture=FakeCapture(),
    )
    result = player.play()
    assert result.failed
    assert "precondition" in result.failure_reason


def test_audit_log_written(tmp_path: Path) -> None:
    db, rec_id, rec_dir = _prep(tmp_path)
    session = PlaySession(
        db=db, recording_id=rec_id, mode="a", injector=DryRunInjector(),
        failsafe=FailSafe(enabled=False)
    )
    FaithfulPlayer(session=session, rec_dir=rec_dir, speed=100.0, capture=FakeCapture()).play()
    conn = db.connect()
    kinds = [
        row["event_kind"]
        for row in conn.execute(
            "SELECT event_kind FROM audit_log WHERE recording_id = ? ORDER BY id",
            (rec_id,),
        )
    ]
    assert "play_start" in kinds
    assert "step_start" in kinds
    assert "step_end" in kinds
    assert "play_end" in kinds
