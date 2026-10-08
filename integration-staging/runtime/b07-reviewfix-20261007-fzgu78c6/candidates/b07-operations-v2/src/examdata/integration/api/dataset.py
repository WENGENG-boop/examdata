"""The fixture-backed read dataset for the isolated v2 API (plan A10).

The v2 API is served from two staged sources only:

* a **catalog snapshot** built from the A03/A05 synthetic provider fixtures via
  the frozen A09 builder - it is the stable identity + read index (courses,
  containers, questions, assets);
* the **provider registry** - answers and regions are read live from the
  fixture providers, keyed by the catalog entry's native locator, so no answer
  or region is ever duplicated into the catalog.

Materials, syllabuses, timetables and jobs are the plan's active-owner families
(plan 8.5). The five feature families are read through the active-owner seam
(``..adapters.active_owner``) and served from clearly labelled synthetic
fixtures; every item carries ``evidence = synthetic_fixture`` and
``integration_status = deferred_active_owner``, and the real owner integration
stays deferred and is never implied.

Packet B07 adds the read-only operations wiring: when the canonical
``operations_root`` setting (``EXAMDATA_OPERATIONS_ROOT``) is set, the dataset
scans that root once, read-only and bounded, derives the checkpoint coverage
and job views (``..operations.jobs``) plus the published-data coverage from the
configured expected manifest (``..operations.published``), and exposes them on
:class:`OperationsDataset`. The scan never writes, never resumes and never
touches a service; an unset root means "no operations view" and the read API
behaves exactly as before the wiring.

Nothing here reads the original tree, the network, a database or Kimi-owned
timetable code.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

from ..adapters.active_owner import (
    DEFERRED_ACTIVE_OWNER,
    EVIDENCE_SYNTHETIC,
    FeatureSource,
    FixtureFeatureSource,
    validate_feature_source,
)
from ..catalog.builder import (
    CatalogBuilder,
    source_from_asset,
    source_from_container,
    source_from_course,
    source_from_question,
)
from ..catalog.model import CatalogEntry, CatalogSnapshot
from ..contracts.base import UNKNOWN
from ..operations.checkpoints import CheckpointObservation
from ..operations.coverage import CoverageView, build_coverage
from ..operations.jobs import JobsView, build_jobs, sanitize_tree, scan_checkpoint_root
from ..operations.published import (
    MANIFEST_NAME,
    PublishedView,
    build_published,
    load_expected_manifest,
)
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

# ``EVIDENCE_SYNTHETIC`` and ``DEFERRED_ACTIVE_OWNER`` are re-exported from the
# active-owner seam, so every family shares one labelling vocabulary.

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


#: fixture document role -> the canonical document type the discovery block carries
_DISCOVERY_ROLES: dict[str, str] = {
    "qp": "question_paper",
    "ms": "mark_scheme",
    "er": "examiner_report",
    "gt": "grade_threshold",
}

#: session label suffix -> the fixture's own English season name
_SEASON_TITLES: dict[str, str] = {
    "jan": "January",
    "january": "January",
    "jun": "June",
    "june": "June",
    "mar": "March",
    "march": "March",
    "nov": "November",
    "november": "November",
    "oct": "October",
    "october": "October",
}


def _session_terms(sessions: Any) -> list[str]:
    """The English season names the container's own session labels carry, in order."""
    terms: list[str] = []
    for session in sessions or []:
        title = _SEASON_TITLES.get(str(session).rsplit("-", 1)[-1].casefold())
        if title and title not in terms:
            terms.append(title)
    return terms


def _discovery_block(system: str, native: Mapping[str, Any], sessions: list[str],
                     role: Any, course_titles: Mapping[str, str]) -> dict[str, Any] | None:
    """The frontend discovery projection for one container document, or ``None``.

    Only the fixture's own native fields are projected; an unknown role, or a
    system without a frozen block shape, returns ``None`` rather than a guess.
    """
    document_type = _DISCOVERY_ROLES.get(str(role))
    if document_type is None:
        return None
    if system == "cie":
        subject = str(native.get("subject"))
        return {
            "board": "cie",
            "subject": subject,
            "subject_title": course_titles.get(subject),
            "year": native.get("year"),
            "season": native.get("season"),
            "paper": native.get("paper"),
            "document_type": document_type,
        }
    if system == "edexcel":
        unit = str(native.get("unit_code") or "").casefold()
        paper_code = native.get("paper_code")
        years: list[str] = []
        for session in sessions:
            year = str(session).split("-", 1)[0]
            if year and year not in years:
                years.append(year)
        return {
            "board": "edexcel",
            "subject": unit,
            "subject_title": None,
            "year": years[0] if len(years) == 1 else None,
            "season": None,
            "paper": f"{unit}-{paper_code}" if paper_code is not None else None,
            "document_type": document_type,
        }
    return None


