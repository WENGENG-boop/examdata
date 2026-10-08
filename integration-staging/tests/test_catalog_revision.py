"""A09 - revision publication: immutability, atomic pointer, CAS, rollback, cursors.

Covers the plan 7.3 publication transaction (steps 6-8) and plan 5.7 cursors:

* each revision is written once; the current pointer is replaced atomically;
* publication is compare-and-swap, so a stale builder is refused;
* republishing the current revision is idempotent;
* rollback restores the retained previous revision atomically;
* a failed validation (no snapshot, or a revision that does not match its
  entries) leaves ``current.json`` untouched;
* cursors bind query/sort/revision, are integrity-checked (tampering -> 400) and
  are refused as stale (409) once their revision is no longer published.

Only staged code and a private temp root are used: no original code, no network,
no live database.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from examdata_integration.catalog.builder import CatalogBuilder
from examdata_integration.catalog.model import CatalogSnapshot, CatalogSource
from examdata_integration.catalog.revision import (
    ANY_CURRENT,
    CURSOR_SCHEMA,
    InvalidCursorError,
    PublicationRejected,
    RevisionError,
    RevisionPublisher,
    StaleCursorError,
    StalePublisherError,
    UnknownRevisionError,
    make_cursor,
    parse_cursor,
    resolve_cursor,
)

STAGING = Path(__file__).resolve().parents[1]
FIXTURE_DIR = STAGING / "fixtures" / "synthetic" / "catalog"


def _base_snapshot():
    data = json.loads((FIXTURE_DIR / "catalog-base-synthetic.json").read_text(encoding="utf-8"))
    result = CatalogBuilder().build([CatalogSource.from_dict(s) for s in data["sources"]])
    assert result.ok, result.problems
    return result.snapshot


def _variant_snapshot():
    data = json.loads((FIXTURE_DIR / "catalog-base-synthetic.json").read_text(encoding="utf-8"))
    sources = [CatalogSource.from_dict(s) for s in data["sources"]]
    sources.append(CatalogSource(
        kind="course", system="cie",
        identity_fields={"system": "cie", "qualification": "igcse",
                         "native_code": "0581", "specification_version": "2026"},
        native_locator={"kind": "course", "native_code": "0581", "qualification": "igcse"},
        content_class="synthetic", evidence_labels=["synthetic_fixture"],
        content_revision="rev-syn-course-0581"))
    result = CatalogBuilder().build(sources)
    assert result.ok, result.problems
    return result.snapshot


# --- publication ------------------------------------------------------------
def test_publish_writes_immutable_revision_and_pointer(tmp_path):
    publisher = RevisionPublisher(tmp_path / "catalog")
    snapshot = _base_snapshot()
    pointer = publisher.publish(snapshot, now="2026-10-05T18:30:00+08:00")
    assert pointer["schema"] == "catalog-pointer/1"
    assert pointer["dataset_revision"] == snapshot.dataset_revision
    assert pointer["previous"] is None
    assert publisher.current_revision() == snapshot.dataset_revision
    assert publisher.retain(snapshot.dataset_revision)
    assert publisher.available_revisions() == [snapshot.dataset_revision]
    # the stored revision body round-trips
    restored = publisher.load_revision(snapshot.dataset_revision)
    assert restored.to_dict() == snapshot.to_dict()


def test_republish_current_revision_is_idempotent(tmp_path):
    publisher = RevisionPublisher(tmp_path / "catalog")
    snapshot = _base_snapshot()
    first = publisher.publish(snapshot, now="2026-10-05T18:30:00+08:00")
    before = publisher.pointer_path.read_text(encoding="utf-8")
    second = publisher.publish(snapshot, now="2026-10-05T19:00:00+08:00")
    assert second == first
    assert publisher.pointer_path.read_text(encoding="utf-8") == before


def test_publish_is_compare_and_swap(tmp_path):
    publisher = RevisionPublisher(tmp_path / "catalog")
    base = _base_snapshot()
    publisher.publish(base, now="t1")
    variant = _variant_snapshot()
    # a builder that read the base revision and publishes while current is base: fine
    publisher.publish(variant, expected_current=base.dataset_revision, now="t2")
    assert publisher.current_revision() == variant.dataset_revision
    # a stale builder still expecting base is refused
    with pytest.raises(StalePublisherError):
        publisher.publish(base, expected_current=base.dataset_revision, now="t3")
    assert publisher.current_revision() == variant.dataset_revision


def test_publish_refuses_a_revision_that_does_not_match_its_entries(tmp_path):
    publisher = RevisionPublisher(tmp_path / "catalog")
    snapshot = _base_snapshot()
    publisher.publish(snapshot, now="t1")
    before = publisher.pointer_path.read_text(encoding="utf-8")

    broken = CatalogSnapshot.from_dict(snapshot.to_dict())
    broken.dataset_revision = "rev-tampered"
    with pytest.raises(PublicationRejected):
        publisher.publish(broken)
    assert publisher.pointer_path.read_text(encoding="utf-8") == before


def test_publish_none_leaves_the_pointer_untouched(tmp_path):
    publisher = RevisionPublisher(tmp_path / "catalog")
    snapshot = _base_snapshot()
    publisher.publish(snapshot, now="t1")
    before = publisher.pointer_path.read_text(encoding="utf-8")
    with pytest.raises(PublicationRejected):
        publisher.publish(None)
    assert publisher.pointer_path.read_text(encoding="utf-8") == before


def test_rollback_restores_the_previous_revision(tmp_path):
    publisher = RevisionPublisher(tmp_path / "catalog")
    base = _base_snapshot()
    variant = _variant_snapshot()
    publisher.publish(base, now="t1")
    publisher.publish(variant, now="t2")
    pointer = publisher.rollback(now="t3")
    assert pointer["dataset_revision"] == base.dataset_revision
    assert publisher.current_revision() == base.dataset_revision
    # both revisions are still retained
    assert set(publisher.available_revisions()) == {base.dataset_revision, variant.dataset_revision}


def test_rollback_without_previous_is_refused(tmp_path):
    publisher = RevisionPublisher(tmp_path / "catalog")
    publisher.publish(_base_snapshot(), now="t1")
    with pytest.raises(RevisionError):
        publisher.rollback()


def test_load_missing_revision_is_an_error(tmp_path):
    publisher = RevisionPublisher(tmp_path / "catalog")
    with pytest.raises(UnknownRevisionError):
        publisher.load_revision("rev-does-not-exist")


# --- cursors ----------------------------------------------------------------
def test_cursor_round_trips():
    cursor = make_cursor(dataset_revision="rev-x", query={"kind": "question"},
                         sort="native_id", last_key="Q7", limit=50)
    payload = parse_cursor(cursor)
    assert payload["schema"] == CURSOR_SCHEMA
    assert payload["dataset_revision"] == "rev-x"
    assert payload["query"] == {"kind": "question"}
    assert payload["last_key"] == "Q7"
    assert payload["limit"] == 50


def test_tampered_cursor_is_invalid():
    cursor = make_cursor(dataset_revision="rev-x", last_key="Q7")
    body, _, _tag = cursor.rpartition(".")
    tampered = body[:-1] + ("A" if body[-1] != "A" else "B") + "."
    with pytest.raises(InvalidCursorError):
        parse_cursor(tampered)
    with pytest.raises(InvalidCursorError):
        parse_cursor("not-a-cursor")
    with pytest.raises(InvalidCursorError):
        parse_cursor("")


def test_overlong_cursor_is_invalid():
    with pytest.raises(InvalidCursorError):
        make_cursor(dataset_revision="rev-x", query={"blob": "z" * 8000})


def test_stale_cursor_is_refused():
    cursor = make_cursor(dataset_revision="rev-gone", last_key="Q1")
    with pytest.raises(StaleCursorError):
        resolve_cursor(cursor, available_revisions=["rev-other"])


def test_cursor_bound_to_a_retained_revision_resolves():
    cursor = make_cursor(dataset_revision="rev-live", last_key="Q1")
    payload = resolve_cursor(cursor, available_revisions=["rev-live", "rev-old"])
    assert payload["dataset_revision"] == "rev-live"


def test_cursor_survives_a_republish_of_the_same_revision(tmp_path):
    publisher = RevisionPublisher(tmp_path / "catalog")
    snapshot = _base_snapshot()
    publisher.publish(snapshot, now="t1")
    cursor = make_cursor(dataset_revision=snapshot.dataset_revision, last_key="Q1")
    publisher.publish(snapshot, now="t2")   # idempotent republish
    payload = resolve_cursor(cursor, available_revisions=publisher.available_revisions())
    assert payload["dataset_revision"] == snapshot.dataset_revision
