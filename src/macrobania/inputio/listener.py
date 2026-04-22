"""pynput 기반 전역 입력 리스너.

이벤트는 thread-safe 큐에 올라가며 별도 쓰레드(Writer)에서 소비된다.
"""
from __future__ import annotations

import contextlib
import queue
import threading
import time
from dataclasses import dataclass, field

from macrobania.logging import get_logger
from macrobania.models import EventKind, RawEvent

log = get_logger(__name__)


def _now_ns() -> int:
    return time.monotonic_ns()


@dataclass
class InputListener:
    """pynput 기반 전역 훅.

    :attr:`queue` 는 thread-safe FIFO. ``start()`` 후 ``stop()`` 호출 전까지
    pynput의 listener thread들이 이벤트를 push한다.
    """

    queue: queue.Queue[RawEvent] = field(default_factory=lambda: queue.Queue(maxsize=10_000))
    _mouse_listener: object | None = field(default=None, init=False, repr=False)
    _kbd_listener: object | None = field(default=None, init=False, repr=False)
    _started: threading.Event = field(default_factory=threading.Event, init=False, repr=False)

    def start(self) -> None:
        if self._started.is_set():
            return
        from pynput import keyboard, mouse

        def _push(evt: RawEvent) -> None:
            try:
                self.queue.put_nowait(evt)
            except queue.Full:
                log.warning("input.queue_full")

        def _on_move(x: int, y: int) -> None:
            _push(RawEvent(ts_ns=_now_ns(), kind=EventKind.MOUSE_MOVE, x=int(x), y=int(y)))

        def _on_click(x: int, y: int, button: object, pressed: bool) -> None:
            name = getattr(button, "name", str(button)).lower()
            btn = "left" if "left" in name else "right" if "right" in name else "middle"
            _push(
                RawEvent(
                    ts_ns=_now_ns(),
                    kind=EventKind.MOUSE_DOWN if pressed else EventKind.MOUSE_UP,
                    x=int(x),
                    y=int(y),
                    button=btn,  # type: ignore[arg-type]
                )
            )

        def _on_scroll(x: int, y: int, dx: int, dy: int) -> None:
            _push(
                RawEvent(
                    ts_ns=_now_ns(),
                    kind=EventKind.SCROLL,
                    x=int(x),
                    y=int(y),
                    dx=int(dx),
                    dy=int(dy),
                )
            )

        def _on_press(key: object) -> None:
            vk = getattr(key, "vk", None)
            _push(RawEvent(ts_ns=_now_ns(), kind=EventKind.KEY_DOWN, vk=vk))

        def _on_release(key: object) -> None:
            vk = getattr(key, "vk", None)
            _push(RawEvent(ts_ns=_now_ns(), kind=EventKind.KEY_UP, vk=vk))

        self._mouse_listener = mouse.Listener(
            on_move=_on_move, on_click=_on_click, on_scroll=_on_scroll
        )
        self._kbd_listener = keyboard.Listener(on_press=_on_press, on_release=_on_release)
        self._mouse_listener.start()  # type: ignore[union-attr]
        self._kbd_listener.start()  # type: ignore[union-attr]
        self._started.set()
        log.info("input.listener_started")

    def stop(self) -> None:
        if not self._started.is_set():
            return
        if self._mouse_listener is not None:
            with contextlib.suppress(Exception):
                self._mouse_listener.stop()  # type: ignore[union-attr]
        if self._kbd_listener is not None:
            with contextlib.suppress(Exception):
                self._kbd_listener.stop()  # type: ignore[union-attr]
        self._started.clear()
        log.info("input.listener_stopped")

    def drain(self) -> list[RawEvent]:
        """버퍼된 이벤트 전부 빼내기."""
        out: list[RawEvent] = []
        while True:
            try:
                out.append(self.queue.get_nowait())
            except queue.Empty:
                break
        return out

    def __enter__(self) -> InputListener:
        self.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.stop()
