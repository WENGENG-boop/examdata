"""A12 shape-parity harness (plan 5.5): value-free fingerprints and diffs.

The parity gate's whole value is that it compares structure without carrying
payload content; these tests prove each detection case the differ must make,
and prove the fingerprint of a payload containing a secret string never
contains that string.
"""
from __future__ import annotations

from examdata_integration.legacy import parity


def test_fingerprint_is_value_free_and_leak_free():
    payload = {"token": "SECRET-VALUE", "nested": [{"name": "also-secret"}]}
    fingerprint = parity.shape(payload)
    assert parity.value_leak(payload, fingerprint) == []
    assert "SECRET-VALUE" not in parity.render_shape(fingerprint)
    assert "also-secret" not in parity.render_shape(fingerprint)


def test_value_leak_flags_a_real_leak():
    payload = {"token": "SECRET-VALUE"}
    bogus = {"dict": {"token": "SECRET-VALUE"}}
    assert parity.value_leak(payload, bogus) == ["SECRET-VALUE"]


def test_mapping_keys_are_structure_not_leak():
    payload = {"question_id": 3}
    fingerprint = parity.shape(payload)
    assert parity.value_leak(payload, fingerprint) == [], "keys are allowed in a fingerprint"
    assert "question_id" in parity.render_shape(fingerprint)


def test_empty_and_nonempty_lists_are_distinguished():
    assert parity.shape([]) == {"list": "empty"}
    assert parity.shape([1]) == {"list": "nonempty", "kinds": ["int"]}
    assert parity.shape_diff(parity.shape([]), parity.shape([1])) == [
        "$: list empty -> non-empty"]
    assert parity.shape_diff(parity.shape([1]), parity.shape([])) == [
        "$: list non-empty -> empty"]


def test_missing_and_added_keys_are_detected():
    diffs = parity.shape_diff(parity.shape({"a": 1}), parity.shape({"b": 1}))
    assert any("key missing after" in d for d in diffs)
    assert any("key added by after" in d for d in diffs)


def test_kind_changes_including_none_to_value_are_detected():
    assert parity.shape_diff(parity.shape({"x": 1}), parity.shape({"x": "1"})) == [
        "$.x: kind int -> str"]
    assert parity.shape_diff(parity.shape({"x": None}), parity.shape({"x": 1})) == [
        "$.x: kind none -> int"]
    assert parity.shape_diff(parity.shape({"x": 1}), parity.shape({"x": None})) == [
        "$.x: kind int -> none"]


def test_item_shape_change_inside_nonempty_list():
    diffs = parity.shape_diff(parity.shape([{"id": 1}]), parity.shape([{"id": 1}, {"id": "x"}]))
    assert len(diffs) == 1 and "item shape added by after" in diffs[0]
    diffs = parity.shape_diff(parity.shape([1, "x"]), parity.shape([1]))
    assert len(diffs) == 1 and "item shape missing after" in diffs[0]


def test_bool_is_not_int_in_fingerprints():
    assert parity.shape(True) == "bool"
    assert parity.shape(1) == "int"


def test_assert_shape_parity_passes_identical_and_raises_on_diff():
    before = {"total": 1, "items": [{"id": 1}]}
    after = {"total": 999, "items": [{"id": 2}]}
    assert parity.assert_shape_parity(before, after) is after, "values differ, shapes do not"

    with_extra = {"total": 1, "items": [{"id": 1}], "extra": None}
    try:
        parity.assert_shape_parity(before, with_extra, label="route X")
    except AssertionError as exc:
        assert "shape parity failed for route X" in str(exc)
        assert "extra" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected an AssertionError")


def test_render_shape_is_compact_and_stable():
    assert parity.render_shape(parity.shape({"a": {"b": None}})) == "dict{a:dict{b:none}}"
    assert parity.render_shape(parity.shape([1, "x"])) == "list[int,str]"
    assert parity.render_shape(parity.shape({"l": []})) == "dict{l:list[empty]}"
