"""A09 - catalog model + store: identity, duplicates, collisions, references.

Covers the plan 7.2 mapping rules the store is responsible for:

* the model round-trips losslessly, including the explicit ``UNKNOWN`` sentinel
  (so an identity never silently changes on a serialisation round-trip);
* one native identity maps to a stable public ID, and the exact native locator a
  provider needs round-trips;
* a benign re-registration (same identity, same content) deduplicates, while the
  same identity with different content is recorded *and* raised as
  ``duplicate_native_id``;
* two different canonical identities colliding on one public ID is recorded and
  rejected;
* an alias claimed by two identities is recorded and rejected atomically;
* a cross-reference that resolves to nothing is reported as ``unresolved_identity``.

Only the staged ``examdata_integration`` package is exercised: no original code,
no network, no live database.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from examdata_integration.catalog.model import (
    CatalogEntry,
    CatalogSnapshot,
    CatalogSource,
    UNKNOWN_TOKEN,
    compute_revision,
    counts_for,
    decode_unknown,
    encode_unknown,
)
from examdata_integration.catalog.store import (
    CatalogStore,
    DuplicateNativeIdError,
    GAP_FOR_CODE,
    problem,
    to_gap,
)
from examdata_integration.contracts.base import UNKNOWN
from examdata_integration.contracts.enums import EntityKind, GapCode, GapScope

STAGING = Path(__file__).resolve().parents[1]
FIXTURE_DIR = STAGING / "fixtures" / "synthetic" / "catalog"


def _course(code: str, *, content_revision: str = "rev-1", **extra) -> CatalogSource:
    return CatalogSource(
        kind="course",
        system="cie",
        identity_fields={"system": "cie", "qualification": "igcse",
                         "native_code": code, "specification_version": "2026"},
        native_locator={"kind": "course", "native_code": code, "qualification": "igcse"},
        aliases=[code],
        searchable={"native_code": code},
        source_revision="2026",
        quality_summary={"content": "complete", "answer_verification": "unverified"},
        content_class="synthetic",
        evidence_labels=["synthetic_fixture"],
        content_revision=content_revision,
        **extra,
    )


def _container(native_id: str, *, course_ref: str | None = None) -> CatalogSource:
    return CatalogSource(
        kind="container",
        system="cie",
        identity_fields={"system": "cie", "kind": "paper",
                         "native_identity": {"native_id": native_id, "session": "June", "year": 2026}},
        native_locator={"kind": "container",
                        "native_identity": {"native_id": native_id, "session": "June", "year": 2026}},
        aliases=[f"{native_id}-june-2026"],
        course_ref=course_ref,
        searchable={"kind": "paper"},
        content_class="synthetic",
        evidence_labels=["synthetic_fixture"],
        content_revision=f"rev-{native_id}",
    )


# --- model round-trip -------------------------------------------------------
def test_source_round_trips_including_unknown():
    source = CatalogSource(
        kind="question",
        system="ielts",
        identity_fields={"system": "ielts",
                         "container_native_identity": {"native_id": "book-1"},
                         "native_id": "Q41",
                         "number_path": ["41"],
                         "parent_native_id": UNKNOWN},
        native_locator={"kind": "question", "native_id": "Q41", "container_ref": "book-1"},
        content_class="synthetic",
        evidence_labels=["synthetic_fixture"],
    )
    payload = source.to_dict()
    assert payload["identity_fields"]["parent_native_id"] == UNKNOWN_TOKEN
    restored = CatalogSource.from_dict(payload)
    assert restored.identity_fields["parent_native_id"] is UNKNOWN
    assert restored.to_dict() == payload
    assert restored.entry_public_id() == source.entry_public_id()


def test_unknown_and_absent_encode_differently():
    present = encode_unknown({"x": UNKNOWN})
    absent = encode_unknown({"x": None})
    assert present != absent
    assert decode_unknown(present)["x"] is UNKNOWN
    assert decode_unknown(absent)["x"] is None


def test_entry_and_snapshot_round_trip():
    source = _course("0400")
    entry = CatalogEntry.from_source(source, source.entry_public_id())
    assert CatalogEntry.from_dict(entry.to_dict()).to_dict() == entry.to_dict()
    snapshot = CatalogSnapshot(dataset_revision=compute_revision([entry]),
                               created_at="2026-10-05T18:30:00+08:00",
                               input_revisions={"fixtures": "x"}, counts=counts_for([entry]),
                               entries=[entry])
    assert CatalogSnapshot.from_dict(snapshot.to_dict()).to_dict() == snapshot.to_dict()
    assert snapshot.recompute_revision() == snapshot.dataset_revision


def test_revision_is_a_pure_function_of_entries():
    a = _course("0400")
    b = _course("0401")
    e1 = CatalogEntry.from_source(a, a.entry_public_id())
    e2 = CatalogEntry.from_source(b, b.entry_public_id())
    assert compute_revision([e1, e2]) == compute_revision([e2, e1])
    assert compute_revision([e1]) != compute_revision([e1, e2])


# --- registration + lookup --------------------------------------------------
def test_add_resolves_and_round_trips_locator():
    store = CatalogStore()
    source = _course("0400")
    entry = store.add(source)
    assert entry is not None
    assert store.resolve("0400") == entry.public_id          # alias
    assert store.resolve(entry.public_id) == entry.public_id  # public id
    assert store.native_locator(entry.public_id) == source.native_locator
    # mutating the returned locator must not corrupt the stored entry
    got = store.native_locator(entry.public_id)
    got["native_code"] = "tampered"
    assert store.native_locator(entry.public_id)["native_code"] == "0400"


def test_benign_reregistration_deduplicates():
    store = CatalogStore()
    first = store.add(_course("0400"))
    second = store.add(_course("0400"))
    assert first is second
    assert len(store.entries) == 1
    assert store.duplicates and store.duplicates[0]["benign"] is True
    assert not store.problems


def test_duplicate_native_id_is_recorded_and_raised():
    store = CatalogStore()
    store.add(_course("0400", content_revision="rev-a"))
    with pytest.raises(DuplicateNativeIdError):
        store.add(_course("0400", content_revision="rev-b"))
    assert [p["code"] for p in store.problems] == ["duplicate_native_id"]
    assert store.duplicates[0]["benign"] is False
    # the first registration is untouched
    assert len(store.entries) == 1


def test_add_all_keeps_going_after_a_duplicate():
    store = CatalogStore()
    out = store.add_all([_course("0400", content_revision="rev-a"),
                         _course("0400", content_revision="rev-b"),
                         _course("0401")])
    assert out[0] is not None and out[1] is None and out[2] is not None
    assert [p["code"] for p in store.problems] == ["duplicate_native_id"]


def test_invalid_identity_is_a_problem_not_a_crash():
    store = CatalogStore()
    bad = CatalogSource(kind="not-a-kind", system="cie",
                        identity_fields={"system": "cie"},
                        native_locator={"kind": "x"})
    assert store.add(bad) is None
    assert store.problems[0]["code"] == "invalid_identity"


# --- collisions + aliases ---------------------------------------------------
def test_identity_collision_is_recorded_and_rejected(monkeypatch):
    import examdata_integration.catalog.store as store_mod
    import examdata_integration.contracts.ids as ids_mod

    forced = "c_" + "a" * 32
    monkeypatch.setattr(store_mod, "derive_public_id", lambda kind, fields: forced)
    monkeypatch.setattr(ids_mod, "derive_public_id", lambda kind, fields: forced)

    store = CatalogStore()
    assert store.add(_container("0580/41")) is not None
    assert store.add(_container("0580/42")) is None
    codes = [p["code"] for p in store.problems]
    assert codes == ["identity_collision"]
    assert len(store.entries) == 1


def test_alias_conflict_is_recorded_and_atomic():
    store = CatalogStore()
    first = _course("0400")
    first.aliases = ["shared"]
    assert store.add(first) is not None
    second = _course("0401")
    second.aliases = ["SHARED"]
    assert store.add(second) is None
    assert [p["code"] for p in store.problems] == ["alias_conflict"]
    # the rejected identity is not half-registered
    assert len(store.entries) == 1
    assert store.resolve("0401") is None


# --- references -------------------------------------------------------------
def test_unresolved_reference_is_reported():
    store = CatalogStore()
    store.add(_container("0580/41", course_ref="9999"))
    problems = store.validate_references()
    assert [p["code"] for p in problems] == ["unresolved_identity"]
    assert problems[0]["scope"] == "course_ref"


def test_resolved_reference_is_clean():
    store = CatalogStore()
    store.add(_course("0580"))
    store.add(_container("0580/41", course_ref="0580"))
    assert store.validate_references() == []


def test_problem_maps_to_a_frozen_gap():
    rec = problem("duplicate_native_id", "catalog", "dup", "c_1")
    gap = to_gap(rec)
    assert gap is not None
    assert gap.code == GapCode.UNRESOLVED_IDENTITY.value
    assert gap.scope == GapScope.SYSTEM.value
    assert to_gap(problem("some_diagnostic", "catalog", "x")) is None
    assert set(GAP_FOR_CODE) >= {"duplicate_native_id", "identity_collision",
                                 "alias_conflict", "unresolved_identity", "invalid_identity"}


# --- fixture cross-check ----------------------------------------------------
def test_base_fixture_loads_and_all_references_resolve():
    data = json.loads((FIXTURE_DIR / "catalog-base-synthetic.json").read_text(encoding="utf-8"))
    store = CatalogStore()
    store.add_all(CatalogSource.from_dict(s) for s in data["sources"])
    assert store.problems == []
    assert store.validate_references() == []
    kinds = sorted(e.kind for e in store.sorted_entries())
    assert kinds == ["asset", "container", "course", "question", "region"]
    assert all(e.public_id for e in store.sorted_entries())
