import pytest

from macrobania.inputio.failsafe import FailSafe, FailSafeTripped


def test_corner_trips() -> None:
    fs = FailSafe(corner_radius=10)
    with pytest.raises(FailSafeTripped):
        fs.check(0, 0)
    assert fs.tripped


def test_far_from_corner_ok() -> None:
    fs = FailSafe(corner_radius=10)
    fs.check(500, 500)
    assert not fs.tripped


def test_disabled_does_not_trip() -> None:
    fs = FailSafe(enabled=False)
    fs.check(0, 0)
    assert not fs.tripped


def test_manual_trip_invokes_callbacks() -> None:
    captured: list[str] = []
    fs = FailSafe(on_trip=[lambda reason: captured.append(reason)])
    fs.trip("kill_switch")
    assert fs.tripped
    assert captured == ["kill_switch"]


def test_raise_once_tripped() -> None:
    fs = FailSafe()
    fs.trip("kill_switch")
    with pytest.raises(FailSafeTripped):
        fs.check(999, 999)


def test_reset() -> None:
    fs = FailSafe()
    fs.trip("x")
    fs.reset()
    assert not fs.tripped
