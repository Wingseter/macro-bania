"""Grounder — 스크린샷 + 타깃 서술 → NormBBox.

모델 출력 변형이 있을 수 있어 관대한 파서 사용:
  - ``bbox`` 는 배열 [x1,y1,x2,y2] 또는 {"x1":.., "y1":..., ...} 모두 허용
  - 0~1000 정규화 범위를 초과하면 clamp
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PIL import Image

from macrobania.agent.client import VLMClient, extract_json
from macrobania.agent.prompts import (
    GROUNDER_SYSTEM,
    GrounderCandidate,
    format_grounder_user,
)
from macrobania.config import get_settings
from macrobania.logging import get_logger
from macrobania.models import GrounderResult, NormBBox

log = get_logger(__name__)


@dataclass
class Grounder:
    client: VLMClient
    model: str | None = None  # None이면 settings.vlm.grounder_model

    @classmethod
    def from_env(cls) -> Grounder:
        return cls(client=VLMClient.from_env())

    def locate(
        self,
        screenshot: Image.Image,
        *,
        target_description: str,
        hint_bbox_pixel: tuple[int, int, int, int] | None = None,
        hint_resolution: tuple[int, int] | None = None,
        candidates: list[GrounderCandidate] | None = None,
        max_tokens: int = 256,
    ) -> GrounderResult:
        model = self.model or get_settings().vlm.grounder_model
        user_text = format_grounder_user(
            target_description=target_description,
            hint_bbox_pixel=hint_bbox_pixel,
            hint_resolution=hint_resolution,
            current_resolution=screenshot.size,
            candidates=candidates,
        )
        log.debug(
            "grounder.locate",
            model=model,
            target=target_description[:60],
            candidates=len(candidates) if candidates else 0,
        )
        raw = self.client.chat_vision(
            model=model,
            system=GROUNDER_SYSTEM,
            user_text=user_text,
            images=[screenshot],
            max_tokens=max_tokens,
            temperature=0.0,
        )
        return parse_grounder_response(raw)


# --- 파서 (클라이언트 없이 단위 테스트 가능) ---


def parse_grounder_response(text: str) -> GrounderResult:
    obj = extract_json(text)
    bbox = _coerce_bbox(obj.get("bbox"))
    return GrounderResult(
        bbox=bbox,
        candidate_id=_coerce_int_or_none(obj.get("candidate_id")),
        confidence=_coerce_confidence(obj.get("confidence")),
        reason=str(obj.get("reason") or ""),
    )


def _coerce_bbox(raw: Any) -> NormBBox:
    if raw is None:
        raise ValueError("bbox field missing")
    if isinstance(raw, dict):
        coords = [raw.get("x1"), raw.get("y1"), raw.get("x2"), raw.get("y2")]
    elif isinstance(raw, (list, tuple)) and len(raw) == 4:
        coords = list(raw)
    else:
        raise ValueError(f"unsupported bbox shape: {raw!r}")

    clamped = [_clamp(round(float(c)), 0, 1000) for c in coords]
    x1, y1, x2, y2 = clamped
    if x2 < x1:
        x1, x2 = x2, x1
    if y2 < y1:
        y1, y2 = y2, y1
    return NormBBox(x1=x1, y1=y1, x2=x2, y2=y2)


def _clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))


def _coerce_int_or_none(raw: Any) -> int | None:
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _coerce_confidence(raw: Any) -> float:
    if raw is None:
        return 0.0
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, v))
