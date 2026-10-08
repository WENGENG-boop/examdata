"""A12 legacy payload builders (plan 5.5): pure translation contracts.

These tests pin the documented legacy payload shapes and the invariants the
builders must never break: page echo, recomputed counts, preserved absence,
untouched quality tokens, and verbatim 422 details. Nothing here imports an
original module; everything is a pure function over synthetic values.
"""
from __future__ import annotations

import pytest

from examdata_integration.legacy import translate as tr


# -- pages --------------------------------------------------------------------

def test_page_echoes_limit_offset_and_copies_items():
    source = [{"id": 1}, {"id": 2}]
    payload = tr.legacy_page(source, total=5, limit=50, offset=10)
    assert payload == {"total": 5, "limit": 50, "offset": 10, "items": [{"id": 1}, {"id": 2}]}
    source[0]["id"] = 999
    assert payload["items"][0]["id"] == 1, "items must be deep copies"


def test_page_rejects_non_int():
    with pytest.raises(TypeError):
        tr.legacy_page([], total="5", limit=1, offset=0)
    with pytest.raises(TypeError):
        tr.legacy_page([], total=5, limit=True, offset=0)


def test_search_page_carries_by_board_and_board():
    payload = tr.legacy_search_page([{"q": 1}], total=1, limit=20, offset=0,
                                    board="cie", by_board={"cie": [1]},
                                    board_source="explicit")
    assert set(payload) == {"total", "limit", "offset", "by_board", "items",
                            "board", "board_source"}
    assert payload["board"] == "cie"
    assert payload["by_board"] == {"cie": [1]}
    assert payload["board_source"] == "explicit"
    without_source = tr.legacy_search_page([], total=0, limit=20, offset=0,
                                           board=None, by_board={})
    assert without_source["board_source"] is None, \
        "no board resolved -> the recorded expression yields None, not a token"
    assert set(without_source) == set(payload), "the key is present either way"


# -- counted queues -----------------------------------------------------------

def test_counted_matches_len_and_guards_extra():
    payload = tr.legacy_counted(["a", "b"], extra={"conflicts": 1})
    assert payload == {"count": 2, "items": ["a", "b"], "conflicts": 1}
    with pytest.raises(ValueError):
        tr.legacy_counted([], extra={"count": 0})


def test_status_counted_total_only_when_the_handler_computed_it():
    without_total = tr.legacy_status_counted("open", [1, 2])
    assert set(without_total) == {"status", "count", "items"}
    assert "total" not in without_total, "absence must be preserved, not filled"
    with_total = tr.legacy_status_counted("pending", [1, 2], total=7)
    assert with_total["total"] == 7


# -- unified views ------------------------------------------------------------

def test_unified_question_view_roundtrip():
    bundle = {"question": {"id": 1}, "children": []}
    payload = tr.unified_question_view(question_id=1, board="cie", board_source="inferred",
                                       source={"subject_code": "0580"}, bundle=bundle)
    assert set(payload) == {"question_id", "board", "board_source", "source", "bundle"}
    assert payload["bundle"] == bundle


def test_taxonomy_counts_roots():
    payload = tr.taxonomy_payload([{"code": "1.1"}, {"code": "1.2"}])
    assert payload["topic_count"] == 2
    assert payload["topic_count"] == len(payload["roots"])


def test_classifications_count_conflicts_but_never_resolve_them():
    items = [{"method": "conflict", "winner": None},
             {"method": "label+content", "winner": "a"},
             {"method": "conflict", "winner": None}]
    payload = tr.classifications_payload(items)
    assert payload["count"] == 3
    assert payload["conflicts"] == 2
    assert payload["items"][0]["winner"] is None, "a conflict must stay unresolved"


def test_provenance_payload_kind_guard_and_shape():
    payload = tr.provenance_payload("question", 42, [{"source": "manual"}])
    assert payload == {"question_id": 42, "sources": [{"source": "manual"}]}
    assert tr.provenance_payload("asset", 7, []) == {"asset_id": 7, "sources": []}
    with pytest.raises(ValueError):
        tr.provenance_payload("paper", 1, [])


def test_provenance_coverage_complete_is_the_legacy_expression():
    complete = tr.provenance_coverage_payload(
        {"a": {"ratio": 1.0}, "b": {"ratio": 1.5}})
    assert complete["complete"] is True
    incomplete = tr.provenance_coverage_payload(
        {"a": {"ratio": 1.0}, "b": {"ratio": 0.5}})
    assert incomplete["complete"] is False


# -- sample / boards / paper --------------------------------------------------

def test_sample_validation_rule():
    assert tr.sample_request_valid(5, None)
    assert tr.sample_request_valid(None, 20)
    assert not tr.sample_request_valid(None, None)
    assert tr.SAMPLE_COUNT_OR_TARGET_DETAIL == "count 与 marks_target 至少给一个"


def test_sample_payload_recomputes_question_count():
    comp = {"marks_total": 12, "requested_marks": 10, "questions": [{"id": 1}]}
    payload = tr.sample_payload(comp)
    assert payload["question_count"] == 1
    assert payload["marks_total"] == 12


def test_boards_payload_shape():
    payload = tr.boards_payload(schema_version="1", auto_detect={"cie": "digits"},
                                boards=[{"board": "cie"}])
    assert set(payload) == {"schema_version", "auto_detect", "boards"}


def test_paper_payload_overrides_board_with_canonical():
    payload = tr.paper_payload({"total": 1, "board": "wrong"}, board="cie",
                               board_source="explicit")
    assert payload["board"] == "cie"
    assert payload["board_source"] == "explicit"
    assert tr.PAPER_QA_FORMAT_DETAIL == "format must be binary or json"


# -- error bodies and quality protection --------------------------------------

def test_error_record_preserves_status_and_detail():
    assert tr.legacy_error(504, "IELTS 聚合器超时（>120s）：coverage") == {
        "status_code": 504, "detail": "IELTS 聚合器超时（>120s）：coverage"}


def test_json_copy_preserves_absence():
    copy = tr.json_copy({"a": 1, "nested": {"x": None}})
    assert "b" not in copy
    assert set(copy["nested"]) == {"x"}
    assert copy["nested"]["x"] is None


def test_quality_fingerprint_is_path_keyed_and_protected():
    before = {"question": {"id": 1, "answer_verification": "unverified",
                           "content": "staged_synthetic"},
              "assets": [{"region_verification": "unverified"}]}
    after = tr.json_copy(before)
    tr.assert_no_quality_change(before, after)
    after["question"]["answer_verification"] = "verified"
    with pytest.raises(AssertionError, match="translation changed quality tokens"):
        tr.assert_no_quality_change(before, after)


def test_quality_fingerprint_ignores_non_dimension_keys():
    payload = {"verified": "yes", "difficulty": {"value": 3}}
    assert tr.quality_fingerprint(payload) == {}
