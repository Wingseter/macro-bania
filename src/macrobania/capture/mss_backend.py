"""MSS 기반 캡처 백엔드 (크로스 플랫폼 폴백)."""
from __future__ import annotations

import contextlib

from PIL import Image

from macrobania.capture.backend import FrameData, now_ns


class MSSBackend:
    """mss ``ScreenShot`` → PIL 이미지."""

    name = "mss"

    def __init__(self) -> None:
        import mss

        self._mss_mod = mss
        self._sct = mss.mss()

    def grab(self, monitor: int = 0) -> FrameData:
        monitors = self._sct.monitors
        # mss.monitors[0] = 전체 가상 모니터, 1.. = 개별 모니터
        idx = monitor + 1 if monitor + 1 < len(monitors) else 1
        target = monitors[idx]
        raw = self._sct.grab(target)
        image = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
        return FrameData(
            image=image,
            ts_ns=now_ns(),
            monitor=monitor,
            resolution=raw.size,
        )

    def close(self) -> None:
        with contextlib.suppress(Exception):
            self._sct.close()
