"""Verifier — 스크린샷 + 질문 → yes/no + 근거."""
from __future__ import annotations

import re
from dataclasses import dataclass

from PIL import Image

from macrobania.agent.client import VLMClient, extract_json
from macrobania.agent.prompts import VERIFIER_SYSTEM, format_verifier_user
from macrobania.config import get_settings
from macrobania.logging import get_logger
from macrobania.models import VerifierResult

log = get_logger(__name__)

_YES_RE = re.compile(r"^(?:yes|true|ok|y\b)", re.IGNORECASE)


@dataclass
class Verifier:
    client: VLMClient | None = None
    model: str | None = None

    @classmethod
    def from_env(cls) -> Verifier:
        return cls(client=VLMClient.from_env())

    def yesno(self, screenshot: Image.Image, question: str) -> VerifierResult:
        if self.client is None:
            # Mock mode — always yes with low trust
            return VerifierResult(answer="yes", reason="no-vlm: default yes")
        model = self.model or get_settings().vlm.verifier_model
        raw = self.client.chat_vision(
            model=model,
            system=VERIFIER_SYSTEM,
            user_text=format_verifier_user(question),
            images=[screenshot],
            max_tokens=128,
            temperature=0.0,
        )
        return parse_verifier_response(raw)


def parse_verifier_response(text: str) -> VerifierResult:
    try:
        obj = extract_json(text)
    except ValueError:
        # Fallback: raw yes/no 문자열 스캔
        low = text.strip().lower()
        if _YES_RE.match(low):
            return VerifierResult(answer="yes", reason=text[:80])
        if low.startswith(("no", "false", "n ", "n,", "n.")):
            return VerifierResult(answer="no", reason=text[:80])
        return VerifierResult(answer="no", reason=f"parse fail: {text[:80]}")

    answer = str(obj.get("answer", "")).strip().lower()
    if answer not in ("yes", "no"):
        answer = "yes" if _YES_RE.match(answer) else "no"
    return VerifierResult(answer=answer, reason=str(obj.get("reason") or "")[:200])
