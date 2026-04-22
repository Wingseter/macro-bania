"""PySide6 GUI (Phase 5, 최소 골격).

사용:
    macrobania gui
또는:
    python -m macrobania.ui

의존성: ``uv sync --extra ui``
"""
from __future__ import annotations


def run_gui() -> int:
    """blocking GUI main. 실패 시 예외."""
    from macrobania.ui.main_window import main as _main

    return _main()


__all__ = ["run_gui"]
