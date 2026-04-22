"""녹화 서브시스템.

 - :mod:`writer`  — SQLite + WebP 프레임 저장
 - :mod:`session` — 캡처·입력·UIA·OCR 조율하여 1회 녹화 수행
 - :mod:`repo`    — 녹화 조회/검사
 - :mod:`builder` — raw event → semantic Step (Phase 2)
 - :mod:`viewer`  — HTML 익스포트 (Phase 2)
"""
from __future__ import annotations

from macrobania.recording.builder import (
    BuilderConfig,
    SemanticizeResult,
    cluster,
    load_steps,
    semanticize,
)
from macrobania.recording.repo import RecordingRepo, RecordingSummary
from macrobania.recording.session import RecordingSession
from macrobania.recording.viewer import export_html
from macrobania.recording.writer import RecordingWriter

__all__ = [
    "BuilderConfig",
    "RecordingRepo",
    "RecordingSession",
    "RecordingSummary",
    "RecordingWriter",
    "SemanticizeResult",
    "cluster",
    "export_html",
    "load_steps",
    "semanticize",
]
