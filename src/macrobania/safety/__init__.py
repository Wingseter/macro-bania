"""안전·프라이버시 서브시스템.

- :mod:`pii`               : 정규식 기반 개인정보 스크러버
- :mod:`process_allowlist` : 활성 창 프로세스 화이트리스트
- :mod:`killswitch`        : 전역 hotkey (pynput GlobalHotKeys)
- :mod:`irreversible`      : 되돌릴 수 없는 액션 감지
"""
from macrobania.safety.irreversible import (
    IrreversibleMatcher,
    detect_matches,
    is_irreversible,
)
from macrobania.safety.killswitch import KillSwitch
from macrobania.safety.pii import PIIScrubber, scrub_text
from macrobania.safety.process_allowlist import (
    ProcessAllowlist,
    ProcessNotAllowedError,
    active_window_process,
)

__all__ = [
    "IrreversibleMatcher",
    "KillSwitch",
    "PIIScrubber",
    "ProcessAllowlist",
    "ProcessNotAllowedError",
    "active_window_process",
    "detect_matches",
    "is_irreversible",
    "scrub_text",
]
