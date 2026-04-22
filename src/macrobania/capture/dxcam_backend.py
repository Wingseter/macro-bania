"""DXCam 기반 캡처 백엔드 (Windows 전용, 선택적 의존성).

DXcam은 설치 실패 또는 미설치 가능. 이 모듈 import 자체는 성공해야 한다.
실제 instance 생성 시에 DXcam이 없으면 ImportError.
"""
from __future__ import annotations

import contextlib

from PIL import Image

from macrobania.capture.backend import FrameData, now_ns


class DXCamBackend:
    """DXGI Desktop Duplication 기반 고속 캡처."""

    name = "dxcam"

    def __init__(self, *, target_fps: int = 30) -> None:
        import dxcam

        self._dxcam_mod = dxcam
        self._target_fps = target_fps
        self._cam = dxcam.create(output_idx=0, output_color="RGB")
        if self._cam is None:
            raise RuntimeError("dxcam.create returned None (adapter/output issue)")

    def grab(self, monitor: int = 0) -> FrameData:
        # dxcam.grab() returns numpy ndarray (H,W,3) in RGB, or None if no new frame
        frame = self._cam.grab()
        if frame is None:
            # 이전 프레임 재사용이 불가하므로 blocking 방식으로 재시도
            frame = self._cam.grab()
        if frame is None:
            raise RuntimeError("DXCam produced no frame (display lost?)")
        h, w = frame.shape[:2]
        image = Image.fromarray(frame)
        return FrameData(
            image=image,
            ts_ns=now_ns(),
            monitor=monitor,
            resolution=(w, h),
        )

    def close(self) -> None:
        with contextlib.suppress(Exception):
            self._cam.release()
