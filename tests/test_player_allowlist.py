from __future__ import annotations

from pathlib import Path

from PIL import Image

from macrobania.capture.backend import FrameData
from macrobania.inputio import DryRunInjector, FailSafe
from macrobania.models import (
    Action,
    ActionType,
    EventKind,
    PixelBBox,
    Platform,
    RawEvent,
)
from macrobania.player import FaithfulPlayer, PlaySession
from macrobania.recording.builder import semanticize
from macrobania.recording.writer import RecordingWriter
from macrobania.safety import ProcessAllowlist
from macrobania.storage import open_db


class _FakeCapture:
    name = "fake"

    def grab(self, monitor: int = 0) -> FrameData:
        img = Image.new("RGB", (100, 100), (0, 0, 0))
        return FrameData(image=img, ts_ns=0, monitor=monitor, resolution=(100, 100))

    def close(self) -> None:
        pass


def _prep(tmp_path: Path):
    db = open_db(tmp_path / "db.sqlite")
    db.connect()
    rec_id = "rec_allow"
    rec_dir = tmp_path / rec_id
    w = RecordingWriter(
        db=db, rec_dir=rec_dir, rec_id=rec_id,
        task_name="t", platform=Platform(os="Windows", resolution=(100, 100)),
    )
    w.create()
    w.write_events(
        [
            RawEvent(ts_ns=100, kind=EventKind.MOUSE_DOWN, x=10, y=10, button="left"),
            RawEvent(ts_ns=200, kind=EventKind.MOUSE_UP, x=10, y=10, button="left"),
        ]
    )
    w.finalize()
    semanticize(db=db, rec_id=rec_id, rec_dir=rec_dir, use_vlm=False)
    # hint_bbox 주입
    conn = db.connect()
    conn.execute(
        "UPDATE steps SET action_json = ? WHERE recording_id = ? AND step_index = 0",
        (
            Action(
                type=ActionType.CLICK,
                target_bbox_hint=PixelBBox(x1=5, y1=5, x2=15, y2=15),
            ).model_dump_json(),
            rec_id,
        ),
    )
    return db, rec_id, rec_dir


def test_allowlist_blocks_step(tmp_path: Path, monkeypatch) -> None:
    db, rec_id, rec_dir = _prep(tmp_path)

    # active_window_process를 불일치 프로세스로 stub
    monkeypatch.setattr(
        "macrobania.player.base.active_window_process", lambda: "evil.exe"
    )

    session = PlaySession(
        db=db,
        recording_id=rec_id,
        mode="a",
        injector=DryRunInjector(),
        failsafe=FailSafe(enabled=False),
        allowlist=ProcessAllowlist(names=["chrome.exe"]),
    )
    player = FaithfulPlayer(
        session=session, rec_dir=rec_dir, speed=100.0, capture=_FakeCapture()
    )
    result = player.play()
    assert result.failed
    assert "allowlist" in result.failure_reason


def test_allowlist_allows_matching_process(tmp_path: Path, monkeypatch) -> None:
    db, rec_id, rec_dir = _prep(tmp_path)
    monkeypatch.setattr(
        "macrobania.player.base.active_window_process", lambda: "chrome.exe"
    )
    session = PlaySession(
        db=db,
        recording_id=rec_id,
        mode="a",
        injector=DryRunInjector(),
        failsafe=FailSafe(enabled=False),
        allowlist=ProcessAllowlist(names=["chrome.exe"]),
    )
    result = FaithfulPlayer(
        session=session, rec_dir=rec_dir, speed=100.0, capture=_FakeCapture()
    ).play()
    assert not result.failed


def test_allowlist_undetected_process_passes(tmp_path: Path, monkeypatch) -> None:
    # active_window_process가 빈 문자열 리턴하면 통과
    db, rec_id, rec_dir = _prep(tmp_path)
    monkeypatch.setattr("macrobania.player.base.active_window_process", lambda: "")
    session = PlaySession(
        db=db,
        recording_id=rec_id,
        mode="a",
        injector=DryRunInjector(),
        failsafe=FailSafe(enabled=False),
        allowlist=ProcessAllowlist(names=["whatever"]),
    )
    result = FaithfulPlayer(
        session=session, rec_dir=rec_dir, speed=100.0, capture=_FakeCapture()
    ).play()
    assert not result.failed