def build_fixture_snapshot(registry: ProviderRegistry) -> CatalogSnapshot:
    """Build the read index from the fixture providers' own models (A09 builder)."""
    sources = []
    container_native: dict[str, Any] = {}
    course_titles: dict[str, str] = {}
    discovery_by_sha: dict[str, dict[str, Any]] = {}
    terms_by_sha: dict[str, list[str]] = {}
    #: provider question public id -> catalog public id, and catalog id per container
    provider_to_catalog: dict[str, str] = {}
    question_catalog: list[tuple[str | None, str]] = []

    for provider_id in registry.provider_ids():
        provider = registry.get(provider_id)
        system = provider.exam_system.value

        courses = _query(provider, Capability.COURSES)
        if courses is not None:
            for course in courses.items:
                source = source_from_course(course)
                names = list(course.names or [])
                course_titles.setdefault(
                    str(course.native_code),
                    str(names[0]) if names else str(course.native_code))
                sources.append(source)

        containers = _query(provider, Capability.CONTAINERS)
        if containers is not None:
            for container in containers.items:
                container_native[container.public_id] = dict(container.native_identity)
                source = source_from_container(system, container)
                source.searchable["resources"] = list(container.resources)
                source.searchable["sections"] = list(container.sections)
                sources.append(source)

                sessions = [
                    str(session)
                    for section in container.sections or []
                    if isinstance(section, Mapping)
                    for session in (section.get("sessions") or [])
                ]
                terms = _session_terms(sessions)
                for resource in container.resources:
                    if not isinstance(resource, Mapping):
                        continue
                    sha = resource.get("sha256")
                    if not sha:
                        continue
                    block = _discovery_block(system, container.native_identity, sessions,
                                             resource.get("role"), course_titles)
                    if block is not None:
                        discovery_by_sha[str(sha)] = block
                    if terms:
                        terms_by_sha[str(sha)] = list(terms)

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
                for asset in result.items:
                    source = source_from_asset(system, asset)
                    sha = str(source.identity_fields.get("sha256") or "")
                    if sha in discovery_by_sha:
                        source.searchable["discovery"] = dict(discovery_by_sha[sha])
                    if sha in terms_by_sha:
                        source.searchable["discovery_terms"] = list(terms_by_sha[sha])
                    sources.append(source)

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


