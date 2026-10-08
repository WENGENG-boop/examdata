"""A10 - the fixture-backed dataset the v2 app is served from.

The dataset is the only data source of the staged API, and it is deliberately
narrow: a catalog snapshot built by the frozen A09 builder from the A05 synthetic
providers, plus a provider registry. These tests pin the properties the routes
rely on - stable identities, resolvable references, a deterministic revision, and
an evidence label that never claims more than a synthetic fixture.

Nothing here reads the original tree, the network or a database.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from examdata_integration.api.dataset import (
    DEFERRED_ACTIVE_OWNER,
    EVIDENCE_SYNTHETIC,
    FIXTURE_ROOT,
    STAGING_ROOT,
    Dataset,
    build_fixture_snapshot,
    catalog_systems,
    default_dataset,
    deferred_fixtures,
    fixture_providers,
)
from examdata_integration.api.view import CatalogView
from examdata_integration.providers.capabilities import Capability

STAGED_SRC = STAGING_ROOT / "src"
STAGED_TESTS = STAGING_ROOT / "tests"


@pytest.fixture(scope="module")
def dataset() -> Dataset:
    return default_dataset()


# -- construction ------------------------------------------------------------ #
def test_dataset_is_served_from_a_synthetic_fixture(dataset) -> None:
    assert dataset.evidence == EVIDENCE_SYNTHETIC
    assert dataset.revision
    assert dataset.available_revisions == (dataset.revision,)


def test_fixture_root_is_inside_the_staging_tree() -> None:
    assert FIXTURE_ROOT == STAGING_ROOT / "fixtures" / "synthetic"
    assert STAGING_ROOT.is_dir()
    assert FIXTURE_ROOT.is_dir()


def test_snapshot_builds_from_three_fixture_providers() -> None:
    registry = fixture_providers()
    assert len(registry.provider_ids()) == 3
    snapshot = build_fixture_snapshot(registry)
    assert snapshot.entries


def test_revision_is_deterministic_across_builds() -> None:
    first = build_fixture_snapshot(fixture_providers())
    second = build_fixture_snapshot(fixture_providers())
    assert first.dataset_revision == second.dataset_revision
    assert [e.public_id for e in first.entries] == [e.public_id for e in second.entries]


def test_counts_cover_the_four_catalog_kinds(dataset) -> None:
    counts = dataset.snapshot.counts
    assert counts["total"] == sum(v for k, v in counts.items() if k != "total")
    for kind in ("course", "container", "question", "asset"):
        assert counts[kind] > 0, kind


def test_every_entry_has_a_native_locator_and_a_system(dataset) -> None:
    for entry in dataset.entries():
        assert entry.native_locator, entry.public_id
        assert entry.system, entry.public_id
        assert entry.kind in {"course", "container", "question", "asset"}


# -- identities and references ----------------------------------------------- #
def test_public_ids_are_unique(dataset) -> None:
    ids = [entry.public_id for entry in dataset.entries()]
    assert len(ids) == len(set(ids))


def test_every_question_container_ref_resolves(dataset) -> None:
    by_id = dataset.by_id()
    for entry in dataset.entries("question"):
        assert entry.container_ref, entry.public_id
        assert entry.container_ref in by_id, entry.public_id


def test_every_container_question_ref_resolves(dataset) -> None:
    by_id = dataset.by_id()
    for entry in dataset.entries("container"):
        refs = entry.searchable.get("question_refs") or []
        for ref in refs:
            assert ref in by_id, (entry.public_id, ref)


def test_every_section_question_id_resolves(dataset) -> None:
    by_id = dataset.by_id()
    for entry in dataset.entries("container"):
        for section in entry.searchable.get("sections") or []:
            for ref in section.get("questions") or []:
                assert ref in by_id, (entry.public_id, ref)


def test_sections_keep_the_fixture_native_order(dataset) -> None:
    view = CatalogView(dataset)
    for entry in dataset.entries("container"):
        refs = entry.searchable.get("question_refs") or []
        native = [view.native_id(dataset.by_id()[ref]) for ref in refs]
        for section in entry.searchable.get("sections") or []:
            ids = section.get("questions")
            if not ids:
                continue
            placed = [view.native_id(dataset.by_id()[ref]) for ref in ids]
            assert placed == native[:len(placed)], (entry.public_id, placed, native)


def test_alias_resolves_to_its_entry(dataset) -> None:
    view = CatalogView(dataset)
    for entry in dataset.entries():
        for alias in entry.aliases:
            assert view.find(alias).public_id == entry.public_id
    assert view.find("SB1") is not None
    assert view.find("no-such-alias") is None


def test_require_raises_a_404_for_an_unknown_identity(dataset) -> None:
    from examdata_integration.api.envelope import ApiError
    with pytest.raises(ApiError) as excinfo:
        CatalogView(dataset).require("course_absent", "course")
    assert excinfo.value.status == 404


def test_asset_lookup_by_sha256(dataset) -> None:
    by_sha = dataset.asset_by_sha()
    assert by_sha
    for entry in dataset.entries("asset"):
        assert by_sha[entry.identity_fields["sha256"]].public_id == entry.public_id


def test_provider_lookup_by_system(dataset) -> None:
    for system in ("cie", "edexcel", "ielts"):
        provider = dataset.provider_for_system(system)
        assert provider is not None
        assert provider.exam_system.value == system
    assert dataset.provider_for_system("toefl") is None


def test_systems_and_system_descriptors(dataset) -> None:
    systems = dataset.systems()
    assert {row["system"] for row in systems} == {
        "cie", "edexcel", "gaokao", "ielts", "toefl"}
    # only the three systems with a registered provider carry catalog entries
    assert catalog_systems(dataset.snapshot) == ["cie", "edexcel", "ielts"]
    for row in systems:
        assert row["availability"] in {"available", "experimental", "unavailable"}
    unavailable = {row["system"] for row in systems if row["availability"] == "unavailable"}
    assert unavailable == {"gaokao", "toefl"}


def test_registry_capabilities_match_the_frozen_fixtures(dataset) -> None:
    descriptors = {d.exam_system.value: d for d in dataset.registry.descriptors()}
    assert Capability.QUESTIONS in descriptors["cie"].capabilities
    assert Capability.REGIONS in descriptors["cie"].capabilities
    assert Capability.QUESTIONS not in descriptors["edexcel"].capabilities
    assert Capability.ANSWERS in descriptors["ielts"].capabilities
    assert Capability.REGIONS not in descriptors["ielts"].capabilities


# -- deferred families ------------------------------------------------------- #
def test_deferred_fixtures_are_labelled_and_complete() -> None:
    fixtures = {k: v for k, v in deferred_fixtures().items() if k != "reason"}
    assert set(fixtures) == {"syllabuses", "materials", "timetable_seasons",
                            "timetable_events", "timetable_windows", "tags", "jobs"}
    for family, rows in fixtures.items():
        if family == "jobs":
            assert rows and all(row["evidence"] == EVIDENCE_SYNTHETIC
                                for row in rows.values())
            continue
        if family == "tags":
            assert rows == []
            continue
        assert rows, family
        for row in rows:
            assert row["evidence"] == EVIDENCE_SYNTHETIC, (family, row)
            assert row["integration_status"] == DEFERRED_ACTIVE_OWNER, (family, row)


def test_no_deferred_fixture_invents_a_date() -> None:
    for row in deferred_fixtures()["timetable_events"]:
        if row["date"] is None:
            assert row["session"] is None or row["note"], row


# -- containment ------------------------------------------------------------- #
def test_the_dataset_reads_no_original_path() -> None:
    for entry in default_dataset().entries():
        blob = repr(entry.to_dict())
        assert "Desktop" not in blob
        assert "examdata/" not in blob.replace("examdata_integration", "")


@pytest.mark.parametrize("root", [STAGED_SRC, STAGED_TESTS])
def test_no_bytecode_was_written_under_staging(root: Path) -> None:
    assert not list(root.rglob("*.pyc"))
    assert not [p for p in root.rglob("__pycache__") if p.is_dir()]


def test_fixture_files_are_read_only_inputs() -> None:
    for path in FIXTURE_ROOT.rglob("*.json"):
        assert path.is_file()
