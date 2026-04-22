"""전역 kill-switch hotkey.

기본: ``ctrl+shift+esc`` (PLAN.md §14 설정값).
pynput의 keyboard.GlobalHotKeys 기반.
"""
from __future__ import annotations

import contextlib
from collections.abc import Callable
from dataclasses import dataclass, field

from macrobania.inputio.failsafe import FailSafe
from macrobania.logging import get_logger

log = get_logger(__name__)


def _normalize_hotkey(combo: str) -> str:
    """`ctrl+shift+esc` → `<ctrl>+<shift>+<esc>` (pynput 포맷)."""
    parts = [p.strip().lower() for p in combo.split("+") if p.strip()]
    wrapped: list[str] = []
    for p in parts:
        if len(p) == 1:
            wrapped.append(p)
        else:
            wrapped.append(f"<{p}>")
    return "+".join(wrapped)


@dataclass
class KillSwitch:
    """글로벌 hotkey로 FailSafe.trip 유발."""

    failsafe: FailSafe
    combo: str = "ctrl+shift+esc"
    extra_on_trip: list[Callable[[], None]] = field(default_factory=list)
    _listener: object | None = field(default=None, init=False, repr=False)
    _active: bool = field(default=False, init=False, repr=False)

    def start(self) -> None:
        if self._active:
            return
        try:
            from pynput import keyboard
        except Exception as e:
            log.warning("killswitch.pynput_unavailable", error=str(e))
            return

        def _trip() -> None:
            log.info("killswitch.tripped", combo=self.combo)
            self.failsafe.trip("kill_switch")
            for cb in self.extra_on_trip:
                with contextlib.suppress(Exception):
                    cb()

        try:
            self._listener = keyboard.GlobalHotKeys(  # type: ignore[attr-defined]
                {_normalize_hotkey(self.combo): _trip}
            )
            self._listener.start()  # type: ignore[union-attr]
            self._active = True
            log.info("killswitch.started", combo=self.combo)
        except Exception as e:
            log.warning("killswitch.start_failed", error=str(e))

    def stop(self) -> None:
        if not self._active:
            return
        if self._listener is not None:
            with contextlib.suppress(Exception):
                self._listener.stop()  # type: ignore[union-attr]
        self._active = False
        log.info("killswitch.stopped")

    def __enter__(self) -> KillSwitch:
        self.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.stop()
