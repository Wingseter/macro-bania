from macrobania.inputio.injector import (
    DryRunInjector,
    execute_action,
    make_injector,
)
from macrobania.models import ActionType


def test_dry_run_records_calls() -> None:
    inj = DryRunInjector()
    inj.click(100, 200, button="right")
    inj.type_text("hello")
    inj.hotkey(["ctrl", "s"])
    assert inj.calls[0][0] == "click"
    assert inj.calls[0][1] == (100, 200)
    assert inj.calls[0][2]["button"] == "right"
    assert inj.calls[1][0] == "type_text"
    assert inj.calls[2][0] == "hotkey"


def test_execute_action_click() -> None:
    inj = DryRunInjector()
    execute_action(inj, action_type=ActionType.CLICK, center=(50, 60))
    name, args, kwargs = inj.calls[0]
    assert name == "click"
    assert args == (50, 60)
    assert kwargs.get("button") == "left"


def test_execute_action_drag() -> None:
    inj = DryRunInjector()
    execute_action(
        inj, action_type=ActionType.DRAG, center=(10, 10), to_center=(100, 100)
    )
    assert inj.calls[0][0] == "drag"
    assert inj.calls[0][1] == (10, 10, 100, 100)


def test_execute_action_type() -> None:
    inj = DryRunInjector()
    execute_action(inj, action_type=ActionType.TYPE, value="abc")
    assert inj.calls[0] == ("type_text", ("abc",), {"interval_ms": 10})


def test_execute_action_hotkey() -> None:
    inj = DryRunInjector()
    execute_action(
        inj, action_type=ActionType.HOTKEY, value="s", modifiers=["ctrl", "shift"]
    )
    assert inj.calls[0][0] == "hotkey"
    assert inj.calls[0][1] == (["ctrl", "shift", "s"],)


def test_execute_action_wait() -> None:
    inj = DryRunInjector()
    execute_action(inj, action_type=ActionType.WAIT, wait_ms=10)
    assert inj.calls[0][0] == "wait"
    assert inj.calls[0][1] == (10,)


def test_make_injector_dry_run() -> None:
    inj = make_injector(dry_run=True)
    assert isinstance(inj, DryRunInjector)
    assert inj.dry_run is True
