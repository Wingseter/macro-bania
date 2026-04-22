"""녹화 서브시스템.

 - :mod:`writer`  — SQLite + WebP 프레임 저장
 - :mod:`session` — 캡처·입력·UIA·OCR 조율하여 1회 녹화 수행
 - :mod:`repo`    — 녹화 조회/검사
 - :mod:`builder` — (Phase 2) raw event → semantic Step
"""
from __future__ import annotations

from macrobania.recording.repo import RecordingRepo, RecordingSummary
from macrobania.recording.session import RecordingSession
from macrobania.recording.writer import RecordingWriter

__all__ = [
    "RecordingRepo",
    "RecordingSession",
    "RecordingSummary",
    "RecordingWriter",
]
