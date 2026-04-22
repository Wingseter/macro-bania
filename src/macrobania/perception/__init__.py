"""Hybrid Perception — UIA + OCR + Screenshot.

 - :mod:`uia`     : pywinauto UIA 트리 스냅샷 (Windows only)
 - :mod:`ocr`     : RapidOCR ONNX 래퍼 (있을 때만)
 - :mod:`matcher` : UIA+OCR → Grounder 후보 감축 (Phase 4)
"""
from __future__ import annotations

from macrobania.perception.matcher import (
    MatcherConfig,
    MatcherResult,
    ScoredCandidate,
    find_candidates,
)
from macrobania.perception.ocr import OCRBlock, OCREngine, OCRUnavailableError
from macrobania.perception.uia import (
    UIAControl,
    UIASnapshot,
    UIASnapshotter,
    UIAUnavailableError,
)

__all__ = [
    "MatcherConfig",
    "MatcherResult",
    "OCRBlock",
    "OCREngine",
    "OCRUnavailableError",
    "ScoredCandidate",
    "UIAControl",
    "UIASnapshot",
    "UIASnapshotter",
    "UIAUnavailableError",
    "find_candidates",
]
