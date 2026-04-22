from macrobania.safety import PIIScrubber, scrub_text
from macrobania.safety.pii import DEFAULT_RULES


def test_email_masked() -> None:
    assert scrub_text("연락: foo.bar+spam@example.com 끝") == "연락: <EMAIL> 끝"


def test_korean_rrn_masked() -> None:
    assert scrub_text("주민 900101-1234567") == "주민 <KRID>"


def test_credit_card_masked() -> None:
    out = scrub_text("카드: 4111 1111 1111 1111")
    assert out == "카드: <CARD>"


def test_phone_kr_masked() -> None:
    assert scrub_text("전화 010-1234-5678 / 02-1234-5678") == "전화 <PHONE> / <PHONE>"


def test_ipv4_masked() -> None:
    assert scrub_text("server 10.0.0.23") == "server <IP>"


def test_apikey_sk_masked() -> None:
    text = "key=sk-abcdefghijklmnopqrstuvwx"
    assert scrub_text(text) == "key=<APIKEY>"


def test_apikey_aws_masked() -> None:
    assert scrub_text("AKIAIOSFODNN7EXAMPLE left") == "<APIKEY> left"


def test_multiple_mixed() -> None:
    text = "user@x.com / 010-1111-2222 / sk-" + "a" * 20
    out = scrub_text(text)
    assert "@x.com" not in out
    assert "010-1111-2222" not in out
    assert "sk-" not in out
    assert out.count("<EMAIL>") == 1
    assert out.count("<PHONE>") == 1
    assert out.count("<APIKEY>") == 1


def test_matches_returns_rule_names() -> None:
    scrubber = PIIScrubber()
    matches = scrubber.matches("foo@bar.com and 10.0.0.1")
    names = {m[0] for m in matches}
    assert "email" in names
    assert "ipv4" in names


def test_default_rules_stable_count() -> None:
    assert len(DEFAULT_RULES) >= 6


def test_clean_text_untouched() -> None:
    assert scrub_text("Hello world 123") == "Hello world 123"
