from macrobania.agent.prompts import (
    GROUNDER_SYSTEM,
    GrounderCandidate,
    format_grounder_user,
    format_verifier_user,
)


def test_grounder_system_has_json_contract() -> None:
    assert '"bbox"' in GROUNDER_SYSTEM
    assert "0-1000" in GROUNDER_SYSTEM or "0~1000" in GROUNDER_SYSTEM


def test_grounder_user_minimal() -> None:
    out = format_grounder_user(
        target_description="로그인 버튼",
        hint_bbox_pixel=None,
        hint_resolution=None,
        current_resolution=(1920, 1080),
    )
    assert "로그인 버튼" in out
    assert "1920x1080" in out
    assert "Hint" not in out
    assert "Candidates" not in out


def test_grounder_user_with_hint_and_candidates() -> None:
    cands = [
        GrounderCandidate(id=0, source="uia", label="Login", bbox_pixel=(92, 210, 132, 248)),
        GrounderCandidate(id=1, source="ocr", label="로그인", bbox_pixel=(96, 215, 128, 232)),
    ]
    out = format_grounder_user(
        target_description="로그인",
        hint_bbox_pixel=(124, 280, 176, 332),
        hint_resolution=(2560, 1440),
        current_resolution=(1920, 1080),
        candidates=cands,
    )
    assert "Hint" in out
    assert "[124, 280, 176, 332]" in out
    assert "Candidates:" in out
    assert "#0" in out and "UIA" in out
    assert "#1" in out and "OCR" in out


def test_verifier_user_format() -> None:
    assert format_verifier_user("로딩 완료?") == "Question: 로딩 완료?"
