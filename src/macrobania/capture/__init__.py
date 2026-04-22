"""화면 캡처 레이어.

 - :class:`CaptureBackend` — 공통 프로토콜
 - :class:`MSSBackend` — mss 폴백 (크로스 플랫폼)
 - :class:`DXCamBackend` — DXGI Desktop Duplication (Windows only, 선택)
 - :func:`open_backend` — 환경에 맞는 백엔드 자동 선택
"""
from __future__ import annotations

from macrobania.capture.backend import CaptureBackend, FrameData, open_backend
from macrobania.capture.frame_diff import frame_diff_ratio
from macrobania.capture.mss_backend import MSSBackend

__all__ = [
    "CaptureBackend",
    "FrameData",
    "MSSBackend",
    "frame_diff_ratio",
    "open_backend",
]
