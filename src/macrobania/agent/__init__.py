"""VLM 에이전트 레이어.

역할별 분리:
  - :mod:`client` — OpenAI 호환 엔드포인트 얇은 래퍼
  - :mod:`grounder` — 스크린샷 + 타깃 서술 → bbox
  - (Phase 2+) captioner / verifier / planner
"""
from macrobania.agent.client import VLMClient
from macrobania.agent.grounder import Grounder

__all__ = ["Grounder", "VLMClient"]
