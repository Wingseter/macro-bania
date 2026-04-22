import pytest

from macrobania.agent.client import extract_json
from macrobania.agent.grounder import parse_grounder_response


def test_extract_json_fenced() -> None:
    resp = 'Sure!\n```json\n{"bbox":[1,2,3,4]}\n```\nDone.'
    assert extract_json(resp) == {"bbox": [1, 2, 3, 4]}


def test_extract_json_bare() -> None:
    resp = 'Answer: {"bbox":[10,10,50,50],"confidence":0.8}'
    assert extract_json(resp)["confidence"] == 0.8


def test_extract_json_missing_raises() -> None:
    with pytest.raises(ValueError):
        extract_json("no braces here")


def test_grounder_parse_array_bbox() -> None:
    result = parse_grounder_response(
        '{"bbox":[100,200,300,400],"candidate_id":1,"confidence":0.95,"reason":"ok"}'
    )
    assert (result.bbox.x1, result.bbox.y1, result.bbox.x2, result.bbox.y2) == (
        100,
        200,
        300,
        400,
    )
    assert result.candidate_id == 1
    assert result.confidence == pytest.approx(0.95)
    assert result.reason == "ok"


def test_grounder_parse_dict_bbox() -> None:
    result = parse_grounder_response(
        '```json\n{"bbox":{"x1":50,"y1":60,"x2":70,"y2":80},"confidence":0.5}\n```'
    )
    assert result.bbox.x1 == 50
    assert result.bbox.x2 == 70


def test_grounder_clamps_out_of_range() -> None:
    # 입력:  x=[-5, 500], y=[2000, 200]
    # 1) clamp to 0..1000 → x=[0, 500], y=[1000, 200]
    # 2) y swap (200 < 1000) → y=[200, 1000]
    result = parse_grounder_response(
        '{"bbox":[-5, 2000, 500, 200],"confidence":1.0}'
    )
    assert result.bbox.x1 == 0
    assert result.bbox.x2 == 500
    assert result.bbox.y1 == 200
    assert result.bbox.y2 == 1000


def test_grounder_clamps_upper_bound() -> None:
    result = parse_grounder_response('{"bbox":[5000, 10, 6000, 20]}')
    assert result.bbox.x1 == 1000
    assert result.bbox.x2 == 1000


def test_grounder_handles_float_coords() -> None:
    result = parse_grounder_response('{"bbox":[12.4,12.6,100.1,200.9]}')
    assert result.bbox.x1 == 12
    assert result.bbox.y1 == 13
    assert result.bbox.x2 == 100
    assert result.bbox.y2 == 201


def test_grounder_missing_bbox_raises() -> None:
    with pytest.raises(ValueError):
        parse_grounder_response('{"confidence":0.5}')


def test_grounder_invalid_confidence_defaults() -> None:
    result = parse_grounder_response(
        '{"bbox":[0,0,10,10],"confidence":"nope"}'
    )
    assert result.confidence == 0.0


def test_grounder_candidate_id_null() -> None:
    result = parse_grounder_response(
        '{"bbox":[0,0,10,10],"candidate_id":null}'
    )
    assert result.candidate_id is None
