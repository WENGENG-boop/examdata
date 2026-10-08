"""A07: the read step (missing index, bad JSON, wrong kind, bad version)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from examdata_integration.adapters import SUPPORTED_SCHEMA_VERSIONS, read_index, validate_index
from examdata_integration.adapters.problems import ProblemCode

STAGING = Path(__file__).resolve().parents[1]
ADAPTER_FIXTURES = STAGING / "fixtures" / "synthetic" / "adapters"
SCRATCH = STAGING / "runtime" / "tmp"
CIE_FIXTURE = ADAPTER_FIXTURES / "cie-index-adapters.json"


def _codes(problems):
    return [p.code for p in problems]


def test_read_index_reads_a_valid_synthetic_fixture():
    data, problems = read_index(CIE_FIXTURE)
    assert problems == []
    assert data is not None
    assert data["board"] == "cie"
    assert data["fixture_kind"] == "synthetic"


def test_read_index_missing_file_is_a_problem_not_an_exception():
    data, problems = read_index(ADAPTER_FIXTURES / "does-not-exist.json")
    assert data is None
    assert _codes(problems) == [ProblemCode.MISSING_INDEX.value]
    assert problems[0].scope == "system"


def test_read_index_directory_path_is_missing_index():
    data, problems = read_index(ADAPTER_FIXTURES)
    assert data is None
    assert _codes(problems) == [ProblemCode.MISSING_INDEX.value]


def test_read_index_invalid_json_is_reported():
    bad = SCRATCH / "a07-invalid.json"
    bad.write_text("{not json", encoding="utf-8")
    data, problems = read_index(bad)
    assert data is None
    assert _codes(problems) == [ProblemCode.INVALID_JSON.value]


def test_read_index_undecodable_bytes_is_unreadable():
    bad = SCRATCH / "a07-undecodable.json"
    bad.write_bytes(b"\xff\xfe\x00\x01binary")
    data, problems = read_index(bad)
    assert data is None
    assert _codes(problems) == [ProblemCode.UNREADABLE_INDEX.value]


@pytest.mark.parametrize("payload,code", [
    (["not", "an", "object"], ProblemCode.INVALID_JSON),
    ({"fixture_kind": "official", "schema_version": "1"}, ProblemCode.WRONG_FIXTURE_KIND),
    ({"schema_version": "1"}, ProblemCode.WRONG_FIXTURE_KIND),
    ({"fixture_kind": "synthetic", "schema_version": "99"},
     ProblemCode.UNSUPPORTED_SCHEMA_VERSION),
    ({"fixture_kind": "synthetic"}, ProblemCode.UNSUPPORTED_SCHEMA_VERSION),
])
def test_validate_index_rejects_bad_documents(payload, code):
    data, problems = validate_index(payload, source_name="unit-test")
    assert data is None
    assert _codes(problems) == [code.value]


def test_validate_index_accepts_a_supported_version():
    data, problems = validate_index({"fixture_kind": "synthetic", "schema_version": "1"})
    assert problems == []
    assert data == {"fixture_kind": "synthetic", "schema_version": "1"}


def test_supported_versions_are_pinned():
    assert SUPPORTED_SCHEMA_VERSIONS == frozenset({"1"})


def test_read_index_does_not_mutate_the_source_file():
    before = CIE_FIXTURE.read_bytes()
    read_index(CIE_FIXTURE)
    assert CIE_FIXTURE.read_bytes() == before


def test_reader_returns_a_plain_dict_copy():
    data, _ = read_index(CIE_FIXTURE)
    data["board"] = "mutated"
    again, _ = read_index(CIE_FIXTURE)
    assert again["board"] == "cie"
    assert json.loads(CIE_FIXTURE.read_text(encoding="utf-8"))["board"] == "cie"
