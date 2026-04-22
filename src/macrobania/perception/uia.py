"""Windows UI Automation 트리 스냅샷.

pywinauto가 없거나 비-Windows 환경에서는 :class:`UIAUnavailableError`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from macrobania.logging import get_logger

log = get_logger(__name__)


class UIAUnavailableError(RuntimeError):
    pass


@dataclass
class UIAControl:
    """UIA 트리의 한 컨트롤."""

    role: str
    name: str
    automation_id: str = ""
    class_name: str = ""
    bbox: tuple[int, int, int, int] = (0, 0, 0, 0)  # x1,y1,x2,y2
    children: list[UIAControl] = field(default_factory=list)


@dataclass
class UIASnapshot:
    hwnd: int
    window_title: str
    root: UIAControl


@dataclass
class UIASnapshotter:
    """pywinauto 기반 UIA 스냅샷.

    비용이 크므로 입력 이벤트 주변 ±300ms에만 호출 권장 (PLAN §11).
    """

    max_depth: int = 4
    _available: bool | None = None

    def available(self) -> bool:
        if self._available is not None:
            return self._available
        try:
            import pywinauto  # noqa: F401

            self._available = True
        except Exception:
            self._available = False
        return self._available

    def snapshot_foreground(self) -> UIASnapshot:
        if not self.available():
            raise UIAUnavailableError("pywinauto not available")

        from pywinauto import Desktop

        try:
            app = Desktop(backend="uia").window(active_only=True)
            el = app.element_info
        except Exception as e:
            raise UIAUnavailableError(f"no active window: {e}") from e

        hwnd = int(getattr(el, "handle", 0) or 0)
        title = str(getattr(el, "name", "") or "")
        root = self._walk(el, depth=0)
        return UIASnapshot(hwnd=hwnd, window_title=title, root=root)

    def _walk(self, el: Any, *, depth: int) -> UIAControl:
        try:
            rect = el.rectangle
            bbox = (int(rect.left), int(rect.top), int(rect.right), int(rect.bottom))
        except Exception:
            bbox = (0, 0, 0, 0)

        ctrl = UIAControl(
            role=str(getattr(el, "control_type", "") or ""),
            name=str(getattr(el, "name", "") or ""),
            automation_id=str(getattr(el, "automation_id", "") or ""),
            class_name=str(getattr(el, "class_name", "") or ""),
            bbox=bbox,
        )
        if depth >= self.max_depth:
            return ctrl
        try:
            for child in el.children():
                ctrl.children.append(self._walk(child, depth=depth + 1))
        except Exception:
            pass
        return ctrl
