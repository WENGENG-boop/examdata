"""A10 - the v2 envelope, the error map and public sanitisation (plan 5.1, 5.2).

The envelope is the one shape every v2 response has, and `ApiError` is the only
non-200 raise path, so a status can only ever come from the plan's map. These
tests pin both properties, plus the two rules that keep a public payload honest:
an explicit UNKNOWN never becomes ``null``, and no local path, credential or
stack frame can leak.

Only staged code is imported; no original module, no network, no live service.
"""
from __future__ import annotations

import json
from enum import Enum

import pytest

from examdata_integration.api.envelope import (
    BINARY_STATUSES,
    EMITTABLE_STATUSES,
    ERROR_MAP,
    SCHEMA_VERSION,
    ApiError,
    clean,
    error_envelope,
    ok_envelope,
    sanitize_details,
    sanitize_text,
)
from examdata_integration.catalog.model import UNKNOWN_TOKEN
from examdata_integration.contracts.base import ContractModel, Gap
from examdata_integration.contracts.canonical import UNKNOWN

#: The plan 5.2 table, restated so a change to the staged map fails loudly.
PLAN_STATUSES = {200, 400, 401, 403, 404, 409, 410, 413, 422, 429, 500, 502, 503, 504}


def test_error_map_is_the_plan_table() -> None:
    assert set(ERROR_MAP) == PLAN_STATUSES
    assert all(isinstance(v, str) and v for v in ERROR_MAP.values())


def test_emittable_statuses_are_a_subset_of_the_map() -> None:
    # the binary carve-outs join the plan 5.2 map: 206/304 are success
    # semantics of the transport and 416 a failure reported in the envelope.
    assert EMITTABLE_STATUSES <= set(ERROR_MAP) | BINARY_STATUSES
    assert 200 in EMITTABLE_STATUSES
    assert 413 in EMITTABLE_STATUSES  # binary budget failures are staged
    # statuses that need a capability Phase A does not stage are documented but
    # never produced by the staged layer.
    assert not EMITTABLE_STATUSES & {401, 403, 410, 429, 504}


@pytest.mark.parametrize("status", sorted(EMITTABLE_STATUSES))
def test_api_error_accepts_every_emittable_status(status: int) -> None:
    error = ApiError(status, "some_code", "a public message")
    assert error.status == status
    assert error.code == "some_code"


@pytest.mark.parametrize("status", [201, 204, 301, 418, 451, 599])
def test_api_error_refuses_a_status_outside_the_map(status: int) -> None:
    with pytest.raises(ValueError):
        ApiError(status, "made_up", "not in the plan's map")


def test_api_error_is_an_exception_carrying_its_message() -> None:
    error = ApiError(404, "not_found", "no catalog entry matches 'x'")
    assert isinstance(error, Exception)
    assert str(error) == "no catalog entry matches 'x'"


def test_api_error_sanitizes_message_and_details() -> None:
    error = ApiError(
        500, "internal_error",
        "failed reading C:/Users/weo/Desktop/api/examdata/secret.json",
        details={"token": "api_key=abcdef0123456789",
                 "nested": {"path": r"C:\Users\weo\Desktop\api\x.py"}})
    assert "C:/Users" not in error.message
    assert "<path>" in error.message
    blob = json.dumps(error.details)
    assert "abcdef0123456789" not in blob
    assert "C:\\Users" not in blob


def test_api_error_to_error_shape() -> None:
    error = ApiError(503, "provider_unavailable", "no provider", retryable=True)
    assert error.to_error() == {
        "code": "provider_unavailable",
        "message": "no provider",
        "retryable": True,
        "details": {},
    }


def test_ok_envelope_shape() -> None:
    payload = ok_envelope(request_id="req_1", data={"items": []},
                          dataset_revision="rev_1", retrieved_at="2026-10-05T00:00:00+00:00",
                          limit=50)
    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["request_id"] == "req_1"
    assert payload["error"] is None
    assert payload["data"] == {"items": []}
    meta = payload["meta"]
    assert meta["dataset_revision"] == "rev_1"
    assert meta["pagination"] == {"limit": 50, "next_cursor": None}
    assert meta["completeness"] == "complete"
    assert meta["warnings"] == []
    assert meta["providers"] == []


