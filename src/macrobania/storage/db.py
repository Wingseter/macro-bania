"""SQLite 연결 헬퍼.

현재는 단순 sqlite3 래핑. 마이그레이션은 ``user_version`` pragma로.
"""
from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from importlib import resources
from pathlib import Path

from macrobania.config import Settings, get_settings

SCHEMA_VERSION = 1


def _load_schema_sql() -> str:
    return resources.files("macrobania.storage").joinpath("schema.sql").read_text(
        encoding="utf-8"
    )


class Database:
    """얇은 sqlite3 래퍼.

    - 자동으로 스키마를 확인/적용 (``user_version``).
    - JSON 필드 헬퍼 ``store_json`` / ``load_json``.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None

    # --- lifecycle ---

    def connect(self) -> sqlite3.Connection:
        if self._conn is not None:
            return self._conn
        conn = sqlite3.connect(self.path, isolation_level=None, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        self._conn = conn
        self._apply_schema(conn)
        return conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # --- context manager ---

    def __enter__(self) -> Database:
        self.connect()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        conn = self.connect()
        conn.execute("BEGIN")
        try:
            yield conn
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise

    # --- schema / version ---

    def _apply_schema(self, conn: sqlite3.Connection) -> None:
        current = conn.execute("PRAGMA user_version").fetchone()[0]
        if current == SCHEMA_VERSION:
            return
        if current == 0:
            conn.executescript(_load_schema_sql())
            return
        raise RuntimeError(
            f"SQLite schema v{current} not upgradable to v{SCHEMA_VERSION} yet. "
            "Migration helper will arrive in Phase 1+."
        )

    # --- helpers ---

    @staticmethod
    def store_json(obj: object) -> str:
        return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))

    @staticmethod
    def load_json(text: str) -> object:
        return json.loads(text) if text else None


_db_singleton: Database | None = None


def get_db(settings: Settings | None = None) -> Database:
    """전역 Database 싱글톤."""
    global _db_singleton
    if _db_singleton is None:
        s = settings or get_settings()
        s.ensure_dirs()
        _db_singleton = Database(s.db_path)
    return _db_singleton


def open_db(path: Path) -> Database:
    """임의 경로 Database (테스트용)."""
    return Database(path)


def reset_db_singleton() -> None:
    global _db_singleton
    if _db_singleton is not None:
        _db_singleton.close()
    _db_singleton = None
