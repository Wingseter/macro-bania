from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from PIL import Image

from macrobania.capture.backend import FrameData
from macrobania.models import EventKind, Platform, RawEvent
from macrobania.recording.repo import RecordingRepo
from macrobania.recording.writer import RecordingWriter
from macrobania.storage import open_db


def _make_writer(tmp_path: Path) -> tuple[RecordingWriter, Path]:
    db_path = tmp_path / "db.sqlite"
    rec_dir = tmp_path / "rec_1"
    db = open_db(db_path)
    db.connect()
    writer = RecordingWriter(
        db=db,
        rec_dir=rec_dir,
        rec_id="rec_test_2026-04-22",
        task_name="demo",
        description="desc",
        platform=Platform(os="Windows", resolution=(800, 600)),
        target_process="notepad.exe",
    )
    return writer, rec_dir


def test_writer_frames_and_events(tmp_path: Path) -> None:
    writer, rec_dir = _make_writer(tmp_path)
    writer.create()

    events = [
        RawEvent(ts_ns=1_000, kind=EventKind.MOUSE_MOVE, x=10, y=20),
        RawEvent(ts_ns=2_000, kind=EventKind.MOUSE_DOWN, x=10, y=20, button="left"),
        RawEvent(ts_ns=2_100, kind=EventKind.MOUSE_UP, x=10, y=20, button="left"),
    ]
    writer.write_events(events)

    img = Image.new("RGB", (800, 600), (5, 5, 5))
    f = FrameData(image=img, ts_ns=3_000, monitor=0, resolution=(800, 600))
    rel = writer.write_frame(f, is_keyframe=True)
    assert (rec_dir / rel).exists()

    rec = writer.finalize()
    assert rec.frame_count == 1
    assert rec.event_count == 3
    assert rec.duration_ms == (3_000 - 1_000) // 1_000_000  # 0
    # ts_ns 범위가 너무 작아 ms 단위론 0


def test_writer_scrubs_pii_in_text(tmp_path: Path) -> None:
    writer, _ = _make_writer(tmp_path)
    writer.create()
    evts = [
        RawEvent(
            ts_ns=100,
            kind=EventKind.TEXT_INPUT,
            text="my email is user@example.com",
        )
    ]
    writer.write_events(evts)
    conn = writer.db.connect()
    row = conn.execute(
        "SELECT text FROM raw_events WHERE recording_id = ?",
        (writer.rec_id,),
    ).fetchone()
    assert row[0] == "my email is <EMAIL>"


def test_repo_list_and_iter(tmp_path: Path) -> None:
    writer, _ = _make_writer(tmp_path)
    writer.create()
    writer.write_events(
        [
            RawEvent(ts_ns=10, kind=EventKind.KEY_DOWN, vk=65),
            RawEvent(ts_ns=20, kind=EventKind.KEY_UP, vk=65),
        ]
    )
    img = Image.new("RGB", (100, 100), (1, 2, 3))
    writer.write_frame(
        FrameData(image=img, ts_ns=30, monitor=0, resolution=(100, 100)),
        is_keyframe=True,
    )
    writer.finalize()

    repo = RecordingRepo(db=writer.db)
    rows = repo.list()
    assert len(rows) == 1
    assert rows[0].id == writer.rec_id
    assert rows[0].event_count == 2
    assert rows[0].frame_count == 1

    got = repo.get(writer.rec_id)
    assert got is not None
    events = list(repo.iter_events(writer.rec_id))
    assert len(events) == 2
    frames = list(repo.iter_frames(writer.rec_id))
    assert len(frames) == 1
    assert str(frames[0]["path"]).endswith(".webp")


def test_repo_delete(tmp_path: Path) -> None:
    writer, _ = _make_writer(tmp_path)
    writer.create()
    writer.finalize()
    repo = RecordingRepo(db=writer.db)
    assert repo.get(writer.rec_id) is not None
    assert repo.delete(writer.rec_id) is True
    assert repo.get(writer.rec_id) is None


def _touch_time() -> datetime:
    return datetime(2026, 1, 1, tzinfo=UTC)
