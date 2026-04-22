"""VLM 에이전트 레이어.

역할별 분리:
  - :mod:`client`     — OpenAI 호환 엔드포인트 얇은 래퍼
  - :mod:`grounder`   — 스크린샷 + 타깃 서술 → bbox
  - :mod:`captioner`  — 이벤트 + 프레임 → semantic Step (Phase 2)
  - (Phase 3+) verifier / planner
"""
from macrobania.agent.captioner import CandidateStep, Captioner, rule_based_step
from macrobania.agent.client import VLMClient
from macrobania.agent.grounder import Grounder

__all__ = [
    "CandidateStep",
    "Captioner",
    "Grounder",
    "VLMClient",
    "rule_based_step",
]
