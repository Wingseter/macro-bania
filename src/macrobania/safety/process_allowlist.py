"""프로세스 화이트리스트.

Play 시 활성 창의 프로세스가 녹화 시점 ``target_process`` 와 매치되는지 확인.
"""
from __future__ import annotations

import contextlib
from dataclasses import dataclass

from macrobania.logging import get_logger

log = get_logger(__name__)


class ProcessNotAllowedError(RuntimeError):
    """허용 프로세스가 아니다."""


@dataclass
class ProcessAllowlist:
    """허용 프로세스명(대소문자 무시) 목록."""

    names: list[str]
    enabled: bool = True

    def normalize(self, name: str) -> str:
        return name.strip().lower()

    def is_allowed(self, process_name: str) -> bool:
        if not self.enabled:
            return True
        n = self.normalize(process_name)
        return any(self.normalize(x) == n for x in self.names)

    def check(self, process_name: str) -> None:
        if not self.is_allowed(process_name):
            raise ProcessNotAllowedError(
                f"active process {process_name!r} not in allowlist {self.names!r}"
            )


def active_window_process() -> str:
    """현재 포커스된 창의 프로세스 이름 (실패 시 빈 문자열).

    Windows 전용. pywin32/psutil이 없으면 빈 문자열.
    """
    with contextlib.suppress(Exception):
        import platform as _pf

        if _pf.system() != "Windows":
            return ""
        import ctypes

        import psutil

        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return ""
        pid = ctypes.c_ulong(0)
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == 0:
            return ""
        p = psutil.Process(pid.value)
        return p.name()
    return ""
