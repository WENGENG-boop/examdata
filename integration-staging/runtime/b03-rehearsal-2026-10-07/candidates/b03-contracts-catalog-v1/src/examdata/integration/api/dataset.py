"""The fixture-backed read dataset for the isolated v2 API (plan A10).

The v2 API is served from two staged sources only:

* a **catalog snapshot** built from the A03/A05 synthetic provider fixtures via
  the frozen A09 builder - it is the stable identity + read index (courses,
  containers, questions, assets);
* the **provider registry** - answers and regions are read live from the
  fixture providers, keyed by the catalog entry's native locator, so no answer
  or region is ever duplicated into the catalog.

Materials, syllabuses, timetables and jobs are the plan's active-owner families
(plan 8.5). They are served from clearly labelled synthetic fixtures and every
item carries ``evidence = synthetic_fixture`` and
``integration_status = deferred_active_owner``; the real integration stays
deferred to Phase B and is never implied.

Nothing here reads the original tree, the network, a database or Kimi-owned
timetable code.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..catalog.builder import (
    CatalogBuilder,
    source_from_asset,
    source_from_container,
    source_from_course,
    source_from_question,
)
from ..catalog.model import CatalogEntry, CatalogSnapshot
from ..contracts.base import UNKNOWN
from ..providers.capabilities import Capability
from ..providers.fixtures import (
    CIEIndexProvider,
    EdexcelIndexProvider,
    IELTSQuestionsProvider,
)
from ..providers.registry import ProviderRegistry
from ..runtime.paths import resolve_root

STAGING_ROOT = resolve_root()
FIXTURE_ROOT = STAGING_ROOT / "fixtures" / "synthetic"

EVIDENCE_SYNTHETIC = "synthetic_fixture"
DEFERRED_ACTIVE_OWNER = "deferred_active_owner"

_DEFERRED_REASON = (
    "owned by the active project owner during Phase A; the staged API serves a "
    "clearly labelled synthetic fixture and the real integration is deferred"
)


def fixture_providers() -> ProviderRegistry:
    """The three A05 synthetic fixture providers, in deterministic order."""
    registry = ProviderRegistry()
    registry.register(CIEIndexProvider(FIXTURE_ROOT / "cie" / "cie-index-synthetic.json"))
    registry.register(EdexcelIndexProvider(FIXTURE_ROOT / "edexcel" / "index-synthetic.json"))
    registry.register(IELTSQuestionsProvider(FIXTURE_ROOT / "ielts" / "questions-synthetic.json"))
    return registry


def _query(provider, capability: Capability):
    if not provider.descriptor.supports(capability):
        return None
    return provider.query(capability)


def build_fixture_snapshot(registry: ProviderRegistry) -> CatalogSnapshot:
    """Build the read index from the fixture providers' own models (A09 builder)."""
    sources = []
    container_native: dict[str, Any] = {}
    #: provider question public id -> catalog public id, and catalog id per container
    provider_to_catalog: dict[str, str] = {}
    question_catalog: list[tuple[str | None, str]] = []

    for provider_id in registry.provider_ids():
        provider = registry.get(provider_id)
        system = provider.exam_system.value

        courses = _query(provider, Capability.COURSES)
        if courses is not None:
            sources.extend(source_from_course(c) for c in courses.items)

        containers = _query(provider, Capability.CONTAINERS)
        if containers is not None:
            for container in containers.items:
                container_native[container.public_id] = dict(container.native_identity)
                source = source_from_container(system, container)
                source.searchable["resources"] = list(container.resources)
                source.searchable["sections"] = list(container.sections)
                sources.append(source)

        questions = _query(provider, Capability.QUESTIONS)
        if questions is not None:
            for question in questions.items:
                source = source_from_question(
                    system, question,
                    container_native_identity=container_native.get(question.container_ref, UNKNOWN),
                    parent_native_id=question.parent_ref,
                )
                source.container_ref = question.container_ref
                catalog_id = source.entry_public_id()
                provider_to_catalog[question.public_id] = catalog_id
                question_catalog.append((question.container_ref, question.public_id))
                sources.append(source)

        for capability in (Capability.ASSETS, Capability.RESOURCES):
            result = _query(provider, capability)
            if result is not None:
                sources.extend(source_from_asset(system, a) for a in result.items)

    # A container's sections keep the fixture's own native order, but every
    # question reference is rewritten to the catalog public id: the provider's
    # own public id is not a catalog identity and must never appear as a link
    # target or be left dangling. Questions that the fixture does not place in a
    # section are appended so none is lost.
    placed: dict[str, list[str]] = {}
    for container_ref, provider_question_id in question_catalog:
        if container_ref:
            placed.setdefault(container_ref, []).append(provider_question_id)

    for source in sources:
        if source.kind != "container":
            continue
        catalog_id = source.entry_public_id()
        if catalog_id not in placed:
            continue
        mapped = [provider_to_catalog[q] for q in placed[catalog_id]]
        sections = []
        used: list[str] = []
        for section in source.searchable.get("sections") or []:
            section = dict(section)
            if isinstance(section.get("questions"), (list, tuple)):
                kept = [provider_to_catalog[q] for q in section["questions"]
                        if q in provider_to_catalog]
                section["questions"] = kept
                used.extend(kept)
            sections.append(section)
        source.searchable["sections"] = sections
        leftover = [q for q in mapped if q not in used]
        source.searchable["question_refs"] = used + leftover

    result = CatalogBuilder().build(
        sources,
        input_revisions={"fixtures": "a10-synthetic-providers",
                         "parser": "catalog-source/1"},
        explanations={},
    )
    if not result.ok or result.snapshot is None:
        raise RuntimeError(
            "the fixture catalog did not build cleanly: "
            f"{[p.get('code') for p in result.problems]}")
    return result.snapshot


