"""입력 이벤트 리스너 + 주입.

 - :class:`InputListener`  — pynput 기반 전역 훅. RawEvent를 queue로 스트림.
 - :class:`FailSafe`       — 좌상단 이동 + 전역 kill-switch
 - :class:`InputInjector`  — pydirectinput SendInput 기반 주입 (Phase 3)
 - :class:`DryRunInjector` — 실제 입력 없이 로그만
"""
from __future__ import annotations

from macrobania.inputio.failsafe import FailSafe, FailSafeTripped
from macrobania.inputio.injector import (
    DryRunInjector,
    Injector,
    InputInjector,
    execute_action,
    make_injector,
)
from macrobania.inputio.listener import InputListener

__all__ = [
    "DryRunInjector",
    "FailSafe",
    "FailSafeTripped",
    "Injector",
    "InputInjector",
    "InputListener",
    "execute_action",
    "make_injector",
]
