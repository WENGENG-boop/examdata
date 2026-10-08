"""A08: the staged source reader classifies and validates without fetching."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from examdata_integration.adapters.source_reader import (
    SUPPORTED_SCHEMA_VERSIONS,
    SourceKind,
    SourceProblemCode,
    classify_path,
    iter_cache_entries,
    read_source,
    validate_kmf_url,
    validate_source,
)

STAGING = Path(__file__).resolve().parents[1]
FIXTURES = STAGING / "fixtures"
A03_IELTS = FIXTURES / "synthetic" / "ielts" / "questions-synthetic.json"
A08_IELTS = FIXTURES / "synthetic" / "ielts-toefl" / "ielts-questions-a08-synthetic.json"
COPIED_TOEFL = FIXTURES / "copied" / "toefl" / "ddy-index.json"
COPIED_PAGES = FIXTURES / "copied" / "ielts" / "printed-pages.json"


def _codes(problems):
    return [p.code for p in problems]


# -- path classification ---------------------------------------------------- #
def test_classify_path_distinguishes_copied_synthetic_and_outside():
    assert classify_path(COPIED_TOEFL) is SourceKind.COPIED_SNAPSHOT
    assert classify_path(A03_IELTS) is SourceKind.SYNTHETIC
    assert classify_path(STAGING / "runtime" / "tmp" / "x.json") is SourceKind.UNKNOWN
    assert classify_path(Path("C:/Users/weo/Desktop/api/examdata/README.md")) \
        is SourceKind.OUTSIDE_STAGING


def test_read_source_never_opens_a_file_outside_staging():
    outside = Path("C:/Users/weo/Desktop/api/docs/PROJECT_STATUS.md")
    data, kind, problems = read_source(outside)
    assert data is None
    assert kind is SourceKind.OUTSIDE_STAGING
    assert _codes(problems) == [SourceProblemCode.OUTSIDE_STAGING.value]


def test_read_source_reads_a_synthetic_fixture():
    data, kind, problems = read_source(A03_IELTS)
    assert kind is SourceKind.SYNTHETIC
    assert problems == []
    assert data["book"]["native_id"] == "synthetic-book-1"


def test_read_source_reads_a_copied_snapshot():
    data, kind, problems = read_source(COPIED_TOEFL)
    assert kind is SourceKind.COPIED_SNAPSHOT
    assert problems == []
    assert len(data["items"]) == 72


def test_read_source_rejects_a_kind_the_caller_does_not_allow():
    data, kind, problems = read_source(COPIED_TOEFL,
                                       allowed_kinds=(SourceKind.SYNTHETIC,))
    assert data is None
    assert kind is SourceKind.COPIED_SNAPSHOT
    assert _codes(problems) == [SourceProblemCode.WRONG_SOURCE_KIND.value]


def test_read_source_reports_a_missing_file():
    data, kind, problems = read_source(FIXTURES / "synthetic" / "nope.json")
    assert data is None
    assert _codes(problems) == [SourceProblemCode.MISSING_SOURCE.value]


def test_read_source_reports_invalid_json():
    broken = STAGING / "runtime" / "tmp" / "a08-broken.json"
    broken.write_text("{ not json", encoding="utf-8")
    try:
        data, kind, problems = read_source(broken)
        assert data is None
        assert _codes(problems) == [SourceProblemCode.INVALID_JSON.value]
    finally:
        broken.unlink(missing_ok=True)


# -- document validation ---------------------------------------------------- #
def test_validate_source_requires_a_synthetic_label():
    payload = {"book": {"native_id": "x"}}
    parsed, problems = validate_source(payload, kind=SourceKind.SYNTHETIC)
    assert parsed is None
    assert _codes(problems) == [SourceProblemCode.WRONG_SOURCE_KIND.value]


def test_validate_source_refuses_to_relabel_a_copied_snapshot():
    parsed, problems = validate_source({"fixture_kind": "synthetic"},
                                       kind=SourceKind.COPIED_SNAPSHOT)
    assert parsed is None
    assert _codes(problems) == [SourceProblemCode.WRONG_SOURCE_KIND.value]


def test_validate_source_rejects_an_unsupported_schema_version():
    parsed, problems = validate_source(
        {"fixture_kind": "synthetic", "schema_version": "9"},
        kind=SourceKind.SYNTHETIC, require_schema_version=True)
    assert parsed is None
    assert _codes(problems) == [SourceProblemCode.UNSUPPORTED_SCHEMA_VERSION.value]
    assert SUPPORTED_SCHEMA_VERSIONS == frozenset({"1"})


def test_validate_source_rejects_a_non_object():
    parsed, problems = validate_source([1, 2, 3], kind=SourceKind.SYNTHETIC)
    assert parsed is None
    assert _codes(problems) == [SourceProblemCode.INVALID_JSON.value]


# -- KMF URL shape ---------------------------------------------------------- #
@pytest.mark.parametrize("url", [
    "https://toefl.kmf.com/detail/read/81fwbj.html",
    "https://toefl.kmf.com/detail/read/51ehlj.html/1",
])
def test_validate_kmf_url_accepts_a_real_detail_url(url):
    ok, reason = validate_kmf_url(url)
    assert ok, reason


@pytest.mark.parametrize("url,needle", [
    ("http://toefl.kmf.com/detail/read/81fwbj.html", "https"),
    ("https://mirror.example/detail/read/81fwbj.html", "host"),
    ("https://toefl.kmf.com/detail/read/81fwbj.htm", "path"),
    ("https://toefl.kmf.com/detail/read/81fw-bj.html", "alphanumeric"),
    ("", "absent"),
    (None, "absent"),
])
def test_validate_kmf_url_rejects_a_bad_url(url, needle):
    ok, reason = validate_kmf_url(url)
    assert not ok
    assert needle in reason


# -- cache entries ---------------------------------------------------------- #
def test_iter_cache_entries_reports_malformed_and_duplicate_entries():
    cache = {"entries": [
        {"native_id": "a"},
        "not-an-object",
        {"kmf_url": "x"},
        {"native_id": "a"},
        {"native_id": "b"},
    ]}
    entries = iter_cache_entries(cache, source_name="c")
    assert len(entries) == 5
    assert [e.native_id for e in entries] == ["a", None, None, "a", "b"]
    rejected = [e for e in entries if e.problem is not None]
    assert [e.problem.code for e in rejected] == \
        [SourceProblemCode.BAD_CACHE_ENTRY.value] * 3
    assert [e.index for e in entries if e.problem is None] == [0, 4]


def test_iter_cache_entries_reports_a_missing_entries_list():
    entries = iter_cache_entries({"schema": "x"}, source_name="c")
    assert len(entries) == 1
    assert entries[0].problem.code == SourceProblemCode.BAD_CACHE_ENTRY.value


def test_iter_cache_entries_on_a_non_object_cache():
    entries = iter_cache_entries(["nope"], source_name="c")
    assert len(entries) == 1
    assert entries[0].problem is not None


# -- no network, no upgrade ------------------------------------------------- #
def test_reading_a_source_never_touches_the_network(monkeypatch):
    import socket

    def _explode(*_args, **_kwargs):
        raise AssertionError("a staged read must not open a socket")

    monkeypatch.setattr(socket, "create_connection", _explode)
    data, kind, problems = read_source(COPIED_TOEFL)
    assert data is not None and problems == []
