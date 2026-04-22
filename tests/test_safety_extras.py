import pytest

from macrobania.safety import (
    IrreversibleMatcher,
    ProcessAllowlist,
    ProcessNotAllowedError,
    detect_matches,
    is_irreversible,
)

# --- process allowlist ---


def test_allowlist_allows_exact() -> None:
    al = ProcessAllowlist(names=["chrome.exe"])
    assert al.is_allowed("chrome.exe")


def test_allowlist_case_insensitive() -> None:
    al = ProcessAllowlist(names=["Chrome.EXE"])
    assert al.is_allowed("chrome.exe")


def test_allowlist_rejects() -> None:
    al = ProcessAllowlist(names=["chrome.exe"])
    assert not al.is_allowed("notepad.exe")


def test_allowlist_disabled_always_ok() -> None:
    al = ProcessAllowlist(names=["chrome.exe"], enabled=False)
    assert al.is_allowed("notepad.exe")


def test_allowlist_check_raises() -> None:
    al = ProcessAllowlist(names=["chrome.exe"])
    with pytest.raises(ProcessNotAllowedError):
        al.check("rogue.exe")


# --- irreversible ---


def test_irreversible_korean() -> None:
    assert is_irreversible("결제 확인")
    assert is_irreversible("계정 삭제하기")


def test_irreversible_english() -> None:
    assert is_irreversible("Confirm purchase now")
    assert is_irreversible("delete this user")


def test_irreversible_clean_text() -> None:
    assert not is_irreversible("hello world")


def test_irreversible_detect_matches_returns_strings() -> None:
    matches = detect_matches("결제하고 transfer")
    assert any("결제" in m for m in matches)
    assert any("transfer" in m.lower() for m in matches)


def test_irreversible_is_none_arg() -> None:
    assert not is_irreversible(None, None)


def test_irreversible_custom_patterns() -> None:
    m = IrreversibleMatcher(patterns=(r"nuke\b",))
    assert m.matches("launch nuke now")
    assert not m.matches("payment")
