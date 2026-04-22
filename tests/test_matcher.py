from macrobania.perception.matcher import (
    MatcherConfig,
    find_candidates,
)
from macrobania.perception.ocr import OCRBlock
from macrobania.perception.uia import UIAControl, UIASnapshot


def _mk_uia(controls: list[tuple[str, str, tuple[int, int, int, int]]]) -> UIASnapshot:
    children = [
        UIAControl(role=role, name=name, bbox=bbox) for role, name, bbox in controls
    ]
    root = UIAControl(role="Window", name="root", bbox=(0, 0, 1000, 1000), children=children)
    return UIASnapshot(hwnd=1, window_title="w", root=root)


def test_matcher_returns_exact_uia_match() -> None:
    uia = _mk_uia([
        ("Button", "Login", (100, 100, 200, 140)),
        ("Button", "Cancel", (300, 100, 400, 140)),
    ])
    result = find_candidates("Login", uia=uia)
    assert result.scored
    best = result.scored[0]
    assert best.candidate.label == "Login"
    assert best.score >= 0.9


def test_matcher_unambiguous_skip_vlm() -> None:
    uia = _mk_uia([
        ("Button", "Save", (100, 100, 200, 140)),
        ("Button", "Cancel", (300, 100, 400, 140)),
    ])
    cfg = MatcherConfig()
    result = find_candidates("Save", uia=uia, cfg=cfg)
    unambig = result.unambiguous(cfg)
    assert unambig is not None
    assert unambig.candidate.label == "Save"


def test_matcher_ambiguous_two_similar() -> None:
    uia = _mk_uia([
        ("Button", "Open", (100, 100, 200, 140)),
        ("Button", "Open File", (300, 100, 400, 140)),
    ])
    result = find_candidates("Open", uia=uia)
    # 정확 일치 하나만 있고 다른 하나는 contains이므로 1등-2등 차이 충분 → unambiguous
    unambig = result.unambiguous(MatcherConfig())
    assert unambig is not None
    assert unambig.candidate.label == "Open"


def test_matcher_with_ocr() -> None:
    ocr = [
        OCRBlock(text="로그인", bbox=(10, 10, 90, 40), confidence=0.9),
        OCRBlock(text="회원가입", bbox=(100, 10, 180, 40), confidence=0.9),
    ]
    result = find_candidates("로그인", ocr=ocr)
    assert result.scored
    assert result.scored[0].candidate.label == "로그인"
    assert result.scored[0].candidate.source == "ocr"


def test_matcher_hint_bbox_boost() -> None:
    uia = _mk_uia([
        ("Button", "Submit", (10, 10, 100, 50)),
        ("Button", "Submit", (500, 500, 600, 540)),
    ])
    # hint가 두 번째 위치 근처면 두 번째가 이김
    result = find_candidates(
        "Submit",
        uia=uia,
        hint_bbox_pixel=(495, 498, 605, 545),
    )
    assert result.scored[0].candidate.bbox_pixel == (500, 500, 600, 540)


def test_matcher_token_based_match() -> None:
    uia = _mk_uia([
        ("Button", "Daily Quest Tab", (10, 10, 100, 50)),
    ])
    result = find_candidates("daily quest", uia=uia)
    assert result.scored
    assert result.scored[0].score > 0.4


def test_matcher_no_match_empty() -> None:
    uia = _mk_uia([("Button", "XYZ", (0, 0, 10, 10))])
    result = find_candidates("nonexistent", uia=uia)
    assert result.scored == []


def test_matcher_max_candidates() -> None:
    uia = _mk_uia([
        ("Button", f"thing {i}", (i * 10, 0, i * 10 + 5, 5))
        for i in range(30)
    ])
    cfg = MatcherConfig(max_candidates=5)
    result = find_candidates("thing", uia=uia, cfg=cfg)
    assert len(result.scored) == 5


def test_matcher_normalizes_quotes_and_parens() -> None:
    uia = _mk_uia([("Tab", "일일 퀘스트", (0, 0, 100, 40))])
    # 설명에 따옴표/괄호가 있어도 매치 가능
    result = find_candidates("'일일 퀘스트' 탭 (사이드바)", uia=uia)
    assert result.scored
    # partial match이므로 점수는 낮아도 0보다 큼
    assert result.scored[0].score > 0
