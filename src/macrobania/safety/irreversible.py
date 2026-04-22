"""Irreversible action 감지.

결제/송금/계정 변경/파일 삭제 같은 되돌릴 수 없는 액션의 힌트 문자열을
찾아내어 human confirm 게이트를 트리거한다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_DEFAULT_PATTERNS = (
    # 한국어
    r"결제",
    r"송금",
    r"이체",
    r"삭제",
    r"제거",
    r"탈퇴",
    r"영구\s*삭제",
    r"계정\s*삭제",
    r"비밀번호\s*변경",
    # 영어
    r"\bpay\b",
    r"\bpurchase\b",
    r"\btransfer\b",
    r"\bdelete\b",
    r"\bremove\b",
    r"\bconfirm\s+(order|purchase|payment|transfer)\b",
    r"\bunsubscribe\b",
    r"\bdrop\s+table\b",
    r"\bformat\s+drive\b",
)


@dataclass
class IrreversibleMatcher:
    """정규식 기반 irreversible action 감지기."""

    patterns: tuple[str, ...] = _DEFAULT_PATTERNS

    def _compiled(self) -> list[re.Pattern[str]]:
        return [re.compile(p, re.IGNORECASE) for p in self.patterns]

    def matches(self, text: str) -> list[str]:
        """매치된 패턴 문자열 목록."""
        if not text:
            return []
        out: list[str] = []
        for pat in self._compiled():
            m = pat.search(text)
            if m:
                out.append(m.group(0))
        return out

    def is_irreversible(self, *texts: str | None) -> bool:
        return any(bool(t) and bool(self.matches(t)) for t in texts)


_default = IrreversibleMatcher()


def is_irreversible(*texts: str | None) -> bool:
    """기본 매처로 확인."""
    return _default.is_irreversible(*texts)


def detect_matches(text: str) -> list[str]:
    return _default.matches(text)
