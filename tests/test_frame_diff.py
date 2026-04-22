from PIL import Image

from macrobania.capture.frame_diff import frame_diff_ratio, significantly_changed


def _solid(w: int, h: int, color: tuple[int, int, int]) -> Image.Image:
    return Image.new("RGB", (w, h), color)


def test_identical_images_diff_zero() -> None:
    a = _solid(100, 100, (123, 0, 0))
    b = _solid(100, 100, (123, 0, 0))
    assert frame_diff_ratio(a, b) == 0.0


def test_completely_different_diff_one() -> None:
    a = _solid(40, 40, (0, 0, 0))
    b = _solid(40, 40, (255, 255, 255))
    assert frame_diff_ratio(a, b) == 1.0


def test_partial_diff_ratio() -> None:
    a = _solid(100, 100, (0, 0, 0))
    b = a.copy()
    # 왼쪽 절반만 흰색
    for x in range(50):
        for y in range(100):
            b.putpixel((x, y), (255, 255, 255))
    ratio = frame_diff_ratio(a, b)
    assert 0.49 <= ratio <= 0.51


def test_significantly_changed_true() -> None:
    a = _solid(50, 50, (0, 0, 0))
    b = _solid(50, 50, (255, 255, 255))
    assert significantly_changed(a, b, min_ratio=0.5)


def test_significantly_changed_false_small_noise() -> None:
    a = _solid(80, 80, (10, 10, 10))
    b = a.copy()
    for x in range(2):
        for y in range(80):
            b.putpixel((x, y), (255, 255, 255))
    # ≈ 2.5% 변경. threshold=0.02 → True. threshold=0.05 → False
    assert significantly_changed(a, b, min_ratio=0.02)
    assert not significantly_changed(a, b, min_ratio=0.05)


def test_different_sizes_resize() -> None:
    a = _solid(100, 100, (30, 30, 30))
    b = _solid(50, 50, (30, 30, 30))
    assert frame_diff_ratio(a, b) == 0.0
