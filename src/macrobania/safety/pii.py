"""PII(개인식별정보) 마스킹.

V1은 정규식 기반 경량 스크러버. Phase 5에서 presidio-analyzer 선택 통합.

마스킹 규칙:
  - 이메일 → ``<EMAIL>``
  - 신용카드 번호(13~19자리, 간단히) → ``<CARD>``
  - 한국 주민등록번호(YYMMDD-NNNNNNN) → ``<KRID>``
  - 전화번호(한국/국제 간단 패턴) → ``<PHONE>``
  - IPv4 주소 → ``<IP>``
  - API 키 비슷한 문자열 (sk-/AKIA 등 prefix) → ``<APIKEY>``

false-positive를 감안해 **녹화 저장 직전** 한 번만 적용하는 것을 권장.
"""
from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from re import Pattern


@dataclass(frozen=True)
class Rule:
    name: str
    pattern: Pattern[str]
    replacement: str


DEFAULT_RULES: tuple[Rule, ...] = (
    Rule(
        name="email",
        pattern=re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),
        replacement="<EMAIL>",
    ),
    Rule(
        name="kr_rrn",
        pattern=re.compile(r"\b\d{6}-\d{7}\b"),
        replacement="<KRID>",
    ),
    # card: 13-19자리 숫자 (공백/하이픈 포함). 단순화된 룰.
    Rule(
        name="card",
        pattern=re.compile(r"\b(?:\d[ -]?){13,19}\b"),
        replacement="<CARD>",
    ),
    Rule(
        name="phone_kr",
        pattern=re.compile(r"\b0\d{1,2}-\d{3,4}-\d{4}\b"),
        replacement="<PHONE>",
    ),
    Rule(
        name="phone_intl",
        pattern=re.compile(r"\+\d{1,3}[-.\s]?\d{1,4}[-.\s]?\d{3,4}[-.\s]?\d{3,4}"),
        replacement="<PHONE>",
    ),
    Rule(
        name="ipv4",
        pattern=re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
        replacement="<IP>",
    ),
    Rule(
        name="apikey",
        pattern=re.compile(
            r"\b(?:sk-[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{20,})\b"
        ),
        replacement="<APIKEY>",
    ),
)


@dataclass
class PIIScrubber:
    """정규식 기반 스크러버.

    추가 룰을 주입하거나 기본 규칙을 비활성화할 수 있다.
    """

    rules: tuple[Rule, ...] = field(default=DEFAULT_RULES)

    def scrub(self, text: str) -> str:
        result = text
        for rule in self.rules:
            result = rule.pattern.sub(rule.replacement, result)
        return result

    def matches(self, text: str) -> list[tuple[str, str]]:
        """매칭된 ``(rule_name, matched_text)`` 목록. 테스트/디버깅용."""
        found: list[tuple[str, str]] = []
        for rule in self.rules:
            for m in rule.pattern.finditer(text):
                found.append((rule.name, m.group(0)))
        return found

    @classmethod
    def with_extra(cls, extra: Iterable[Rule]) -> PIIScrubber:
        return cls(rules=DEFAULT_RULES + tuple(extra))


_default = PIIScrubber()


def scrub_text(text: str) -> str:
    """기본 규칙으로 스크럽."""
    return _default.scrub(text)
