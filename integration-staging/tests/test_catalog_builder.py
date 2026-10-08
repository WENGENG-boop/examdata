"""A09 - catalog builder: validation, diff, and the two rejection rules.

Covers the plan 7.3 build transaction (steps 1-5) and its two safety rules:

* a build is reproducible - the dataset revision is a pure function of the
  entries, so two builds of the same inputs agree;
* a build that hits any problem returns ``snapshot=None`` (nothing publishable);
* a removal between revisions must be explained, else ``unexplained_removal``;
* a quality promotion must rest on authoritative evidence, else
  ``unexplained_quality_upgrade`` - and a synthetic fixture is never authoritative.

Fixtures are hand-authored synthetic mapping inputs under
``fixtures/synthetic/catalog/``. No original code, network, or live database.
"""
from __future__ import annotations

import json
from pathlib import Path

from examdata_integration.catalog.builder import (
    CatalogBuilder,
    diff_snapshots,
    has_authoritative_evidence,
    source_from_course,
    source_from_region,
)
from examdata_integration.catalog.model import CatalogEntry, CatalogSource, counts_for
from examdata_integration.contracts.models import Course, Region
from examdata_integration.contracts.enums import ExamSystem

STAGING = Path(__file__).resolve().parents[1]
FIXTURE_DIR = STAGING / "fixtures" / "synthetic" / "catalog"


