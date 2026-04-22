"""재생 서브시스템.

모드:
  - :mod:`mode_a_faithful`   — 원본 타임스탬프 재생 + precondition 체크
  - :mod:`mode_b_grounded`   — ★ V1 핵심, Hybrid Perception + Grounder
  - :mod:`mode_c_autonomous` — Planner ReAct (Phase 6)
"""
from __future__ import annotations

from macrobania.player.base import PlayResult, PlaySession, StepOutcome
from macrobania.player.frame_cache import GroundingCache
from macrobania.player.mode_a_faithful import FaithfulPlayer
from macrobania.player.mode_b_grounded import GroundedPlayer

__all__ = [
    "FaithfulPlayer",
    "GroundedPlayer",
    "GroundingCache",
    "PlayResult",
    "PlaySession",
    "StepOutcome",
]
