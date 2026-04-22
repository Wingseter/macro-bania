"""프레임 간 픽셀 차이 비율 계산.

PLAN.md §11 녹화 원칙: diff ≥ 2% 일 때만 delta 저장.
"""
from __future__ import annotations

import numpy as np
from PIL import Image


def frame_diff_ratio(a: Image.Image, b: Image.Image, *, threshold: int = 16) -> float:
    """두 이미지 간 "변경된 픽셀" 비율 (0.0 ~ 1.0).

    각 채널별 절댓값 차 합이 ``threshold``(기본 16) 초과하면 변경으로 집계.
    해상도가 다르면 작은 쪽으로 리사이즈.
    """
    if a.size != b.size:
        b = b.resize(a.size)

    # RGB로 통일
    if a.mode != "RGB":
        a = a.convert("RGB")
    if b.mode != "RGB":
        b = b.convert("RGB")

    arr_a = np.asarray(a, dtype=np.int16)
    arr_b = np.asarray(b, dtype=np.int16)
    diff = np.abs(arr_a - arr_b).sum(axis=-1)  # (H,W)
    changed = (diff > threshold).sum()
    total = diff.size
    return float(changed) / float(total) if total else 0.0


def significantly_changed(
    a: Image.Image, b: Image.Image, *, min_ratio: float = 0.02
) -> bool:
    """diff 비율이 ``min_ratio`` (기본 2%) 이상이면 True."""
    return frame_diff_ratio(a, b) >= min_ratio
