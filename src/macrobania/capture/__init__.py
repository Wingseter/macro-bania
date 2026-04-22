"""화면 캡처 레이어 (Phase 1).

예정 구현:
  - :class:`DXCamBackend` — DXGI Desktop Duplication 기반, 고성능 (Windows)
  - :class:`MSSBackend` — mss 폴백 (크로스 플랫폼, P0 spike에서 사용)
  - 프레임 diff 기반 delta 저장

인터페이스는 :class:`CaptureBackend` Protocol로 추상화한다.
"""
from __future__ import annotations

from typing import Protocol

from PIL import Image


class CaptureBackend(Protocol):
    """캡처 백엔드 공통 인터페이스."""

    def grab(self, monitor: int = 0) -> Image.Image:
        """현재 프레임을 PIL 이미지로."""
        ...

    def close(self) -> None: ...


__all__ = ["CaptureBackend"]
