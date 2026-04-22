"""Hybrid Perception — UIA + OCR + Screenshot.

 - :mod:`uia` : pywinauto UIA 트리 스냅샷 (Windows only)
 - :mod:`ocr` : RapidOCR ONNX 래퍼 (있을 때만)
"""
from __future__ import annotations

from macrobania.perception.ocr import OCREngine, OCRUnavailableError
from macrobania.perception.uia import UIASnapshotter, UIAUnavailableError

__all__ = [
    "OCREngine",
    "OCRUnavailableError",
    "UIASnapshotter",
    "UIAUnavailableError",
]
