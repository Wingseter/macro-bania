from macrobania.agent.verifier import parse_verifier_response


def test_parse_yes() -> None:
    r = parse_verifier_response('{"answer":"yes","reason":"form visible"}')
    assert r.answer == "yes"
    assert "form" in r.reason


def test_parse_no() -> None:
    r = parse_verifier_response('{"answer":"no","reason":"spinner still"}')
    assert r.answer == "no"


def test_parse_fenced() -> None:
    r = parse_verifier_response('```json\n{"answer":"YES","reason":""}\n```')
    assert r.answer == "yes"


def test_parse_abbrev_yes_fallback() -> None:
    r = parse_verifier_response("Y, looks good")
    assert r.answer == "yes"


def test_parse_abbrev_no_fallback() -> None:
    r = parse_verifier_response("no it did not")
    assert r.answer == "no"


def test_parse_unparseable_defaults_no() -> None:
    r = parse_verifier_response("weird output")
    assert r.answer == "no"


def test_parse_invalid_answer_defaults_no() -> None:
    r = parse_verifier_response('{"answer":"maybe"}')
    assert r.answer == "no"
