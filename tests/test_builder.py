from __future__ import annotations

from pathlib import Path

from PIL import Image

from macrobania.agent.captioner import (
    CandidateStep,
    classify_events,
    rule_based_step,
)
from macrobania.capture.backend import FrameData
from macrobania.models import ActionType, EventKind, Platform, RawEvent
from macrobania.recording.builder import (
    BuilderConfig,
    FramesIndex,
    cluster,
    load_events,
    load_frames_index,
    load_steps,
    semanticize,
)
from macrobania.recording.writer import RecordingWriter
from macrobania.storage import open_db

# ---------- classify_events ----------


def _e(kind: EventKind, ts: int = 0, **kw: object) -> RawEvent:
    return RawEvent(ts_ns=ts, kind=kind, **kw)  # type: ignore[arg-type]


def test_classify_click() -> None:
    events = [
        _e(EventKind.MOUSE_DOWN, 100, x=10, y=10, button="left"),
        _e(EventKind.MOUSE_UP, 200, x=10, y=10, button="left"),
    ]
    assert classify_events(events) is ActionType.CLICK


def test_classify_double_click() -> None:
    events = [
        _e(EventKind.MOUSE_DOWN, 100, x=10, y=10, button="left"),
        _e(EventKind.MOUSE_UP, 150, x=10, y=10, button="left"),
        _e(EventKind.MOUSE_DOWN, 200, x=10, y=10, button="left"),
        _e(EventKind.MOUSE_UP, 250, x=10, y=10, button="left"),
    ]
    assert classify_events(events) is ActionType.DOUBLE_CLICK


def test_classify_drag() -> None:
    events = [
        _e(EventKind.MOUSE_DOWN, 100, x=10, y=10, button="left"),
        _e(EventKind.MOUSE_MOVE, 150, x=100, y=100),
        _e(EventKind.MOUSE_UP, 200, x=200, y=200, button="left"),
    ]
    assert classify_events(events) is ActionType.DRAG


def test_classify_scroll() -> None:
    events = [_e(EventKind.SCROLL, 100, x=0, y=0, dx=0, dy=-1)]
    assert classify_events(events) is ActionType.SCROLL


def test_classify_type() -> None:
    events = [_e(EventKind.KEY_DOWN, i * 10, vk=ord("A") + i) for i in range(10)]
    assert classify_events(events) is ActionType.TYPE


def test_classify_hotkey() -> None:
    events = [
        _e(EventKind.KEY_DOWN, 100, vk=17),  # CTRL
        _e(EventKind.KEY_DOWN, 110, vk=83),  # S
        _e(EventKind.KEY_UP, 120, vk=83),
        _e(EventKind.KEY_UP, 130, vk=17),
    ]
    # KEY_DOWN count == 2, so HOTKEY
    assert classify_events(events) is ActionType.HOTKEY


def test_classify_empty() -> None:
    assert classify_events([]) is ActionType.WAIT


def test_rule_based_step_has_caption() -> None:
    cand = CandidateStep(
        ts_start_ns=100,
        ts_end_ns=200,
        events=[
            _e(EventKind.MOUSE_DOWN, 100, x=50, y=50, button="left"),
            _e(EventKind.MOUSE_UP, 200, x=50, y=50, button="left"),
        ],
        frame_before_path="frames/f0.webp",
        frame_after_path="frames/f1.webp",
        raw_event_ids=[1, 2],
    )
    step = rule_based_step(cand)
    assert step.action.type is ActionType.CLICK
    assert "클릭" in step.caption
    assert step.confidence < 0.5  # rule-based → low confidence


# ---------- cluster / frames index ----------


def test_frames_index_before_after() -> None:
    idx = FramesIndex(
        entries=[
            (100, "frames/f0.webp"),
            (200, "frames/f1.webp"),
            (300, "frames/f2.webp"),
        ]
    )
    assert idx.frame_before(250) == "frames/f1.webp"
    assert idx.frame_after(150) == "frames/f1.webp"
    assert idx.frame_before(50) is None
    assert idx.frame_after(500) == "frames/f2.webp"


def test_cluster_splits_by_time_window() -> None:
    # 1.5s 간격으로 두 클러스터
    events = [
        (1, _e(EventKind.MOUSE_DOWN, 1_000_000_000, x=0, y=0, button="left")),
        (2, _e(EventKind.MOUSE_UP, 1_100_000_000, x=0, y=0, button="left")),
        (3, _e(EventKind.MOUSE_DOWN, 5_000_000_000, x=1, y=1, button="left")),
        (4, _e(EventKind.MOUSE_UP, 5_100_000_000, x=1, y=1, button="left")),
    ]
    cands = cluster(events, cfg=BuilderConfig(cluster_window_ns=1_500_000_000))
    assert len(cands) == 2
    assert cands[0].raw_event_ids == [1, 2]
    assert cands[1].raw_event_ids == [3, 4]


def test_cluster_drops_mouse_move_only() -> None:
    events = [
        (1, _e(EventKind.MOUSE_MOVE, 100, x=1, y=1)),
        (2, _e(EventKind.MOUSE_MOVE, 200, x=2, y=2)),
    ]
    assert cluster(events) == []


# ---------- integration: semanticize + load_steps ----------


def _rec_id() -> str:
    return "rec_test_builder"


def _prep_recording(tmp_path: Path) -> tuple[Path, object]:
    db = open_db(tmp_path / "db.sqlite")
    db.connect()
    rec_dir = tmp_path / _rec_id()
    writer = RecordingWriter(
        db=db,
        rec_dir=rec_dir,
        rec_id=_rec_id(),
        task_name="t",
        platform=Platform(os="Windows", resolution=(800, 600)),
    )
    writer.create()

    img0 = Image.new("RGB", (100, 100), (0, 0, 0))
    img1 = Image.new("RGB", (100, 100), (255, 255, 255))
    writer.write_frame(
        FrameData(image=img0, ts_ns=1_000_000_000, monitor=0, resolution=(100, 100)),
        is_keyframe=True,
    )
    writer.write_frame(
        FrameData(image=img1, ts_ns=2_000_000_000, monitor=0, resolution=(100, 100)),
        is_keyframe=False,
    )
    writer.write_events(
        [
            RawEvent(ts_ns=1_500_000_000, kind=EventKind.MOUSE_DOWN, x=50, y=50, button="left"),
            RawEvent(ts_ns=1_550_000_000, kind=EventKind.MOUSE_UP, x=50, y=50, button="left"),
            # 2초 뒤 별도 클러스터
            RawEvent(ts_ns=3_600_000_000, kind=EventKind.KEY_DOWN, vk=65),
            RawEvent(ts_ns=3_700_000_000, kind=EventKind.KEY_UP, vk=65),
        ]
    )
    writer.finalize()
    return rec_dir, db


def test_semanticize_rule_based(tmp_path: Path) -> None:
    rec_dir, db = _prep_recording(tmp_path)
    result = semanticize(db=db, rec_id=_rec_id(), rec_dir=rec_dir, use_vlm=False)
    assert result.step_count == 2
    steps = load_steps(db, _rec_id())
    assert [s.action.type for s in steps] == [ActionType.CLICK, ActionType.HOTKEY]
    assert steps[0].confidence < 0.5


def test_load_events_roundtrip(tmp_path: Path) -> None:
    rec_dir, db = _prep_recording(tmp_path)
    _ = rec_dir
    events = load_events(db, _rec_id())
    assert len(events) == 4
    idx = load_frames_index(db, _rec_id())
    assert len(idx.entries) == 2
