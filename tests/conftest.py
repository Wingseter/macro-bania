"""pytest 공통 fixture."""
from __future__ import annotations

from pathlib import Path

import pytest

from macrobania import logging as mblog
from macrobania.config import Settings, reset_settings
from macrobania.storage import db as db_mod


@pytest.fixture
def tmp_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Settings:
    """격리된 임시 data_dir을 쓰는 Settings."""
    # 환경 오염 방지
    for key in list(__import__("os").environ):
        if key.startswith("MACROBANIA_"):
            monkeypatch.delenv(key, raising=False)

    reset_settings()
    db_mod.reset_db_singleton()
    mblog.reset_logging()

    settings = Settings(data_dir=tmp_path)
    settings.ensure_dirs()
    return settings