def fixture_feature_source() -> FixtureFeatureSource:
    """The read-only active-owner fixture source, validated on construction."""
    return FixtureFeatureSource(
        syllabuses=SYLLABUS_FIXTURES,
        materials=MATERIAL_FIXTURES,
        timetable_seasons=TIMETABLE_SEASON_FIXTURES,
        timetable_events=TIMETABLE_EVENT_FIXTURES,
        timetable_windows=TIMETABLE_WINDOW_FIXTURES,
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

#: The canonical operations-root setting read by the app factory when no
#: explicit root is given (packet B07).
OPERATIONS_ROOT_ENV = "EXAMDATA_OPERATIONS_ROOT"
#: Sentinel for ``default_dataset(operations_root=...)``: resolve the root from
#: the environment. An explicit path overrides it; ``None`` disables the view.
FROM_ENVIRONMENT = "__from_environment__"


def _operations_root_from_env() -> Path | None:
    """The configured operations root, or ``None`` when unset or empty."""
    raw = os.environ.get(OPERATIONS_ROOT_ENV, "")
    if not isinstance(raw, str) or not raw.strip():
        return None
    return Path(raw).resolve()


@dataclass
class OperationsDataset:
    """The read-only operations view derived from one configured root.

    The root is scanned exactly once per dataset construction (bounded and
    read-only); the A13 coverage rows and the B07 job rows are derived from
    that one scan and never from a second read. ``problems`` lists every
    derivation problem, and nothing here ever writes, resumes or starts
    anything.
    """

    root: Path | None
    root_kind: str = "configured"
    observations: list[CheckpointObservation] = field(default_factory=list)
    coverage: CoverageView = field(default_factory=CoverageView)
    jobs: JobsView = field(default_factory=JobsView)
    published: PublishedView | None = None
    skipped: list[dict[str, str]] = field(default_factory=list)
    truncated: bool = False
    problems: list[dict[str, Any]] = field(default_factory=list)

    @property
    def scanned_files(self) -> int:
        return len(self.observations)

    def to_public(self, *, secrets: Iterable[str] = ()) -> dict[str, Any]:
        """The sanitized public projection of the whole operations view."""
        return {
            "read_only": True,
            "root": {
                "kind": self.root_kind,
                "configured": self.root is not None,
                "scanned_files": self.scanned_files,
                "truncated": self.truncated,
                "skipped": sanitize_tree(self.skipped, secrets=secrets),
                "problems": sanitize_tree(self.problems, secrets=secrets),
            },
            "checkpoints": sanitize_tree(self.coverage.to_dict(), secrets=secrets),
            "jobs": self.jobs.briefs(secrets=secrets),
            "published": (sanitize_tree(self.published.to_dict(), secrets=secrets)
                          if self.published is not None else None),
        }


def operations_view(*, entries: Iterable[Any], root: str | Path | None,
                    observed_at: datetime | None = None,
                    dataset_revision: str | None = None) -> OperationsDataset | None:
    """Build the operations view for a configured root (``None`` disables it).

    ``root=None`` means no operations root is configured: the view is ``None``
    and the read API behaves exactly as before the B07 wiring. A configured
    root that is not a directory is recorded as ``missing`` with an explicit
    problem instead of raising, and a missing or invalid expected manifest is
    recorded as its own problem, never guessed.
    """
    if root is None:
        return None
    base = Path(root)
    view = OperationsDataset(root=base)
    if not base.is_dir():
        view.root_kind = "missing"
        view.problems.append({"code": "operations_root_missing"})
        return view
    scan = scan_checkpoint_root(base, observed_at=observed_at)
    view.observations = list(scan.observations)
    view.skipped = list(scan.skipped)
    view.truncated = scan.truncated
    view.coverage = build_coverage(scan.observations)
    view.jobs = build_jobs(view.coverage, scan.observations)
    manifest = None
    manifest_problem: str | None = None
    try:
        manifest = load_expected_manifest(base)
        if manifest is None:
            manifest_problem = "expected_manifest_missing"
    except ValueError:
        manifest_problem = "expected_manifest_invalid"
    except OSError:
        manifest_problem = "expected_manifest_unreadable"
    if manifest_problem is not None:
        view.problems.append({"code": manifest_problem})
    if manifest is not None:
        view.published = build_published(entries, manifest,
                                         dataset_revision=dataset_revision)
    return view


@dataclass
class Dataset:
    """Everything the app factory needs, with no global state."""

    snapshot: CatalogSnapshot
    registry: ProviderRegistry
    features: FeatureSource
    available_revisions: tuple[str, ...] = ()
    evidence: str = EVIDENCE_SYNTHETIC
    operations: OperationsDataset | None = None

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


def default_dataset(*, features: FeatureSource | None = None,
                    operations_root: str | Path | None = FROM_ENVIRONMENT) -> Dataset:
    """Build the fixture dataset the app factory uses when none is supplied.

    ``operations_root`` defaults to the canonical environment setting (packet
    B07); pass an explicit path to override it, or ``None`` to disable the
    operations view. Either way the construction is read-only.
    """
    source = features if features is not None else fixture_feature_source()
    validate_feature_source(source)
    registry = fixture_providers()
    snapshot = build_fixture_snapshot(registry)
    if operations_root == FROM_ENVIRONMENT:
        resolved_root: Path | None = _operations_root_from_env()
    elif operations_root is None:
        resolved_root = None
    else:
        resolved_root = Path(operations_root).resolve()
    operations = operations_view(entries=snapshot.entries, root=resolved_root,
                                 dataset_revision=snapshot.dataset_revision)
    return Dataset(snapshot=snapshot, registry=registry, features=source,
                   available_revisions=(snapshot.dataset_revision,),
                   operations=operations)


def deferred_fixtures(features: FeatureSource | None = None) -> dict[str, Any]:
    """The labelled deferred families, for the routes that must not imply real data."""
    source = features if features is not None else fixture_feature_source()
    return {
        "syllabuses": source.syllabuses(),
        "materials": source.materials(),
        "timetable_seasons": source.timetable_seasons(),
        "timetable_events": source.timetable_events(),
        "timetable_windows": source.timetable_windows(),
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
    "OPERATIONS_ROOT_ENV",
    "FROM_ENVIRONMENT",
    "fixture_providers",
    "build_fixture_snapshot",
    "fixture_feature_source",
    "Dataset",
    "OperationsDataset",
    "default_dataset",
    "operations_view",
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
