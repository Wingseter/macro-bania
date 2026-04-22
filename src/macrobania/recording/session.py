"""녹화 세션 오케스트레이터.

 - 캡처 쓰레드: N FPS로 프레임을 폴링, 픽셀 diff ≥ 2% 또는 keyframe 주기면 writer에 저장
 - 입력 리스너: pynput이 자체 쓰레드에서 이벤트를 큐로 push
 - 메인 쓰레드: stop 요청을 받을 때까지 대기, 주기적으로 이벤트 플러시
"""
from __future__ import annotations

import dataclasses
import platform as py_platform
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime

from macrobania.capture import CaptureBackend, FrameData, open_backend
from macrobania.capture.frame_diff import significantly_changed
from macrobania.config import Settings, get_settings
from macrobania.inputio import InputListener
from macrobania.logging import get_logger
from macrobania.models import Platform, Recording
from macrobania.recording.writer import RecordingWriter
from macrobania.storage import Database, get_db

log = get_logger(__name__)


def _detect_platform() -> Platform:
    """실행 환경의 해상도/DPI를 Best-effort로 탐지."""
    os_name = f"{py_platform.system()} {py_platform.release()}"
    res: tuple[int, int] = (1920, 1080)
    dpi: float = 1.0
    try:
        import mss

        with mss.mss() as sct:
            mon = sct.monitors[1]
            res = (int(mon["width"]), int(mon["height"]))
    except Exception:
        pass
    try:
        if py_platform.system() == "Windows":
            import ctypes

            user32 = ctypes.windll.user32  # type: ignore[attr-defined]
            user32.SetProcessDPIAware()
            dpi = user32.GetDpiForSystem() / 96.0
    except Exception:
        pass
    return Platform(os=os_name, resolution=res, dpi_scale=dpi)


def _rec_id() -> str:
    # "rec_2026-04-22_14-33-01-123"
    return "rec_" + datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")[:-3]


@dataclass
class RecorderConfig:
    capture_fps: int = 6  # 초당 캡처 샘플링. VLM 호출 안 하므로 저부하.
    keyframe_interval_s: float = 5.0
    diff_threshold: float = 0.02
    flush_interval_s: float = 0.5
    capture_monitor: int = 0


@dataclass
class RecordingSession:
    """1회 녹화.

    ``run()`` 은 blocking. ``stop()`` 호출 또는 hotkey/시간초과로 종료.
    외부 이벤트로 종료하려면 ``asyncio.to_thread(session.run)`` 로 감싸라.
    """

    task_name: str
    description: str = ""
    target_process: str | None = None
    target_window_title_regex: str | None = None
    cfg: RecorderConfig = field(default_factory=RecorderConfig)
    settings: Settings = field(default_factory=get_settings)
    _stop: threading.Event = field(default_factory=threading.Event, init=False, repr=False)
    _capture: CaptureBackend | None = field(default=None, init=False, repr=False)
    _listener: InputListener | None = field(default=None, init=False, repr=False)
    _writer: RecordingWriter | None = field(default=None, init=False, repr=False)
    recording: Recording | None = field(default=None, init=False, repr=False)

    # --- public API ---

    def stop(self) -> None:
        self._stop.set()

    def run(self, *, db: Database | None = None) -> Recording:
        """blocking 녹화 루프."""
        settings = self.settings
        settings.ensure_dirs()
        db = db or get_db(settings)

        rec_id = _rec_id()
        rec_dir = settings.recordings_dir / rec_id
        platform = _detect_platform()

        self._writer = RecordingWriter(
            db=db,
            rec_dir=rec_dir,
            rec_id=rec_id,
            task_name=self.task_name,
            description=self.description,
            platform=platform,
            target_process=self.target_process,
            target_window_title_regex=self.target_window_title_regex,
        )
        self._writer.create()
        log.info(
            "session.start",
            rec_id=rec_id,
            capture_fps=self.cfg.capture_fps,
            resolution=platform.resolution,
        )

        self._capture = open_backend()
        self._listener = InputListener()
        self._listener.start()

        try:
            self._loop()
        finally:
            assert self._listener is not None
            assert self._capture is not None
            assert self._writer is not None
            self._listener.stop()
            # 마지막 잔여 이벤트 플러시
            remaining = self._listener.drain()
            if remaining:
                self._writer.write_events(remaining)
            self._capture.close()
            self.recording = self._writer.finalize()

        return self.recording

    # --- internals ---

    def _loop(self) -> None:
        assert self._capture is not None
        assert self._listener is not None
        assert self._writer is not None

        period = 1.0 / max(1, self.cfg.capture_fps)
        last_keyframe = 0.0
        last_flush = 0.0
        last_frame: FrameData | None = None

        while not self._stop.is_set():
            tick = time.monotonic()

            try:
                frame = self._capture.grab(monitor=self.cfg.capture_monitor)
            except Exception as e:
                log.warning("capture.grab_failed", error=str(e))
                time.sleep(period)
                continue

            is_keyframe = (tick - last_keyframe) >= self.cfg.keyframe_interval_s
            should_save = is_keyframe or last_frame is None
            if (
                not should_save
                and last_frame is not None
                and significantly_changed(
                    last_frame.image, frame.image, min_ratio=self.cfg.diff_threshold
                )
            ):
                should_save = True

            if should_save:
                self._writer.write_frame(frame, is_keyframe=is_keyframe)
                last_frame = frame
                if is_keyframe:
                    last_keyframe = tick

            # 이벤트 플러시
            if (tick - last_flush) >= self.cfg.flush_interval_s:
                evs = self._listener.drain()
                if evs:
                    self._writer.write_events(evs)
                last_flush = tick

            elapsed = time.monotonic() - tick
            if elapsed < period:
                self._stop.wait(period - elapsed)

    def snapshot_state(self) -> dict[str, object]:
        """관측/테스트용 상태 덤프."""
        return dataclasses.asdict(self.cfg) | {"stopped": self._stop.is_set()}
