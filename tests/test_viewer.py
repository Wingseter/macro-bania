from __future__ import annotations

from pathlib import Path

from PIL import Image

from macrobania.capture.backend import FrameData
from macrobania.models import EventKind, Platform, RawEvent
from macrobania.recording import export_html, semanticize
from macrobania.recording.writer import RecordingWriter
from macrobania.storage import open_db


def test_export_html_writes_file(tmp_path: Path) -> None:
    db = open_db(tmp_path / "db.sqlite")
    db.connect()
    rec_id = "rec_viewer"
    rec_dir = tmp_path / rec_id
    writer = RecordingWriter(
        db=db,
        rec_dir=rec_dir,
        rec_id=rec_id,
        task_name="viewer test",
        description="a desc",
        platform=Platform(os="Windows", resolution=(100, 100)),
    )
    writer.create()
    writer.write_frame(
        FrameData(
            image=Image.new("RGB", (40, 40), (255, 0, 0)),
            ts_ns=100,
            monitor=0,
            resolution=(40, 40),
        ),
        is_keyframe=True,
    )
    writer.write_events(
        [
            RawEvent(ts_ns=500, kind=EventKind.MOUSE_DOWN, x=1, y=1, button="left"),
            RawEvent(ts_ns=600, kind=EventKind.MOUSE_UP, x=1, y=1, button="left"),
        ]
    )
    writer.finalize()

    semanticize(db=db, rec_id=rec_id, rec_dir=rec_dir, use_vlm=False)

    out = tmp_path / "out.html"
    export_html(db=db, rec_id=rec_id, rec_dir=rec_dir, out_path=out)
    assert out.exists()
    html = out.read_text(encoding="utf-8")
    assert "viewer test" in html
    assert "f00000.webp" in html
    assert "click" in html
