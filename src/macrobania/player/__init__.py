"""재생 서브시스템.

모드:
  - :mod:`mode_a_faithful`   — 원본 타임스탬프 재생 + precondition 체크 (Phase 3)
  - :mod:`mode_b_grounded`   — ★ V1 핵심, Hybrid Perception (Phase 4)
  - :mod:`mode_c_autonomous` — Planner ReAct (Phase 6)
"""
from __future__ import annotations

from macrobania.player.base import PlayResult, PlaySession, StepOutcome
from macrobania.player.mode_a_faithful import FaithfulPlayer

__all__ = [
    "FaithfulPlayer",
    "PlayResult",
    "PlaySession",
    "StepOutcome",
]
