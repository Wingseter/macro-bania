"""Captioner — raw event + before/after 프레임 → Semantic Step.

사용자가 제안한 Qwen3.5-0.8B (기본) 활용 지점.
VLM이 없을 때도 동작하도록 ``rule_based_caption`` fallback 제공.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

from PIL import Image

from macrobania.agent.client import VLMClient, extract_json
from macrobania.config import get_settings
from macrobania.logging import get_logger
from macrobania.models import Action, ActionType, EventKind, RawEvent, Step

log = get_logger(__name__)

CAPTIONER_SYSTEM = (
    "You convert a sequence of low-level input events (with before/after screenshots) "
    "into ONE semantic step for a Windows desktop macro. "
    "Reply with ONLY one JSON object, no prose. Fields: "
    '{"type":"click"|"double_click"|"drag"|"type"|"hotkey"|"scroll"|"wait",'
    '"target_description":str, "caption":str, '
    '"precondition":str|null, "postcondition":str|null, "confidence":0-1}'
    " target_description is a human phrase of the UI element. "
    "caption is a short Korean sentence summarizing the action."
)


@dataclass
class CandidateStep:
    """이벤트 클러스터링 결과."""

    ts_start_ns: int
    ts_end_ns: int
    events: list[RawEvent]
    frame_before_path: str | None
    frame_after_path: str | None
    raw_event_ids: list[int]


@dataclass
class Captioner:
    client: VLMClient | None = None
    model: str | None = None  # None → settings.vlm.captioner_model

    @classmethod
    def from_env(cls) -> Captioner:
        return cls(client=VLMClient.from_env())

    def caption(
        self,
        candidate: CandidateStep,
        *,
        frame_before_img: Image.Image | None = None,
        frame_after_img: Image.Image | None = None,
        window_title: str | None = None,
    ) -> Step:
        """VLM이 있으면 의미 기반, 없으면 룰 기반 캡션."""
        if self.client is None or frame_before_img is None or frame_after_img is None:
            return rule_based_step(candidate)

        model = self.model or get_settings().vlm.captioner_model
        user_text = _format_events(candidate, window_title=window_title)
        raw = self.client.chat_vision(
            model=model,
            system=CAPTIONER_SYSTEM,
            user_text=user_text,
            images=[frame_before_img, frame_after_img],
            max_tokens=512,
            temperature=0.0,
        )
        try:
            obj = extract_json(raw)
        except ValueError as e:
            log.warning("captioner.bad_json", error=str(e), raw=raw[:200])
            return rule_based_step(candidate)

        try:
            type_raw = str(obj.get("type", "click"))
            action_type = ActionType(type_raw) if type_raw in ActionType._value2member_map_ else ActionType.CLICK
        except ValueError:
            action_type = ActionType.CLICK

        action = Action(
            type=action_type,
            target_description=str(obj.get("target_description") or "") or None,
            value=_collect_text(candidate),
        )
        return Step(
            index=0,  # index는 caller가 채움
            ts_start_ns=candidate.ts_start_ns,
            ts_end_ns=candidate.ts_end_ns,
            frame_before=candidate.frame_before_path,
            frame_after=candidate.frame_after_path,
            raw_event_ids=candidate.raw_event_ids,
            action=action,
            caption=str(obj.get("caption") or "")[:200],
            precondition=_s_or_none(obj.get("precondition")),
            postcondition=_s_or_none(obj.get("postcondition")),
            confidence=_to_confidence(obj.get("confidence")),
        )


# --- 룰 기반 fallback ---


def rule_based_step(candidate: CandidateStep) -> Step:
    """VLM 없이도 그럴듯한 Step을 만든다."""
    action_type = classify_events(candidate.events)
    text = _collect_text(candidate)
    caption = _describe(action_type, candidate.events, text)
    action = Action(
        type=action_type,
        target_description=None,
        value=text,
    )
    return Step(
        index=0,
        ts_start_ns=candidate.ts_start_ns,
        ts_end_ns=candidate.ts_end_ns,
        frame_before=candidate.frame_before_path,
        frame_after=candidate.frame_after_path,
        raw_event_ids=candidate.raw_event_ids,
        action=action,
        caption=caption,
        confidence=0.3,  # rule-based는 낮은 confidence
    )


def classify_events(events: list[RawEvent]) -> ActionType:
    """이벤트 시퀀스 → ActionType 추정."""
    kinds = [e.kind for e in events]
    if not kinds:
        return ActionType.WAIT

    # click pattern: down → up (같은 위치 근접)
    has_mouse_down = EventKind.MOUSE_DOWN in kinds
    has_mouse_up = EventKind.MOUSE_UP in kinds
    has_scroll = EventKind.SCROLL in kinds
    has_key_press = EventKind.KEY_DOWN in kinds or EventKind.TEXT_INPUT in kinds

    if has_scroll:
        return ActionType.SCROLL

    if has_mouse_down and has_mouse_up:
        # 2회 연속이면 double click
        down_count = sum(1 for k in kinds if k is EventKind.MOUSE_DOWN)
        if down_count >= 2:
            return ActionType.DOUBLE_CLICK
        # 클릭 포지션이 여러 곳이면 drag
        downs = [(e.x, e.y) for e in events if e.kind is EventKind.MOUSE_DOWN]
        ups = [(e.x, e.y) for e in events if e.kind is EventKind.MOUSE_UP]
        if downs and ups and downs[0] != ups[-1]:
            dx = abs((downs[0][0] or 0) - (ups[-1][0] or 0))
            dy = abs((downs[0][1] or 0) - (ups[-1][1] or 0))
            if dx > 20 or dy > 20:
                return ActionType.DRAG
        return ActionType.CLICK

    if has_key_press:
        # 단일 핫키(Ctrl+Something)는 HOTKEY, 다수 텍스트는 TYPE
        key_down_count = sum(1 for k in kinds if k is EventKind.KEY_DOWN)
        if key_down_count <= 3:
            return ActionType.HOTKEY
        return ActionType.TYPE

    return ActionType.WAIT


def _collect_text(candidate: CandidateStep) -> str | None:
    pieces = [e.text for e in candidate.events if e.text]
    if not pieces:
        return None
    return "".join(pieces)


def _describe(action_type: ActionType, events: list[RawEvent], text: str | None) -> str:
    last_mouse = next(
        (e for e in reversed(events) if e.kind in (EventKind.MOUSE_UP, EventKind.MOUSE_DOWN)),
        None,
    )
    if action_type is ActionType.CLICK and last_mouse is not None:
        return f"{last_mouse.button or 'left'} 클릭 @ ({last_mouse.x},{last_mouse.y})"
    if action_type is ActionType.DOUBLE_CLICK and last_mouse is not None:
        return f"더블 클릭 @ ({last_mouse.x},{last_mouse.y})"
    if action_type is ActionType.DRAG:
        return "드래그"
    if action_type is ActionType.SCROLL:
        return "스크롤"
    if action_type is ActionType.TYPE:
        snippet = (text or "")[:30]
        return f"입력: {snippet!r}"
    if action_type is ActionType.HOTKEY:
        vks = [str(e.vk) for e in events if e.vk is not None][:4]
        return "핫키: " + "+".join(vks)
    return "대기"


def _format_events(candidate: CandidateStep, *, window_title: str | None) -> str:
    lines = ["Events (monotonic ns):"]
    for e in candidate.events[:20]:
        parts = [f"  t={e.ts_ns}", e.kind.value]
        if e.x is not None:
            parts.append(f"({e.x},{e.y})")
        if e.button is not None:
            parts.append(f"btn={e.button}")
        if e.vk is not None:
            parts.append(f"vk={e.vk}")
        if e.text is not None:
            # PII가 이미 스크럽된 상태여야 함
            parts.append(f"text={e.text[:30]!r}")
        lines.append(" ".join(parts))
    if window_title:
        lines.append(f"Window: {window_title}")
    return "\n".join(lines)


def _s_or_none(v: object) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _to_confidence(v: object) -> float:
    if v is None:
        return 0.6
    try:
        f = float(v)
    except (TypeError, ValueError):
        return 0.6
    return max(0.0, min(1.0, f))


# --- 테스트 유틸 ---

_EMPTY_JSON_RE = re.compile(r"^\s*\{\s*\}\s*$")


def looks_empty_json(text: str) -> bool:
    return bool(_EMPTY_JSON_RE.match(text))


def dump_for_log(obj: object) -> str:
    return json.dumps(obj, ensure_ascii=False)
