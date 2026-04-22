"""안전·프라이버시 서브시스템.

- :mod:`macrobania.safety.pii`: 정규식 기반 개인정보 스크러버
- (추후) 프로세스 화이트리스트, kill switch, irreversible action 감지
"""
from macrobania.safety.pii import PIIScrubber, scrub_text

__all__ = ["PIIScrubber", "scrub_text"]
