from macrobania.agent.planner import parse_planner_response


def test_parse_click_action() -> None:
    r = parse_planner_response(
        '{"type":"click","target_description":"Login 버튼","rationale":"start login"}'
    )
    assert r.type == "click"
    assert r.target_description == "Login 버튼"
    assert "login" in r.rationale.lower()
    assert not r.is_terminal


def test_parse_done_terminal() -> None:
    r = parse_planner_response('{"type":"done","rationale":"goal achieved"}')
    assert r.is_terminal


def test_parse_unknown_type_becomes_done() -> None:
    r = parse_planner_response('{"type":"nuke"}')
    assert r.type == "done"


def test_parse_with_value() -> None:
    r = parse_planner_response('{"type":"type","value":"hello","rationale":"x"}')
    assert r.type == "type"
    assert r.value == "hello"


def test_parse_bad_json_returns_wait() -> None:
    r = parse_planner_response("no json here")
    assert r.type == "wait"


def test_parse_fenced_json() -> None:
    r = parse_planner_response(
        '```json\n{"type":"hotkey","value":"s","rationale":"save"}\n```'
    )
    assert r.type == "hotkey"
    assert r.value == "s"


def test_parse_null_target_ok() -> None:
    r = parse_planner_response('{"type":"wait","target_description":null,"rationale":"load"}')
    assert r.target_description is None


def test_parse_to_action_type_roundtrip() -> None:
    r = parse_planner_response('{"type":"click","target_description":"X"}')
    assert r.to_action_type().value == "click"