def _load(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _sources(data: dict) -> list[CatalogSource]:
    return [CatalogSource.from_dict(s) for s in data.get("sources", [])]


def _previous(data: dict):
    previous_sources = data.get("previous_sources")
    if not previous_sources:
        return None
    result = CatalogBuilder().build([CatalogSource.from_dict(s) for s in previous_sources])
    assert result.ok, result.problems
    return result.snapshot


def _codes(result) -> list[str]:
    return sorted({p["code"] for p in result.problems})


# --- valid build ------------------------------------------------------------
def test_base_fixture_builds_a_publishable_snapshot():
    data = _load("catalog-base-synthetic.json")
    result = CatalogBuilder().build(_sources(data), input_revisions=data["input_revisions"])
    assert result.ok, result.problems
    assert result.snapshot is not None
    assert result.snapshot.dataset_revision == result.candidate_revision
    assert result.counts["total"] == 5
    assert result.counts["course"] == 1 and result.counts["question"] == 1
    assert result.snapshot.counts == result.counts
    assert result.snapshot.recompute_revision() == result.snapshot.dataset_revision


def test_build_is_reproducible_across_runs():
    data = _load("catalog-base-synthetic.json")
    first = CatalogBuilder().build(_sources(data))
    second = CatalogBuilder().build(_sources(data))
    assert first.ok and second.ok
    assert first.candidate_revision == second.candidate_revision
    assert first.snapshot.to_dict()["entries"] == second.snapshot.to_dict()["entries"]


def test_created_at_and_input_revisions_do_not_change_the_revision():
    data = _load("catalog-base-synthetic.json")
    a = CatalogBuilder().build(_sources(data), created_at="2000-01-01T00:00:00+00:00",
                               input_revisions={"x": 1})
    b = CatalogBuilder().build(_sources(data), created_at="2099-12-31T00:00:00+00:00",
                               input_revisions={"x": 2})
    assert a.candidate_revision == b.candidate_revision


# --- rejection rules from fixtures -----------------------------------------
def test_duplicate_native_id_fixture_is_rejected():
    data = _load("catalog-duplicate-native-id-synthetic.json")
    result = CatalogBuilder().build(_sources(data))
    assert not result.ok and result.snapshot is None
    assert _codes(result) == ["duplicate_native_id"]


def test_incomplete_reference_fixture_is_rejected():
    data = _load("catalog-incomplete-reference-synthetic.json")
    result = CatalogBuilder().build(_sources(data))
    assert not result.ok and result.snapshot is None
    assert _codes(result) == ["unresolved_identity"]


def test_unexplained_removal_fixture_is_rejected():
    data = _load("catalog-removal-unexplained-synthetic.json")
    result = CatalogBuilder().build(_sources(data), previous=_previous(data),
                                    explanations=data.get("explanations") or {})
    assert not result.ok and result.snapshot is None
    assert "unexplained_removal" in _codes(result)


def test_explained_removal_is_allowed():
    data = _load("catalog-removal-unexplained-synthetic.json")
    previous = _previous(data)
    removed_pid = CatalogSource.from_dict(data["previous_sources"][1]).entry_public_id()
    result = CatalogBuilder().build(_sources(data), previous=previous,
                                    explanations={removed_pid: "withdrawn upstream"})
    assert result.ok, result.problems
    assert result.diff["counts"]["removed"] == 1
    assert result.snapshot.explanations == {removed_pid: "withdrawn upstream"}


def test_unexplained_quality_upgrade_fixture_is_rejected():
    data = _load("catalog-quality-upgrade-unexplained-synthetic.json")
    result = CatalogBuilder().build(_sources(data), previous=_previous(data))
    assert not result.ok and result.snapshot is None
    assert _codes(result) == ["unexplained_quality_upgrade"]


def test_quality_upgrade_with_authoritative_evidence_is_allowed():
    data = _load("catalog-quality-upgrade-unexplained-synthetic.json")
    previous = _previous(data)
    upgraded = _sources(data)
    # swap the synthetic label for an authoritative one, keep the promotion
    upgraded[0].evidence_labels = ["copied_snapshot"]
    result = CatalogBuilder().build(upgraded, previous=previous)
    assert result.ok, result.problems
    assert result.diff["counts"]["quality_upgrades"] == 1
    assert has_authoritative_evidence(result.snapshot.entries[0]) is True


def test_synthetic_evidence_is_never_authoritative():
    data = _load("catalog-quality-upgrade-unexplained-synthetic.json")
    snapshot = CatalogBuilder().build(_sources(data)).snapshot  # one course, synthetic_fixture only
    assert snapshot is not None
    assert has_authoritative_evidence(snapshot.entries[0]) is False


# --- diff -------------------------------------------------------------------
def test_diff_reports_added_removed_and_changed():
    base = _load("catalog-base-synthetic.json")
    previous = CatalogBuilder().build(_sources(base)).snapshot

    changed = _sources(base)
    changed[0].searchable = {"native_code": "0580", "names": ["Renamed"]}   # course changes
    changed.append(CatalogSource.from_dict(base["sources"][0]))             # benign dup -> ignored
    extra = CatalogSource(kind="course", system="cie",
                          identity_fields={"system": "cie", "qualification": "igcse",
                                           "native_code": "0581", "specification_version": "2026"},
                          native_locator={"kind": "course", "native_code": "0581", "qualification": "igcse"},
                          content_class="synthetic", evidence_labels=["synthetic_fixture"],
                          content_revision="rev-0581")
    changed.append(extra)

    result = CatalogBuilder().build(changed, previous=previous)
    assert result.ok, result.problems
    assert result.diff["counts"]["added"] == 1
    assert result.diff["counts"]["removed"] == 0
    assert result.diff["counts"]["changed"] == 1


def test_diff_snapshots_of_identical_entries_is_empty():
    base = _load("catalog-base-synthetic.json")
    snapshot = CatalogBuilder().build(_sources(base)).snapshot
    diff = diff_snapshots(snapshot, snapshot.entries)
    assert diff["counts"] == {"added": 0, "removed": 0, "changed": 0, "quality_upgrades": 0}


# --- mapping helpers preserve the native identity --------------------------
def test_source_from_course_preserves_native_identity():
    course = Course(system=ExamSystem.CIE, qualification="igcse", native_code="0580",
                    specification_version="2026", names=["Mathematics"], aliases=["0580"])
    source = source_from_course(course)
    assert source.kind == "course"
    assert source.identity_fields["native_code"] == "0580"
    assert source.identity_fields["specification_version"] == "2026"
    assert source.content_class == "unknown"   # not carried by the model -> not invented
    entry = CatalogEntry.from_source(source, source.entry_public_id())
    assert entry.public_id


def test_source_from_region_preserves_document_hash_and_bbox():
    region = Region(document_role="qp",
                    document_sha256="0" * 64,
                    page=3, bbox=(1.0, 2.0, 3.0, 4.0), coordinate_system="pdf_points")
    source = source_from_region("cie", region)
    assert source.identity_fields["document_sha256"] == "0" * 64
    assert source.identity_fields["bbox"] == [1.0, 2.0, 3.0, 4.0]
    assert source.native_locator["page"] == 3
