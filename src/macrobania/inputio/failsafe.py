"""Fail-safe 메커니즘.

1. **Corner FAILSAFE**: 마우스가 좌상단 (0,0) 근처에 있으면 ``check()`` 가 예외 발생
2. **Kill-switch 콜백**: ``FailSafe.on_trip`` 에 등록된 콜백 실행

전역 hotkey 처리는 pynput keyboard.GlobalHotKeys로 별도 도입 (Phase 5).
"""
from __future__ import annotations

import contextlib
import threading
from collections.abc import Callable
from dataclasses import dataclass, field


class FailSafeTripped(RuntimeError):
    """사용자 의도 중단."""


@dataclass
class FailSafe:
    """재생 루프에서 주기적으로 ``check()`` 호출."""

    corner_radius: int = 10
    enabled: bool = True
    _tripped: threading.Event = field(default_factory=threading.Event, init=False, repr=False)
    on_trip: list[Callable[[str], None]] = field(default_factory=list)

    def trip(self, reason: str) -> None:
        if self._tripped.is_set():
            return
        self._tripped.set()
        for cb in self.on_trip:
            with contextlib.suppress(Exception):
                cb(reason)

    def reset(self) -> None:
        self._tripped.clear()

    @property
    def tripped(self) -> bool:
        return self._tripped.is_set()

    def check(self, mouse_x: int, mouse_y: int) -> None:
        if not self.enabled:
            return
        if self._tripped.is_set():
            raise FailSafeTripped("kill_switch")
        if abs(mouse_x) <= self.corner_radius and abs(mouse_y) <= self.corner_radius:
            self.trip("corner")
            raise FailSafeTripped("corner")
