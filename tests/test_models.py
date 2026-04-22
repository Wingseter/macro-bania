from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from macrobania.models import (
    Action,
    ActionType,
    NormBBox,
    PixelBBox,
    Platform,
    Recording,
    Step,
)


def test_pixel_bbox_geometry() -> None:
    bb = PixelBBox(x1=10, y1=20, x2=110, y2=220)
    assert bb.width == 100
    assert bb.height == 200
    assert bb.center == (60, 120)


def test_norm_bbox_range() -> None:
    with pytest.raises(ValidationError):
        NormBBox(x1=-1, y1=0, x2=10, y2=10)
    with pytest.raises(ValidationError):
        NormBBox(x1=0, y1=0, x2=1001, y2=10)


def test_pixel_from_norm() -> None:
    nb = NormBBox(x1=0, y1=0, x2=500, y2=1000)
    pb = PixelBBox.from_norm(nb, width=1920, height=1080)
    assert pb.x1 == 0 and pb.y1 == 0
    assert pb.x2 == 960  # 500/1000 * 1920
    assert pb.y2 == 1080


def test_recording_minimal() -> None:
    r = Recording(
        id="rec_2026-04-22_14-33-01",
        task_name="demo",
        created_at=datetime(2026, 4, 22, 14, 33, 1, tzinfo=UTC),
        platform=Platform(os="Windows 11", resolution=(1920, 1080)),
    )
    assert r.frame_count == 0
    assert r.task_name == "demo"


def test_recording_id_pattern() -> None:
    with pytest.raises(ValidationError):
        Recording(
            id="notarec",
            task_name="x",
            created_at=datetime.now(tz=UTC),
            platform=Platform(os="x", resolution=(10, 10)),
        )


def test_step_json_roundtrip() -> None:
    step = Step(
        index=0,
        ts_start_ns=1_000,
        ts_end_ns=2_000,
        action=Action(type=ActionType.CLICK, target_description="Login"),
        caption="로그인 클릭",
        confidence=0.9,
    )
    dumped = step.model_dump_json()
    loaded = Step.model_validate_json(dumped)
    assert loaded == step
    assert loaded.action.type == ActionType.CLICK


def test_action_type_values() -> None:
    assert ActionType("click") is ActionType.CLICK
    assert ActionType("type") is ActionType.TYPE
