"""프롬프트 템플릿.

PLAN.md §13을 구현 수준으로 옮긴 것. Jinja가 과할 정도로 단순해서 f-string 유지.
"""
from __future__ import annotations

from dataclasses import dataclass

GROUNDER_SYSTEM = (
    "You are a GUI grounding assistant. Given a screenshot and a target description, "
    "return the bounding box of the exact UI element in 0-1000 normalized coords. "
    "You MAY receive pre-filtered candidates (UIA/OCR hits). Prefer them unless "
    "visual evidence clearly contradicts.\n"
    'Return ONLY one JSON object: {"bbox":[x1,y1,x2,y2],'
    '"candidate_id":int|null,"confidence":0.0-1.0,"reason":"..."}'
)


@dataclass(frozen=True)
class GrounderCandidate:
    """UIA/OCR가 제시한 후보."""

    id: int
    source: str  # "uia" | "ocr"
    label: str
    bbox_pixel: tuple[int, int, int, int]


def format_grounder_user(
    *,
    target_description: str,
    hint_bbox_pixel: tuple[int, int, int, int] | None,
    hint_resolution: tuple[int, int] | None,
    current_resolution: tuple[int, int],
    candidates: list[GrounderCandidate] | None = None,
) -> str:
    """Grounder user 프롬프트 조립."""
    lines: list[str] = []
    lines.append(f'Target: "{target_description}"')
    if hint_bbox_pixel is not None and hint_resolution is not None:
        lines.append(
            f"Hint (from recording): bbox={list(hint_bbox_pixel)} "
            f"@ {hint_resolution[0]}x{hint_resolution[1]}"
        )
    lines.append(f"Current resolution: {current_resolution[0]}x{current_resolution[1]}")
    if candidates:
        lines.append("Candidates:")
        for c in candidates:
            lines.append(
                f"  #{c.id} {c.source.upper()}: {c.label!r}, bbox={list(c.bbox_pixel)}"
            )
    return "\n".join(lines)


VERIFIER_SYSTEM = (
    "You verify a UI condition from a screenshot. "
    'Return ONLY: {"answer":"yes"|"no","reason":"..."}'
)


def format_verifier_user(question: str) -> str:
    return f"Question: {question}"
