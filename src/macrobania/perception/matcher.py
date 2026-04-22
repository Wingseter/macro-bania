"""UIA + OCR 후보 감축기 (Hybrid Perception core).

PLAN.md §9.2: VLM 호출 전 UIA/OCR로 후보를 좁힘. 후보가 정확히 1개면 VLM 스킵 가능.

스코어링 규칙(대소문자 무시, 공백 트림):
  - target 문자열과 UIA name 정확 일치      : 1.00
  - target 문자열과 OCR text  정확 일치      : 0.95
  - target 부분 일치 (UIA name contains)    : 0.70
  - target 부분 일치 (OCR text contains)    : 0.65
  - target 토큰 전부 포함 (소프트)           : 0.45
  - UIA role = target에서 언급된 role 힌트  : +0.10 보너스
  - hint_bbox와 겹치면(IoU > 0.2)           : +0.20 보너스
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from macrobania.agent.prompts import GrounderCandidate
from macrobania.logging import get_logger
from macrobania.perception.ocr import OCRBlock
from macrobania.perception.uia import UIAControl, UIASnapshot

log = get_logger(__name__)


_ROLE_HINTS = {
    "button": ("button",),
    "입력": ("edit", "textbox"),
    "텍스트": ("text",),
    "탭": ("tab", "tabitem"),
    "링크": ("hyperlink",),
    "메뉴": ("menu", "menuitem"),
    "체크": ("checkbox",),
}


@dataclass(frozen=True)
class ScoredCandidate:
    candidate: GrounderCandidate
    score: float
    match_reason: str = ""


@dataclass
class MatcherConfig:
    exact_threshold: float = 0.90
    unambiguous_gap: float = 0.20  # 1등과 2등 score 차이가 이만큼 나야 VLM 스킵
    max_candidates: int = 10


@dataclass
class MatcherResult:
    scored: list[ScoredCandidate]

    @property
    def candidates(self) -> list[GrounderCandidate]:
        return [s.candidate for s in self.scored]

    def unambiguous(self, cfg: MatcherConfig) -> ScoredCandidate | None:
        """단일 강력 후보면 반환 (VLM 스킵용)."""
        if not self.scored:
            return None
        best = self.scored[0]
        if best.score < cfg.exact_threshold:
            return None
        if len(self.scored) == 1:
            return best
        second = self.scored[1]
        if (best.score - second.score) >= cfg.unambiguous_gap:
            return best
        return None


def find_candidates(
    target: str,
    *,
    uia: UIASnapshot | None = None,
    ocr: list[OCRBlock] | None = None,
    hint_bbox_pixel: tuple[int, int, int, int] | None = None,
    cfg: MatcherConfig | None = None,
) -> MatcherResult:
    """target 서술 문자열에 대한 후보 목록.

    target은 자연어 문자열. 따옴표/괄호/힌트 제거 후 정규화.
    """
    cfg = cfg or MatcherConfig()
    norm_target = _normalize(target)
    if not norm_target:
        return MatcherResult(scored=[])

    scored: list[ScoredCandidate] = []
    next_id = 0

    if uia is not None:
        for ctrl in _flatten(uia.root):
            score, reason = _score_uia(ctrl, norm_target)
            if score <= 0:
                continue
            if hint_bbox_pixel is not None:
                score += _iou_bonus(ctrl.bbox, hint_bbox_pixel)
            scored.append(
                ScoredCandidate(
                    candidate=GrounderCandidate(
                        id=next_id,
                        source="uia",
                        label=ctrl.name or ctrl.role,
                        bbox_pixel=ctrl.bbox,
                    ),
                    score=min(score, 1.0),
                    match_reason=reason,
                )
            )
            next_id += 1

    if ocr is not None:
        for blk in ocr:
            score, reason = _score_ocr(blk, norm_target)
            if score <= 0:
                continue
            if hint_bbox_pixel is not None:
                score += _iou_bonus(blk.bbox, hint_bbox_pixel)
            scored.append(
                ScoredCandidate(
                    candidate=GrounderCandidate(
                        id=next_id,
                        source="ocr",
                        label=blk.text,
                        bbox_pixel=blk.bbox,
                    ),
                    score=min(score, 1.0),
                    match_reason=reason,
                )
            )
            next_id += 1

    scored.sort(key=lambda s: s.score, reverse=True)
    return MatcherResult(scored=scored[: cfg.max_candidates])


# --- scoring helpers ---


def _normalize(s: str) -> str:
    # 따옴표/괄호 안 힌트 제거 후 공백 정규화
    s = re.sub(r"[\"'`]", "", s)
    s = re.sub(r"\(.*?\)|\[.*?\]", "", s)
    return " ".join(s.lower().split())


def _score_uia(ctrl: UIAControl, target_norm: str) -> tuple[float, str]:
    name = _normalize(ctrl.name)
    role = (ctrl.role or "").lower()

    if not name and not role:
        return 0.0, ""

    if name and name == target_norm:
        return 1.0, "uia:name_exact"
    if name and target_norm in name:
        return 0.7, "uia:name_contains_target"
    if name and name in target_norm:
        return 0.6, "uia:target_contains_name"

    tokens = [t for t in target_norm.split() if t]
    if name and tokens and all(t in name for t in tokens):
        return 0.55, "uia:all_tokens_in_name"

    # role hint 보너스
    for hint, roles in _ROLE_HINTS.items():
        if hint in target_norm and any(r in role for r in roles):
            return 0.35, "uia:role_hint_only"
    return 0.0, ""


def _score_ocr(blk: OCRBlock, target_norm: str) -> tuple[float, str]:
    text = _normalize(blk.text)
    if not text:
        return 0.0, ""
    if text == target_norm:
        return 0.95, "ocr:text_exact"
    if target_norm in text:
        return 0.65, "ocr:contains_target"
    if text in target_norm:
        return 0.55, "ocr:target_contains_text"

    tokens = [t for t in target_norm.split() if len(t) >= 2]
    if tokens and all(t in text for t in tokens):
        return 0.45, "ocr:all_tokens"
    return 0.0, ""


def _flatten(root: UIAControl) -> list[UIAControl]:
    out: list[UIAControl] = []
    stack = [root]
    while stack:
        node = stack.pop()
        out.append(node)
        stack.extend(node.children)
    return out


def _iou_bonus(bbox_a: tuple[int, int, int, int], bbox_b: tuple[int, int, int, int]) -> float:
    x1 = max(bbox_a[0], bbox_b[0])
    y1 = max(bbox_a[1], bbox_b[1])
    x2 = min(bbox_a[2], bbox_b[2])
    y2 = min(bbox_a[3], bbox_b[3])
    if x2 <= x1 or y2 <= y1:
        return 0.0
    inter = (x2 - x1) * (y2 - y1)
    area_a = max(0, (bbox_a[2] - bbox_a[0]) * (bbox_a[3] - bbox_a[1]))
    area_b = max(0, (bbox_b[2] - bbox_b[0]) * (bbox_b[3] - bbox_b[1]))
    union = area_a + area_b - inter
    if union <= 0:
        return 0.0
    iou = inter / union
    return 0.2 if iou > 0.2 else 0.0
