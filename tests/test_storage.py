from __future__ import annotations

from pathlib import Path

import pytest

from macrobania.storage import open_db
from macrobania.storage.db import SCHEMA_VERSION


def test_schema_applied(tmp_path: Path) -> None:
    db = open_db(tmp_path / "test.sqlite")
    with db:
        conn = db.connect()
        v = conn.execute("PRAGMA user_version").fetchone()[0]
        assert v == SCHEMA_VERSION
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        for expected in {
            "recordings",
            "raw_events",
            "frames",
            "steps",
            "audit_log",
            "sessions",
        }:
            assert expected in tables


def test_transaction_rollback(tmp_path: Path) -> None:
    db = open_db(tmp_path / "t.sqlite")
    with db, pytest.raises(RuntimeError), db.transaction() as conn:
        conn.execute(
            "INSERT INTO recordings (id, task_name, created_at, os, resolution_w, resolution_h) "
            "VALUES (?,?,?,?,?,?)",
            ("rec_x", "x", "2026-01-01", "Windows", 1, 1),
        )
        raise RuntimeError("boom")
    # 새 연결로 다시 확인
    db2 = open_db(tmp_path / "t.sqlite")
    with db2:
        conn = db2.connect()
        count = conn.execute("SELECT COUNT(*) FROM recordings").fetchone()[0]
        assert count == 0


def test_transaction_commit(tmp_path: Path) -> None:
    db = open_db(tmp_path / "t.sqlite")
    with db:
        with db.transaction() as conn:
            conn.execute(
                "INSERT INTO recordings (id, task_name, created_at, os, resolution_w, resolution_h) "
                "VALUES (?,?,?,?,?,?)",
                ("rec_y", "y", "2026-01-01", "Windows", 1920, 1080),
            )
        conn = db.connect()
        count = conn.execute("SELECT COUNT(*) FROM recordings").fetchone()[0]
        assert count == 1


def test_json_helpers(tmp_path: Path) -> None:
    db = open_db(tmp_path / "t.sqlite")
    raw = db.store_json({"a": 1, "b": [1, 2]})
    assert '"a":1' in raw
    loaded = db.load_json(raw)
    assert loaded == {"a": 1, "b": [1, 2]}
