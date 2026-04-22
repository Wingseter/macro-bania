"""Planner — 자연어 goal + 현재 스크린샷 + 최근 history → 다음 단일 action.

PLAN.md §13.4 ReAct 프롬프트 구현.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from PIL import Image

from macrobania.agent.client import VLMClient, extract_json
from macrobania.config import get_settings
from macrobania.logging import get_logger
from macrobania.models import ActionType

log = get_logger(__name__)


PLANNER_SYSTEM = (
    "You control a Windows desktop. Plan the NEXT SINGLE action toward the goal. "
    "Prefer terminating (done) when the goal is satisfied, or waiting if the UI "
    "is still loading.\n"
    "Action schema (JSON, no prose):\n"
    '{"type":"click"|"double_click"|"drag"|"type"|"hotkey"|"scroll"|"wait"|"done",'
    '"target_description":str|null, "value":str|null, "rationale":str}'
)


PlanActionType = Literal[
    "click", "double_click", "drag", "type", "hotkey", "scroll", "wait", "done"
]


@dataclass(frozen=True)
class PlannerDecision:
    type: PlanActionType
    target_description: str | None = None
    value: str | None = None
    rationale: str = ""

    @property
    def is_terminal(self) -> bool:
        return self.type == "done"

    def to_action_type(self) -> ActionType:
        return ActionType(self.type)


@dataclass
class Planner:
    client: VLMClient | None = None
    model: str | None = None
    max_history: int = 6

    @classmethod
    def from_env(cls) -> Planner:
        return cls(client=VLMClient.from_env())

    def plan(
        self,
        *,
        goal: str,
        screenshot: Image.Image,
        history: list[str] | None = None,
        few_shot_steps: list[str] | None = None,
    ) -> PlannerDecision:
        if self.client is None:
            # Mock mode: always done (safer failure mode)
            return PlannerDecision(type="done", rationale="no planner client")
        model = self.model or get_settings().vlm.planner_model
        user_text = _format_user(
            goal=goal,
            history=history or [],
            few_shot=few_shot_steps or [],
            max_history=self.max_history,
        )
        log.debug("planner.plan", model=model, goal=goal[:60], hist=len(history or []))
        raw = self.client.chat_vision(
            model=model,
            system=PLANNER_SYSTEM,
            user_text=user_text,
            images=[screenshot],
            max_tokens=512,
            temperature=0.0,
        )
        return parse_planner_response(raw)


def _format_user(*, goal: str, history: list[str], few_shot: list[str], max_history: int) -> str:
    lines: list[str] = [f"Goal: {goal}"]
    if few_shot:
        lines.append("Similar past steps (RAG):")
        for ex in few_shot[:5]:
            lines.append(f"  - {ex}")
    if history:
        lines.append("Recent history:")
        for h in history[-max_history:]:
            lines.append(f"  - {h}")
    return "\n".join(lines)


_VALID_TYPES = {"click", "double_click", "drag", "type", "hotkey", "scroll", "wait", "done"}


def parse_planner_response(text: str) -> PlannerDecision:
    try:
        obj = extract_json(text)
    except ValueError as e:
        log.warning("planner.bad_json", error=str(e), raw=text[:200])
        return PlannerDecision(type="wait", rationale="parse fail; wait then re-plan")

    raw_type = str(obj.get("type", "done")).strip().lower()
    if raw_type not in _VALID_TYPES:
        raw_type = "done"

    target = obj.get("target_description")
    value = obj.get("value")
    rationale = str(obj.get("rationale") or "")[:300]

    return PlannerDecision(
        type=raw_type,  # type: ignore[arg-type]
        target_description=str(target) if target not in (None, "") else None,
        value=str(value) if value not in (None, "") else None,
        rationale=rationale,
    )
