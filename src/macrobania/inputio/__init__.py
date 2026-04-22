"""입력 이벤트 리스너 + 주입.

 - :class:`InputListener` — pynput 기반 전역 훅. RawEvent를 queue로 스트림.
 - :class:`FailSafe` — 좌상단 이동 + 전역 kill-switch
 - :class:`InputInjector` — (Phase 3) SendInput/pydirectinput 주입 [아직 미구현]
"""
from __future__ import annotations

from macrobania.inputio.failsafe import FailSafe, FailSafeTripped
from macrobania.inputio.listener import InputListener

__all__ = [
    "FailSafe",
    "FailSafeTripped",
    "InputListener",
]
