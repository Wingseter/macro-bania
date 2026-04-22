"""프레임 diff 기반 Grounder 캐시 (Gemini 픽셀 diff 최적화).

직전 스크린샷 대비 변화가 작고 동일 target을 다시 찾으면 이전 좌표를 재사용.
"""
from __future__ import annotations

from dataclasses import dataclass

from PIL import Image

from macrobania.capture.frame_diff import frame_diff_ratio
from macrobania.logging import get_logger
from macrobania.models import NormBBox

log = get_logger(__name__)


@dataclass
class _CacheEntry:
    target: str
    image: Image.Image
    bbox: NormBBox


@dataclass
class GroundingCache:
    """LRU 느낌의 작은 캐시 (기본 크기 16). 실용 단계에선 충분.

    lookup 기준:
      - target 서술 문자열 동일
      - 마지막 이미지와 pixel diff ≤ ``stale_threshold``
    """

    max_entries: int = 16
    stale_threshold: float = 0.02
    entries: list[_CacheEntry] | None = None

    def __post_init__(self) -> None:
        if self.entries is None:
            self.entries = []

    def lookup(self, target: str, image: Image.Image) -> NormBBox | None:
        assert self.entries is not None
        for entry in reversed(self.entries):
            if entry.target != target:
                continue
            try:
                diff = frame_diff_ratio(entry.image, image)
            except Exception:
                continue
            if diff <= self.stale_threshold:
                log.debug("grounding_cache.hit", target=target[:40], diff=diff)
                return entry.bbox
        return None

    def insert(self, target: str, image: Image.Image, bbox: NormBBox) -> None:
        assert self.entries is not None
        self.entries.append(_CacheEntry(target=target, image=image.copy(), bbox=bbox))
        if len(self.entries) > self.max_entries:
            # 가장 오래된 것부터 제거
            self.entries = self.entries[-self.max_entries :]

    def clear(self) -> None:
        assert self.entries is not None
        self.entries.clear()
