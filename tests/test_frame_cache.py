from PIL import Image

from macrobania.models import NormBBox
from macrobania.player.frame_cache import GroundingCache


def _solid(color: tuple[int, int, int]) -> Image.Image:
    return Image.new("RGB", (60, 60), color)


def test_cache_hit_same_image() -> None:
    cache = GroundingCache()
    img = _solid((10, 10, 10))
    bbox = NormBBox(x1=100, y1=200, x2=300, y2=400)
    cache.insert("Login", img, bbox)
    assert cache.lookup("Login", img) == bbox


def test_cache_miss_different_target() -> None:
    cache = GroundingCache()
    cache.insert("Login", _solid((0, 0, 0)), NormBBox(x1=0, y1=0, x2=10, y2=10))
    assert cache.lookup("Logout", _solid((0, 0, 0))) is None


def test_cache_miss_stale_image() -> None:
    cache = GroundingCache(stale_threshold=0.01)
    cache.insert("Login", _solid((0, 0, 0)), NormBBox(x1=0, y1=0, x2=10, y2=10))
    # 전부 변화 → diff ~1.0
    other = _solid((255, 255, 255))
    assert cache.lookup("Login", other) is None


def test_cache_lru_eviction() -> None:
    cache = GroundingCache(max_entries=2)
    cache.insert("a", _solid((0, 0, 0)), NormBBox(x1=0, y1=0, x2=1, y2=1))
    cache.insert("b", _solid((1, 1, 1)), NormBBox(x1=0, y1=0, x2=2, y2=2))
    cache.insert("c", _solid((2, 2, 2)), NormBBox(x1=0, y1=0, x2=3, y2=3))
    # "a" 증발
    assert cache.lookup("a", _solid((0, 0, 0))) is None
    assert cache.lookup("b", _solid((1, 1, 1))) is not None


def test_cache_clear() -> None:
    cache = GroundingCache()
    cache.insert("x", _solid((0, 0, 0)), NormBBox(x1=0, y1=0, x2=1, y2=1))
    cache.clear()
    assert cache.lookup("x", _solid((0, 0, 0))) is None
