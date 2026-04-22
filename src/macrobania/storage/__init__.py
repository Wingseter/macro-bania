"""SQLite 기반 영속화 레이어.

녹화 메타데이터/이벤트/스텝은 SQLite에, 이미지(WebP)/UIA/OCR snapshot은 파일시스템에.
"""
from macrobania.storage.db import Database, get_db, open_db

__all__ = ["Database", "get_db", "open_db"]
