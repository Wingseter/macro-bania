"""MSS 캡처 백엔드 기본 동작 검증.

CI에서 가상 디스플레이가 없더라도 MSS는 일반적으로 첫 프레임 정도는 반환 가능.
실패 시 skip.
"""
from __future__ import annotations

import pytest

from macrobania.capture import MSSBackend


@pytest.fixture
def mss_backend() -> MSSBackend:
    try:
        return MSSBackend()
    except Exception as e:
        pytest.skip(f"mss unavailable: {e}")


def test_grab_returns_frame(mss_backend: MSSBackend) -> None:
    try:
        frame = mss_backend.grab(monitor=0)
    except Exception as e:
        pytest.skip(f"screen grab failed in this env: {e}")
    assert frame.image.size[0] > 0
    assert frame.image.size[1] > 0
    assert frame.ts_ns > 0
    mss_backend.close()


def test_backend_name() -> None:
    try:
        b = MSSBackend()
    except Exception as e:
        pytest.skip(f"mss unavailable: {e}")
    assert b.name == "mss"
    b.close()