def test_error_envelope_has_null_data_and_unknown_completeness() -> None:
    payload = error_envelope(request_id="req_2",
                             error=ApiError(404, "not_found", "absent"),
                             dataset_revision="rev_1",
                             retrieved_at="2026-10-05T00:00:00+00:00")
    assert payload["data"] is None
    assert payload["error"]["code"] == "not_found"
    assert payload["meta"]["completeness"] == "unknown"
    assert payload["meta"]["pagination"] == {"limit": None, "next_cursor": None}
    assert payload["meta"]["warnings"] == []


def test_envelope_warnings_are_sanitized() -> None:
    payload = ok_envelope(request_id="req_3", data=None, dataset_revision=None,
                          retrieved_at="2026-10-05T00:00:00+00:00",
                          warnings=["read C:/tmp/x.json\n\nnow"])
    assert payload["meta"]["warnings"] == ["read <path> now"]


class _Colour(Enum):
    RED = "red"


class _Row(ContractModel):
    SCHEMA = "row/1"

    def __init__(self) -> None:
        self.public_id = "q_1"
        self.colour = _Colour.RED

    def to_dict(self) -> dict:
        return {"schema": self.SCHEMA, "public_id": self.public_id,
                "colour": self.colour}


def test_clean_encodes_unknown_as_its_reserved_token() -> None:
    assert clean(UNKNOWN) == UNKNOWN_TOKEN
    assert clean({"a": UNKNOWN, "b": [UNKNOWN, None]}) == {
        "a": UNKNOWN_TOKEN, "b": [UNKNOWN_TOKEN, None]}


def test_clean_never_emits_the_internal_schema_key() -> None:
    assert clean(_Row()) == {"public_id": "q_1", "colour": "red"}
    assert clean({"row": _Row(), "schema": "keep-me-out"}) == {
        "row": {"public_id": "q_1", "colour": "red"}}


def test_clean_turns_enums_into_values() -> None:
    assert clean(_Colour.RED) == "red"
    assert clean({"colours": [_Colour.RED]}) == {"colours": ["red"]}


def test_clean_serializes_a_contract_model_gap() -> None:
    row = clean(Gap(code="missing_answer_slot", scope="answer", detail="no slot"))
    assert row == {"code": "missing_answer_slot", "scope": "answer",
                   "detail": "no slot"}


def test_sanitize_text_collapses_whitespace_and_bounds_length() -> None:
    assert sanitize_text("  a\n\tb   c ") == "a b c"
    assert len(sanitize_text("x" * 5000)) == 300


def test_sanitize_text_removes_stack_frames() -> None:
    text = sanitize_text('Traceback (most recent call last):\nFile "x.py", line 3')
    assert "Traceback" not in text
    assert "line 3" not in text
    assert "x.py" not in text
    assert text == "[stack]: [stack]"


def test_sanitize_text_redacts_credentials_and_paths() -> None:
    assert sanitize_text("api_key=supersecret") == "api_key=<redacted>"
    assert "abcdef" not in sanitize_text("Bearer abcdef")
    assert "<redacted>" in sanitize_text("Bearer abcdef")
    assert sanitize_text(r"see C:\Users\weo\x.json now") == "see <path> now"
    assert sanitize_text("see /var/lib/examdata/x now") == "see <path> now"


def test_sanitize_details_recurses_and_bounds_depth() -> None:
    deep: dict = {}
    cursor = deep
    for _ in range(12):
        cursor["child"] = {}
        cursor = cursor["child"]
    out = sanitize_details(deep)
    blob = json.dumps(out)
    assert "<depth-limit>" in blob
    assert sanitize_details(_Colour.RED) == "red"
    assert sanitize_details([1, "C:/x"]) == [1, "<path>"]