# --------------------------------------------------------------------------- #
# clearly labelled deferred fixtures (materials, syllabuses, timetables, jobs)
# --------------------------------------------------------------------------- #
def _deferred(entry: dict[str, Any]) -> dict[str, Any]:
    out = dict(entry)
    out["evidence"] = EVIDENCE_SYNTHETIC
    out["integration_status"] = DEFERRED_ACTIVE_OWNER
    return out


SYLLABUS_FIXTURES: tuple[dict[str, Any], ...] = (
    _deferred({
        "public_id": "syl_synthetic_cie_0580",
        "system": "cie", "course_native_code": "9999", "version": "2026",
        "title": "Synthetic syllabus (fixture)",
        "applicable_years": [2026], "source_evidence": ["synthetic_fixture"],
    }),
    _deferred({
        "public_id": "syl_synthetic_ielts_book",
        "system": "ielts", "course_native_code": "SYNTH-BOOK-1", "version": "1",
        "title": "Synthetic syllabus (fixture)",
        "applicable_years": [], "source_evidence": ["synthetic_fixture"],
    }),
)

MATERIAL_FIXTURES: tuple[dict[str, Any], ...] = (
    _deferred({
        "public_id": "mat_synthetic_cie_ins", "system": "cie", "kind": "insert",
        "native_id": "SYNTH-INS-1", "applicability": "synthetic",
        "access_mode": "fixture_only", "versions": ["1"],
    }),
    _deferred({
        "public_id": "mat_synthetic_edexcel_gt", "system": "edexcel", "kind": "grade_thresholds",
        "native_id": "SYNTH-GT-1", "applicability": "synthetic",
        "access_mode": "fixture_only", "versions": ["1"],
    }),
)

TIMETABLE_SEASON_FIXTURES: tuple[dict[str, Any], ...] = (
    _deferred({
        "system": "cie", "qualification": "igcse", "season": "June", "year": 2026,
        "availability": "unavailable",
        "reason": "the synthetic fixtures carry no session date, so the season "
                  "boundary is explicitly unknown rather than guessed",
    }),
    _deferred({
        "system": "edexcel", "qualification": "igcse", "season": "June", "year": 2026,
        "availability": "unavailable",
        "reason": "no timetable source is staged in Phase A",
    }),
)

TIMETABLE_EVENT_FIXTURES: tuple[dict[str, Any], ...] = (
    _deferred({
        "system": "cie", "qualification": "igcse", "zone": "zone5",
        "course_native_code": "9999", "component": "11", "date": None, "session": None,
        "raw_text": None,
        "note": "unknown boundaries stay null; nothing is inferred from similarity",
    }),
    _deferred({
        "system": "edexcel", "qualification": "igcse", "zone": "zone5",
        "course_native_code": "SYNTH-UNIT-1", "component": None, "date": "2026-06-01",
        "session": "AM", "raw_text": "synthetic timetable line",
    }),
)

TIMETABLE_WINDOW_FIXTURES: tuple[dict[str, Any], ...] = (
    _deferred({
        "system": "cie", "qualification": "igcse", "zone": "zone5",
        "original_text": None, "source": "synthetic_fixture",
        "raw": {"start": None, "end": None}, "parsed": {"start": None, "end": None},
        "unknown_boundaries": ["start", "end"],
    }),
    _deferred({
        "system": "edexcel", "qualification": "igcse", "zone": "zone5",
        "original_text": "synthetic window", "source": "synthetic_fixture",
        "raw": {"start": "2026-06-01", "end": None},
        "parsed": {"start": "2026-06-01", "end": None},
        "unknown_boundaries": ["end"],
    }),
)

