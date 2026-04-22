from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

from macrobania.agent.grounder import Grounder
from macrobania.capture.backend import FrameData
from macrobania.inputio import DryRunInjector, FailSafe
from macrobania.models import (
    Action,
    ActionType,
    EventKind,
    GrounderResult,
    NormBBox,
    Platform,
    RawEvent,
)
from macrobania.perception.ocr import OCRBlock, OCREngine
from macrobania.perception.uia import UIAControl, UIASnapshot, UIASnapshotter
from macrobania.player import GroundedPlayer, PlaySession
from macrobania.recording.builder import semanticize
from macrobania.recording.writer import RecordingWriter
from macrobania.storage import open_db

# --- 테스트용 fakes ---


@dataclass
class FakeCapture:
    image: Image.Image = field(
        default_factory=lambda: Image.new("RGB", (1000, 1000), (0, 0, 0))
    )
    name: str = "fake"
    grabs: int = 0

    def grab(self, monitor: int = 0) -> FrameData:
        self.grabs += 1
        return FrameData(image=self.image, ts_ns=0, monitor=monitor, resolution=self.image.size)

    def close(self) -> None:
        pass


class FakeUIA(UIASnapshotter):
    def __init__(self, snapshot: UIASnapshot | None) -> None:
        self._snap = snapshot

    def available(self) -> bool:  # type: ignore[override]
        return True

    def snapshot_foreground(self) -> UIASnapshot:  # type: ignore[override]
        if self._snap is None:
            from macrobania.perception.uia import UIAUnavailableError

            raise UIAUnavailableError("no active window")
        return self._snap


class FakeOCR(OCREngine):
    def __init__(self, blocks: list[OCRBlock]) -> None:
        self._blocks = blocks

    def available(self) -> bool:  # type: ignore[override]
        return True

    def read(self, image) -> list[OCRBlock]:  # type: ignore[override]
        _ = image
        return list(self._blocks)


class RecordingGrounder(Grounder):
    """grounder.locate() 호출 시 고정 bbox 반환 + 호출 카운트 저장."""

    def __init__(self, bbox: NormBBox) -> None:
        self._bbox = bbox
        self.calls = 0

    def locate(self, screenshot, **kw) -> GrounderResult:  # type: ignore[override]
        self.calls += 1
        return GrounderResult(bbox=self._bbox, confidence=0.9, reason="stub")


# --- 녹화 fixture ---


def _prep(tmp_path: Path, *, target_desc: str | None = "Login 버튼") -> tuple[object, str, Path]:
    db = open_db(tmp_path / "db.sqlite")
    db.connect()
    rec_id = "rec_mode_b"
    rec_dir = tmp_path / rec_id
    writer = RecordingWriter(
        db=db,
        rec_dir=rec_dir,
        rec_id=rec_id,
        task_name="t",
        platform=Platform(os="Windows", resolution=(1000, 1000)),
    )
    writer.create()
    writer.write_frame(
        FrameData(
            image=Image.new("RGB", (100, 100), (0, 0, 0)),
            ts_ns=0,
            monitor=0,
            resolution=(100, 100),
        ),
        is_keyframe=True,
    )
    writer.write_events(
        [
            RawEvent(ts_ns=100, kind=EventKind.MOUSE_DOWN, x=50, y=50, button="left"),
            RawEvent(ts_ns=200, kind=EventKind.MOUSE_UP, x=50, y=50, button="left"),
        ]
    )
    writer.finalize()
    semanticize(db=db, rec_id=rec_id, rec_dir=rec_dir, use_vlm=False)

    # step 0에 target_description / hint_bbox 수동 주입
    if target_desc is not None:
        with db.transaction() as conn:
            action = Action(
                type=ActionType.CLICK,
                target_description=target_desc,
            )
            conn.execute(
                "UPDATE steps SET action_json = ? WHERE recording_id = ? AND step_index = 0",
                (action.model_dump_json(), rec_id),
            )
    return db, rec_id, rec_dir


# --- 테스트 ---


