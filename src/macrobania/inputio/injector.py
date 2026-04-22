"""입력 주입 (Injector).

:class:`InputInjector`        — pydirectinput 기반 실주입
:class:`DryRunInjector`       — 실제 입력 대신 로그만 남김 (기본값)
:class:`RecordingInjector`    — DB audit_log + 파일 audit 병행 (wrapper)
"""
from __future__ import annotations

import time
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Protocol

from macrobania.logging import get_logger
from macrobania.models import ActionType

log = get_logger(__name__)


class Injector(Protocol):
    """주입 인터페이스."""

    dry_run: bool

    def move(self, x: int, y: int, duration_ms: int = 0) -> None: ...
    def click(self, x: int, y: int, button: str = "left") -> None: ...
    def double_click(self, x: int, y: int, button: str = "left") -> None: ...
    def drag(self, x1: int, y1: int, x2: int, y2: int, *, button: str = "left", duration_ms: int = 300) -> None: ...
    def type_text(self, text: str, *, interval_ms: int = 10) -> None: ...
    def hotkey(self, keys: Sequence[str]) -> None: ...
    def scroll(self, dx: int, dy: int, x: int | None = None, y: int | None = None) -> None: ...
    def wait(self, ms: int) -> None: ...


@dataclass
class DryRunInjector:
    """아무것도 하지 않고 로그만 남기는 injector (기본값)."""

    dry_run: bool = True
    calls: list[tuple[str, tuple, dict]] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.calls is None:
            self.calls = []

    def _record(self, name: str, *args: object, **kwargs: object) -> None:
        self.calls.append((name, args, kwargs))
        log.info("inject.dry", action=name, args=args, kwargs=kwargs)

    def move(self, x: int, y: int, duration_ms: int = 0) -> None:
        self._record("move", x, y, duration_ms=duration_ms)

    def click(self, x: int, y: int, button: str = "left") -> None:
        self._record("click", x, y, button=button)

    def double_click(self, x: int, y: int, button: str = "left") -> None:
        self._record("double_click", x, y, button=button)

    def drag(
        self, x1: int, y1: int, x2: int, y2: int, *, button: str = "left", duration_ms: int = 300
    ) -> None:
        self._record("drag", x1, y1, x2, y2, button=button, duration_ms=duration_ms)

    def type_text(self, text: str, *, interval_ms: int = 10) -> None:
        self._record("type_text", text, interval_ms=interval_ms)

    def hotkey(self, keys: Sequence[str]) -> None:
        self._record("hotkey", list(keys))

    def scroll(self, dx: int, dy: int, x: int | None = None, y: int | None = None) -> None:
        self._record("scroll", dx, dy, x=x, y=y)

    def wait(self, ms: int) -> None:
        # Dry-run에서도 실제 대기는 허용 — 타이밍 의존 로직 테스트용
        time.sleep(ms / 1000.0)
        self._record("wait", ms)


class InputInjector:
    """pydirectinput 기반 실주입."""

    dry_run: bool = False

    def __init__(self) -> None:
        try:
            import pydirectinput

            self._pdi = pydirectinput
            self._pdi.FAILSAFE = True
            self._pdi.PAUSE = 0  # 기본 50ms 지연 제거 (우리가 직접 관리)
        except ImportError as e:
            raise RuntimeError(
                "pydirectinput not installed — 'uv sync --extra inject' 필요"
            ) from e

    def move(self, x: int, y: int, duration_ms: int = 0) -> None:
        self._pdi.moveTo(x, y, duration=duration_ms / 1000.0 if duration_ms else 0.0)

    def click(self, x: int, y: int, button: str = "left") -> None:
        self._pdi.click(x=x, y=y, button=button)

    def double_click(self, x: int, y: int, button: str = "left") -> None:
        self._pdi.doubleClick(x=x, y=y, button=button)

    def drag(
        self, x1: int, y1: int, x2: int, y2: int, *, button: str = "left", duration_ms: int = 300
    ) -> None:
        self._pdi.moveTo(x1, y1)
        self._pdi.mouseDown(button=button)
        self._pdi.moveTo(x2, y2, duration=duration_ms / 1000.0)
        self._pdi.mouseUp(button=button)

    def type_text(self, text: str, *, interval_ms: int = 10) -> None:
        self._pdi.typewrite(text, interval=interval_ms / 1000.0)

    def hotkey(self, keys: Sequence[str]) -> None:
        self._pdi.hotkey(*keys)

    def scroll(self, dx: int, dy: int, x: int | None = None, y: int | None = None) -> None:
        if x is not None and y is not None:
            self._pdi.moveTo(x, y)
        # pydirectinput.scroll은 세로 기본
        if dy:
            self._pdi.scroll(dy * 100)

    def wait(self, ms: int) -> None:
        time.sleep(ms / 1000.0)


def make_injector(*, dry_run: bool) -> Injector:
    if dry_run:
        return DryRunInjector()
    try:
        return InputInjector()
    except RuntimeError as e:
        log.warning("injector.fallback_dry_run", reason=str(e))
        return DryRunInjector()


# --- action → injector 호출 매핑 ---


def execute_action(
    injector: Injector,
    *,
    action_type: ActionType,
    center: tuple[int, int] | None = None,
    to_center: tuple[int, int] | None = None,
    value: str | None = None,
    modifiers: Iterable[str] = (),
    wait_ms: int | None = None,
) -> None:
    """Action 실행 편의 함수."""
    if action_type is ActionType.CLICK:
        assert center is not None, "click needs center"
        injector.click(*center)
    elif action_type is ActionType.DOUBLE_CLICK:
        assert center is not None
        injector.double_click(*center)
    elif action_type is ActionType.DRAG:
        assert center is not None and to_center is not None
        injector.drag(center[0], center[1], to_center[0], to_center[1])
    elif action_type is ActionType.TYPE:
        assert value is not None
        injector.type_text(value)
    elif action_type is ActionType.HOTKEY:
        keys = list(modifiers)
        if value:
            keys.append(value)
        injector.hotkey(keys)
    elif action_type is ActionType.SCROLL:
        dy = -1
        if value:
            with_sign = value.lower()
            dy = -1 if "down" in with_sign else 1
        injector.scroll(0, dy, *(center or (None, None)))
    elif action_type is ActionType.WAIT:
        injector.wait(wait_ms or 500)
    elif action_type is ActionType.FOCUS_WINDOW:
        # 이 레벨에서 직접 창 포커스 구현은 생략 (Phase 5)
        log.info("inject.focus_window_noop", hint=value)
    elif action_type is ActionType.DONE:
        return