TAG_FIXTURES: tuple[dict[str, Any], ...] = ()

JOB_FIXTURES: dict[str, dict[str, Any]] = {
    "job_synthetic_coverage": _deferred({
        "public_id": "job_synthetic_coverage",
        "scope": "coverage", "input_revision": "rev-synthetic",
        "state": "succeeded", "progress": {"done": 1, "total": 1},
        "started_at": None, "finished_at": None,
        "result": {"note": "synthetic job record; no real job queue is staged"},
    }),
}

UNAVAILABLE_SYSTEMS: dict[str, str] = {
    "toefl": "the TOEFL read adapter is staged but no TOEFL provider is registered "
             "in Phase A, so the system is reported unavailable",
    "gaokao": "gaokao is out of scope for the staged Phase A dataset",
}


@dataclass
class Dataset:
    """Everything the app factory needs, with no global state."""

    snapshot: CatalogSnapshot
    registry: ProviderRegistry
    available_revisions: tuple[str, ...] = ()
    evidence: str = EVIDENCE_SYNTHETIC

    @property
    def revision(self) -> str:
        return self.snapshot.dataset_revision

    def entries(self, kind: str | None = None) -> list[CatalogEntry]:
        rows = [e for e in self.snapshot.entries if kind is None or e.kind == kind]
        return sorted(rows, key=lambda e: e.public_id)

    def by_id(self) -> dict[str, CatalogEntry]:
        return self.snapshot.by_id()

    def asset_by_sha(self) -> dict[str, CatalogEntry]:
        return {e.identity_fields.get("sha256"): e
                for e in self.entries("asset") if e.identity_fields.get("sha256")}

    def provider_for_system(self, system: str) -> Any | None:
        for descriptor in self.registry.descriptors():
            if descriptor.exam_system.value == system:
                return self.registry.get(descriptor.provider_id)
        return None

    def systems(self) -> list[dict[str, Any]]:
        out = []
        for descriptor in self.registry.descriptors():
            out.append({
                "system": descriptor.exam_system.value,
                "availability": descriptor.availability.value,
                "providers": [descriptor.provider_id],
                "evidence": self.evidence,
            })
        for system, reason in UNAVAILABLE_SYSTEMS.items():
            out.append({"system": system, "availability": "unavailable",
                        "providers": [], "reason": reason, "evidence": self.evidence})
        return sorted(out, key=lambda row: row["system"])


def default_dataset() -> Dataset:
    """Build the fixture dataset the app factory uses when none is supplied."""
    registry = fixture_providers()
    snapshot = build_fixture_snapshot(registry)
    return Dataset(snapshot=snapshot, registry=registry,
                   available_revisions=(snapshot.dataset_revision,))


def deferred_fixtures() -> dict[str, Any]:
    """The labelled deferred families, for the routes that must not imply real data."""
    return {
        "syllabuses": list(SYLLABUS_FIXTURES),
        "materials": list(MATERIAL_FIXTURES),
        "timetable_seasons": list(TIMETABLE_SEASON_FIXTURES),
        "timetable_events": list(TIMETABLE_EVENT_FIXTURES),
        "timetable_windows": list(TIMETABLE_WINDOW_FIXTURES),
        "tags": list(TAG_FIXTURES),
        "jobs": dict(JOB_FIXTURES),
        "reason": _DEFERRED_REASON,
    }


def catalog_systems(snapshot: CatalogSnapshot) -> list[str]:
    return sorted({e.system for e in snapshot.entries if e.system})


__all__ = [
    "STAGING_ROOT",
    "FIXTURE_ROOT",
    "EVIDENCE_SYNTHETIC",
    "DEFERRED_ACTIVE_OWNER",
    "fixture_providers",
    "build_fixture_snapshot",
    "Dataset",
    "default_dataset",
    "deferred_fixtures",
    "catalog_systems",
    "SYLLABUS_FIXTURES",
    "MATERIAL_FIXTURES",
    "TIMETABLE_SEASON_FIXTURES",
    "TIMETABLE_EVENT_FIXTURES",
    "TIMETABLE_WINDOW_FIXTURES",
    "TAG_FIXTURES",
    "JOB_FIXTURES",
    "UNAVAILABLE_SYSTEMS",
]
