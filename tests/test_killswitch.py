from macrobania.inputio.failsafe import FailSafe, FailSafeTripped
from macrobania.safety.killswitch import KillSwitch, _normalize_hotkey


def test_normalize_hotkey_wrap_modifiers() -> None:
    assert _normalize_hotkey("ctrl+shift+esc") == "<ctrl>+<shift>+<esc>"


def test_normalize_hotkey_single_char_unwrapped() -> None:
    assert _normalize_hotkey("ctrl+a") == "<ctrl>+a"


def test_normalize_hotkey_trims_and_lowercases() -> None:
    assert _normalize_hotkey(" CTRL + Shift + F1 ") == "<ctrl>+<shift>+<f1>"


def test_killswitch_construction_does_not_fail() -> None:
    fs = FailSafe()
    ks = KillSwitch(failsafe=fs, combo="ctrl+shift+esc")
    # start는 pynput global hook에 접근하므로 테스트에서는 호출하지 않음
    # 대신 failsafe 직접 trip 테스트
    ks.failsafe.trip("kill_switch")
    try:
        ks.failsafe.check(500, 500)
    except FailSafeTripped as e:
        assert str(e) == "kill_switch"


def test_extra_on_trip_registered_before_start() -> None:
    fs = FailSafe()
    called: list[str] = []
    ks = KillSwitch(failsafe=fs, extra_on_trip=[lambda: called.append("!")])
    # start/stop 대신 직접 fs.trip — extra_on_trip은 KillSwitch 내부 콜백에서 실행되므로
    # 기능적 테스트: 속성이 보관되는지만 확인
    assert ks.extra_on_trip[0]() is None
    assert called == ["!"]
