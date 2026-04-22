from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

from macrobania.agent.grounder import Grounder
from macrobania.agent.planner import Planner, PlannerDecision
from macrobania.capture.backend import FrameData
from macrobania.inputio import DryRunInjector, FailSafe
from macrobania.models import GrounderResult, NormBBox, Platform
from macrobania.perception.uia import UIAControl, UIASnapshot, UIASnapshotter
from macrobania.player import AutonomousPlayer, PlaySession
from macrobania.recording.writer import RecordingWriter
from macrobania.storage import open_db


@dataclass
class FakeCapture:
    image: Image.Image = field(
        default_factory=lambda: Image.new("RGB", (1000, 1000), (0, 0, 0))
    )
    name: str = "fake"

    def grab(self, monitor: int = 0) -> FrameData:
        return FrameData(image=self.image, ts_ns=0, monitor=monitor, resolution=self.image.size)

    def close(self) -> None:
        pass


class ScriptedPlanner(Planner):
    """미리 정해진 decisions를 순서대로 리턴."""

    def __init__(self, script: list[PlannerDecision]) -> None:
        self.script = list(script)
        self.calls = 0

    def plan(self, **kw) -> PlannerDecision:  # type: ignore[override]
        _ = kw
        if self.calls >= len(self.script):
            return PlannerDecision(type="done", rationale="script ended")
        d = self.script[self.calls]
        self.calls += 1
        return d


class StubGrounder(Grounder):
    def __init__(self, bbox: NormBBox) -> None:
        self._bbox = bbox
        self.calls = 0

    def locate(self, screenshot, **kw) -> GrounderResult:  # type: ignore[override]
        self.calls += 1
        return GrounderResult(bbox=self._bbox, confidence=0.9, reason="stub")


class FakeUIA(UIASnapshotter):
    def __init__(self, snap: UIASnapshot | None) -> None:
        self._snap = snap

    def available(self) -> bool:  # type: ignore[override]
        return True

    def snapshot_foreground(self) -> UIASnapshot:  # type: ignore[override]
        assert self._snap is not None
        return self._snap


def _prep(tmp_path: Path):
    db = open_db(tmp_path / "db.sqlite")
    db.connect()
    rec_id = "rec_c"
    rec_dir = tmp_path / rec_id
    RecordingWriter(
        db=db, rec_dir=rec_dir, rec_id=rec_id,
        task_name="goal",
        platform=Platform(os="Windows", resolution=(1000, 1000)),
    ).create()
    return db, rec_id, rec_dir


def test_mode_c_terminates_on_done(tmp_path: Path) -> None:
    db, rec_id, _ = _prep(tmp_path)
    planner = ScriptedPlanner([PlannerDecision(type="done", rationale="trivially done")])
    grounder = StubGrounder(bbox=NormBBox(x1=0, y1=0, x2=10, y2=10))
    injector = DryRunInjector()
    session = PlaySession(
        db=db, recording_id=rec_id, mode="c",
        injector=injector, failsafe=FailSafe(enabled=False),
    )
    player = AutonomousPlayer(
        session=session, planner=planner, grounder=grounder,
        goal="do nothing", capture=FakeCapture(),
    )
    result = player.play()
    assert not result.failed
    assert len(result.outcomes) == 1
    assert result.outcomes[0].status == "success"


def test_mode_c_click_then_done(tmp_path: Path) -> None:
    db, rec_id, _ = _prep(tmp_path)
    uia = UIASnapshot(
        hwnd=1, window_title="w",
        root=UIAControl(
            role="Window", name="root", bbox=(0, 0, 1000, 1000),
            children=[
                UIAControl(role="Button", name="OK", bbox=(100, 100, 200, 140)),
            ],
        ),
    )
    planner = ScriptedPlanner([
        PlannerDecision(type="click", target_description="OK", rationale="confirm"),
        PlannerDecision(type="done", rationale="confirmed"),
    ])
    grounder = StubGrounder(bbox=NormBBox(x1=0, y1=0, x2=10, y2=10))
    injector = DryRunInjector()
    session = PlaySession(
        db=db, recording_id=rec_id, mode="c",
        injector=injector, failsafe=FailSafe(enabled=False),
    )
    player = AutonomousPlayer(
        session=session, planner=planner, grounder=grounder,
        goal="click OK", capture=FakeCapture(), uia=FakeUIA(uia),
    )
    result = player.play()
    assert not result.failed
    assert len(result.outcomes) == 2
    # UIA가 해결했으므로 grounder는 호출되지 않음
    assert grounder.calls == 0
    click = next(c for c in injector.calls if c[0] == "click")
    # (100+200)/2 = 150, (100+140)/2 = 120
    assert click[1] == (150, 120)


def test_mode_c_max_steps_reached(tmp_path: Path) -> None:
    db, rec_id, _ = _prep(tmp_path)
    # planner가 done을 리턴하지 않음 → wait 반복 → max_steps hit
    planner = ScriptedPlanner([PlannerDecision(type="wait", rationale="loading")] * 30)
    grounder = StubGrounder(bbox=NormBBox(x1=0, y1=0, x2=10, y2=10))
    session = PlaySession(
        db=db, recording_id=rec_id, mode="c",
        injector=DryRunInjector(), failsafe=FailSafe(enabled=False),
    )
    player = AutonomousPlayer(
        session=session, planner=planner, grounder=grounder,
        goal="noop loop", capture=FakeCapture(),
        max_steps=3, inter_step_ms=1,
    )
    result = player.play()
    assert result.failed
    assert "max_steps" in result.failure_reason


def test_mode_c_falls_to_grounder_when_uia_misses(tmp_path: Path) -> None:
    db, rec_id, _ = _prep(tmp_path)
    planner = ScriptedPlanner([
        PlannerDecision(type="click", target_description="elusive target", rationale="try"),
        PlannerDecision(type="done", rationale="ok"),
    ])
    grounder = StubGrounder(bbox=NormBBox(x1=200, y1=200, x2=300, y2=300))
    injector = DryRunInjector()
    session = PlaySession(
        db=db, recording_id=rec_id, mode="c",
        injector=injector, failsafe=FailSafe(enabled=False),
    )
    player = AutonomousPlayer(
        session=session, planner=planner, grounder=grounder,
        goal="g", capture=FakeCapture(), uia=None, ocr=None,
    )
    result = player.play()
    assert not result.failed
    assert grounder.calls == 1  # UIA/OCR 없음 → Grounder 호출
