"""RapidOCR 기반 OCR 래퍼 (선택적).

모델이 없으면 :class:`OCRUnavailableError`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PIL import Image

from macrobania.logging import get_logger

log = get_logger(__name__)


class OCRUnavailableError(RuntimeError):
    pass


@dataclass(frozen=True)
class OCRBlock:
    text: str
    bbox: tuple[int, int, int, int]  # x1,y1,x2,y2
    confidence: float


class OCREngine:
    """RapidOCR 지연 초기화 래퍼.

    기본값은 ONNXRuntime 기반(CPU). GPU 지원은 Phase 5에서.
    """

    def __init__(self) -> None:
        self._engine: Any | None = None

    def available(self) -> bool:
        try:
            import rapidocr_onnxruntime  # noqa: F401

            return True
        except Exception:
            return False

    def _ensure_engine(self) -> Any:
        if self._engine is not None:
            return self._engine
        try:
            from rapidocr_onnxruntime import RapidOCR
        except Exception as e:
            raise OCRUnavailableError(f"rapidocr not installed: {e}") from e
        self._engine = RapidOCR()
        return self._engine

    def read(self, image: Image.Image) -> list[OCRBlock]:
        engine = self._ensure_engine()
        import numpy as np

        arr = np.asarray(image.convert("RGB"))[:, :, ::-1]  # RGB → BGR for rapidocr
        result, _ = engine(arr)
        if result is None:
            return []
        blocks: list[OCRBlock] = []
        for box, text, conf in result:
            # box: [[x1,y1],[x2,y1],[x2,y2],[x1,y2]]
            xs = [int(p[0]) for p in box]
            ys = [int(p[1]) for p in box]
            bbox = (min(xs), min(ys), max(xs), max(ys))
            blocks.append(OCRBlock(text=str(text), bbox=bbox, confidence=float(conf)))
        return blocks
