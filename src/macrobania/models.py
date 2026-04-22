"""Pydantic 데이터 모델.

PLAN.md §10 스키마의 파이썬 표현.
좌표 규약:
  - ``PixelBBox``: 절대 픽셀 좌표 (스크린샷 원본 해상도 기준)
  - ``NormBBox``: 0~1000 정규화 (Qwen3-VL 공식 출력 포맷)
"""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

# --- 좌표 ---


class PixelBBox(BaseModel):
    """x1,y1,x2,y2 픽셀 좌표. x2>x1, y2>y1 보장."""

    model_config = ConfigDict(frozen=True)

    x1: int
    y1: int
    x2: int
    y2: int

    @property
    def width(self) -> int:
        return self.x2 - self.x1

    @property
    def height(self) -> int:
        return self.y2 - self.y1

    @property
    def center(self) -> tuple[int, int]:
        return ((self.x1 + self.x2) // 2, (self.y1 + self.y2) // 2)

    @classmethod
    def from_norm(cls, norm: NormBBox, width: int, height: int) -> PixelBBox:
        return cls(
            x1=int(norm.x1 * width / 1000),
            y1=int(norm.y1 * height / 1000),
            x2=int(norm.x2 * width / 1000),
            y2=int(norm.y2 * height / 1000),
        )


class NormBBox(BaseModel):
    """0~1000 정규화 bbox (Qwen3-VL grounding 출력 포맷)."""

    model_config = ConfigDict(frozen=True)

    x1: int = Field(ge=0, le=1000)
    y1: int = Field(ge=0, le=1000)
    x2: int = Field(ge=0, le=1000)
    y2: int = Field(ge=0, le=1000)


# --- 이벤트 ---


class EventKind(StrEnum):
    MOUSE_DOWN = "mouse_down"
    MOUSE_UP = "mouse_up"
    MOUSE_MOVE = "mouse_move"
    KEY_DOWN = "key_down"
    KEY_UP = "key_up"
    SCROLL = "scroll"
    TEXT_INPUT = "text_input"


class RawEvent(BaseModel):
    """저수준 입력 이벤트."""

    ts_ns: int
    kind: EventKind
    # mouse
    x: int | None = None
    y: int | None = None
    button: Literal["left", "right", "middle"] | None = None
    # keyboard
    vk: int | None = None
    scan: int | None = None
    extended: int | None = None
    text: str | None = None
    # scroll
    dx: int | None = None
    dy: int | None = None
    # window context
    window_hwnd: str | None = None
    window_title: str | None = None


# --- 액션 ---


class ActionType(StrEnum):
    CLICK = "click"
    DOUBLE_CLICK = "double_click"
    DRAG = "drag"
    TYPE = "type"
    HOTKEY = "hotkey"
    SCROLL = "scroll"
    WAIT = "wait"
    FOCUS_WINDOW = "focus_window"
    DONE = "done"


class Action(BaseModel):
    """Semantic action."""

    type: ActionType
    target_description: str | None = None
    target_bbox_hint: PixelBBox | None = None
    target_crop_path: Path | None = None
    target_uia_path: str | None = None
    target_ocr_text: str | None = None
    to_bbox: PixelBBox | None = None
    value: str | None = None
    modifiers: list[str] = Field(default_factory=list)
    wait_ms: int | None = None
    wait_until: str | None = None  # VLM 조건문


# --- Step ---


class Step(BaseModel):
    """Semantic step (VLM 후처리 산출물)."""

    index: int
    ts_start_ns: int
    ts_end_ns: int
    frame_before: str | None = None
    frame_after: str | None = None
    raw_event_ids: list[int] = Field(default_factory=list)
    action: Action
    caption: str = ""
    precondition: str | None = None
    postcondition: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


# --- Recording ---


class Platform(BaseModel):
    os: str
    resolution: tuple[int, int]
    dpi_scale: float = 1.0
    primary_monitor: int = 0


class Recording(BaseModel):
    """녹화 최상위."""

    id: Annotated[str, Field(pattern=r"^rec_[\w:-]+$")]
    task_name: str
    description: str = ""
    created_at: datetime
    platform: Platform
    target_process: str | None = None
    target_window_title_regex: str | None = None
    frame_count: int = 0
    event_count: int = 0
    duration_ms: int = 0
    step_count: int = 0
    state_graph_id: str | None = None


# --- Grounder 응답 ---


class GrounderResult(BaseModel):
    """Grounder VLM 응답 파싱 결과."""

    bbox: NormBBox
    candidate_id: int | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reason: str = ""


class VerifierResult(BaseModel):
    """Verifier VLM 응답."""

    answer: Literal["yes", "no"]
    reason: str = ""
