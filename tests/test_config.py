from __future__ import annotations

from pathlib import Path

import pytest

from macrobania.config import Settings, get_settings, reset_settings


def test_derived_paths(tmp_path: Path) -> None:
    s = Settings(data_dir=tmp_path)
    assert s.db_path == tmp_path / "macrobania.sqlite"
    assert s.recordings_dir == tmp_path / "recordings"
    assert s.audit_log_path == tmp_path / "audit.log"


def test_ensure_dirs(tmp_path: Path) -> None:
    s = Settings(data_dir=tmp_path / "deep" / "nested")
    s.ensure_dirs()
    assert s.data_dir.exists()
    assert s.recordings_dir.exists()
    assert s.models_dir.exists()


def test_env_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MACROBANIA_VLM_GROUNDER_MODEL", "ui-venus:2b")
    monkeypatch.setenv("MACROBANIA_DATA_DIR", str(tmp_path))
    reset_settings()
    s = get_settings()
    assert s.vlm.grounder_model == "ui-venus:2b"
    assert s.data_dir == tmp_path


def test_singleton() -> None:
    reset_settings()
    a = get_settings()
    b = get_settings()
    assert a is b
