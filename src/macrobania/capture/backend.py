"""캡처 백엔드 공통 인터페이스."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Protocol

from PIL import Image

from macrobania.logging import get_logger

log = get_logger(__name__)


@dataclass(frozen=True)
class FrameData:
    """캡처된 프레임."""

    image: Image.Image
    ts_ns: int
    monitor: int
    resolution: tuple[int, int]


class CaptureBackend(Protocol):
    """모든 캡처 백엔드가 구현해야 할 공통 인터페이스."""

    name: str

    def grab(self, monitor: int = 0) -> FrameData:
        """현재 프레임을 캡처."""
        ...

    def close(self) -> None:
        """리소스 해제."""
        ...


def now_ns() -> int:
    return time.monotonic_ns()


def open_backend(prefer: str = "auto") -> CaptureBackend:
    """환경에 맞는 캡처 백엔드를 반환.

    :param prefer: ``"auto"``, ``"dxcam"``, ``"mss"``
    """
    if prefer in ("auto", "dxcam"):
        try:
            from macrobania.capture.dxcam_backend import DXCamBackend

            backend = DXCamBackend()
            log.info("capture.backend_selected", backend="dxcam")
            return backend
        except Exception as e:
            if prefer == "dxcam":
                raise
            log.info("capture.dxcam_unavailable_fallback_mss", reason=str(e))

    from macrobania.capture.mss_backend import MSSBackend

    backend = MSSBackend()
    log.info("capture.backend_selected", backend="mss")
    return backend