def test_mode_b_uia_match_skips_grounder(tmp_path: Path) -> None:
    db, rec_id, rec_dir = _prep(tmp_path)
    uia = UIASnapshot(
        hwnd=1,
        window_title="w",
        root=UIAControl(
            role="Window",
            name="root",
            bbox=(0, 0, 1000, 1000),
            children=[
                UIAControl(role="Button", name="Login 버튼", bbox=(400, 400, 500, 440)),
                UIAControl(role="Button", name="Cancel", bbox=(600, 400, 700, 440)),
            ],
        ),
    )
    grounder = RecordingGrounder(bbox=NormBBox(x1=0, y1=0, x2=10, y2=10))
    injector = DryRunInjector()
    session = PlaySession(
        db=db, recording_id=rec_id, mode="b", injector=injector,
        failsafe=FailSafe(enabled=False),
    )
    player = GroundedPlayer(
        session=session,
        rec_dir=rec_dir,
        grounder=grounder,
        capture=FakeCapture(),
        uia=FakeUIA(uia),
    )
    result = player.play()
    assert not result.failed
    assert grounder.calls == 0  # UIA가 해결 → VLM 호출 X
    click_calls = [c for c in injector.calls if c[0] == "click"]
    assert len(click_calls) == 1
    # bbox 중심 (450, 420)
    assert click_calls[0][1] == (450, 420)


def test_mode_b_falls_back_to_grounder(tmp_path: Path) -> None:
    db, rec_id, rec_dir = _prep(tmp_path)
    # UIA/OCR에 매치 없음 → Grounder VLM이 호출돼야 함
    grounder = RecordingGrounder(bbox=NormBBox(x1=500, y1=500, x2=600, y2=600))
    injector = DryRunInjector()
    session = PlaySession(
        db=db, recording_id=rec_id, mode="b", injector=injector,
        failsafe=FailSafe(enabled=False),
    )
    player = GroundedPlayer(
        session=session,
        rec_dir=rec_dir,
        grounder=grounder,
        capture=FakeCapture(Image.new("RGB", (1000, 1000), (0, 0, 0))),
        uia=None,
        ocr=None,
    )
    result = player.play()
    assert not result.failed
    assert grounder.calls == 1
    click = next(c for c in injector.calls if c[0] == "click")
    # norm 550,550 → pixel 550,550
    assert click[1] == (550, 550)


def test_mode_b_ocr_match(tmp_path: Path) -> None:
    db, rec_id, rec_dir = _prep(tmp_path, target_desc="로그인")
    ocr = FakeOCR([OCRBlock(text="로그인", bbox=(100, 100, 200, 140), confidence=0.9)])
    grounder = RecordingGrounder(bbox=NormBBox(x1=0, y1=0, x2=10, y2=10))
    injector = DryRunInjector()
    session = PlaySession(
        db=db, recording_id=rec_id, mode="b", injector=injector,
        failsafe=FailSafe(enabled=False),
    )
    player = GroundedPlayer(
        session=session,
        rec_dir=rec_dir,
        grounder=grounder,
        capture=FakeCapture(),
        uia=None,
        ocr=ocr,
    )
    result = player.play()
    assert not result.failed
    assert grounder.calls == 0
    # ocr bbox 중심 (150, 120)
    click = next(c for c in injector.calls if c[0] == "click")
    assert click[1] == (150, 120)


def test_mode_b_cache_reuses_on_stable_screen(tmp_path: Path) -> None:
    """같은 target을 두 번 찾을 때 캐시가 두 번째 호출에서 VLM 스킵."""
    db, rec_id, rec_dir = _prep(tmp_path)
    # 같은 target을 두 번 실행하도록 step 추가
    conn = db.connect()
    action = Action(type=ActionType.CLICK, target_description="Login 버튼")
    conn.execute(
        "INSERT INTO steps (recording_id, step_index, ts_start_ns, ts_end_ns, "
        "action_json, caption, confidence, raw_event_ids) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (rec_id, 1, 300, 400, action.model_dump_json(), "click 2", 0.5, "[]"),
    )

    grounder = RecordingGrounder(bbox=NormBBox(x1=100, y1=100, x2=200, y2=200))
    injector = DryRunInjector()
    session = PlaySession(
        db=db, recording_id=rec_id, mode="b", injector=injector,
        failsafe=FailSafe(enabled=False),
    )
    # UIA/OCR 없음 → 첫 호출 Grounder → 캐시 저장
    player = GroundedPlayer(
        session=session,
        rec_dir=rec_dir,
        grounder=grounder,
        capture=FakeCapture(),
        uia=None,
        ocr=None,
    )
    result = player.play()
    assert not result.failed
    assert grounder.calls == 1  # 두 번째는 캐시 히트
    click_calls = [c for c in injector.calls if c[0] == "click"]
    assert len(click_calls) == 2
