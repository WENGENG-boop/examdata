"""W4a shared test builders: injected synthetic components for the seam tests.

Everything here builds *test-local*, clearly labelled synthetic components
inside the test's own temporary deployment root. Nothing reads the frozen
fixture tree except :func:`fixture_content_store`, which deliberately points at
it so a test can prove the production path refuses a fixture-rooted store.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from examdata.integration.api.binary import ContentStore
from examdata.integration.api.dataset import FIXTURE_ROOT
from examdata.integration.catalog.model import (
    CatalogEntry,
    CatalogSnapshot,
    compute_revision,
)
from examdata.integration.contracts.enums import ExamSystem
from examdata.integration.providers.capabilities import Availability, Capability
from examdata.integration.providers.protocol import ProviderDescriptor
from examdata.integration.providers.results import ProviderResult


class SyntheticProvider:
    """A non-fixture provider with a real descriptor; answers empty successes."""

    def __init__(self, provider_id: str = "w4a_synth_provider", *,
                 system: ExamSystem = ExamSystem.CIE,
                 capabilities: Sequence[Capability] = (Capability.COURSES,
                                                       Capability.CONTAINERS)) -> None:
        self.descriptor = ProviderDescriptor(
            provider_id=provider_id,
            exam_system=system,
            display_name="W4a synthetic provider",
            capabilities=frozenset(capabilities),
            availability=Availability.AVAILABLE,
        )

    def query(self, capability: Any, *, filters: Mapping[str, Any] | None = None,
              target: str | None = None) -> ProviderResult:
        cap = Capability.coerce(capability)
        if not self.descriptor.supports(cap):
            return ProviderResult.unsupported(self.descriptor.provider_id, cap.value)
        return ProviderResult.success(self.descriptor.provider_id, cap.value)


def synthetic_registry(*providers: Any) -> Any:
    """A registry holding the given providers (one synthetic provider by default)."""
    from examdata.integration.providers.registry import ProviderRegistry

    registry = ProviderRegistry()
    for provider in (providers or (SyntheticProvider(),)):
        registry.register(provider)
    return registry


def empty_registry() -> Any:
    from examdata.integration.providers.registry import ProviderRegistry

    return ProviderRegistry()


def synthetic_snapshot() -> CatalogSnapshot:
    """A one-entry snapshot with a real, computed revision."""
    entries = [
        CatalogEntry(
            public_id="course:w4a:9709",
            kind="course",
            system="cie",
            identity_fields={"system": "cie", "kind": "course", "native_id": "9709"},
            native_locator={"system": "cie", "kind": "course", "native_id": "9709"},
            evidence_labels=["synthetic_injected"],
        )
    ]
    return CatalogSnapshot(
        dataset_revision=compute_revision(entries),
        created_at="2026-10-07T00:00:00+00:00",
        input_revisions={"w4a_test": "synthetic-injected"},
        counts={"course": 1},
        entries=entries,
    )


def production_rows() -> dict[str, list[dict[str, Any]]]:
    """Rows labelled the way an integrated real source would be (no fixtures)."""
    return {
        "syllabuses": [{
            "public_id": "syllabus:w4a:1", "system": "cie", "version": "2026",
            "evidence": "production_source", "integration_status": "integrated",
        }],
        "materials": [{
            "public_id": "material:w4a:1", "system": "cie", "kind": "notes",
            "native_id": "m1", "evidence": "production_source",
            "integration_status": "integrated",
        }],
        "timetable_seasons": [{
            "system": "cie", "season": "june", "year": 2026,
            "availability": "unknown", "evidence": "production_source",
            "integration_status": "integrated",
        }],
        "timetable_events": [{
            "system": "cie", "zone": "default", "course_native_code": "9709",
            "component": "P1", "date": None, "session": None,
            "evidence": "production_source", "integration_status": "integrated",
        }],
        "timetable_windows": [{
            "system": "cie", "zone": "default",
            "unknown_boundaries": ["start", "end"],
            "parsed": {"start": None, "end": None},
            "evidence": "production_source", "integration_status": "integrated",
        }],
    }


class StubFeatureSource:
    """A non-fixture feature source over rows the caller controls."""

    def __init__(self, rows: Mapping[str, Sequence[Mapping[str, Any]]]
                 | None = None) -> None:
        merged = production_rows()
        for key, value in dict(rows or {}).items():
            merged[key] = [dict(row) for row in value]
        self._rows = {key: [dict(row) for row in value]
                      for key, value in merged.items()}

    def syllabuses(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self._rows["syllabuses"]]

    def materials(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self._rows["materials"]]

    def timetable_seasons(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self._rows["timetable_seasons"]]

    def timetable_events(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self._rows["timetable_events"]]

    def timetable_windows(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self._rows["timetable_windows"]]


class MissingAccessorSource(StubFeatureSource):
    """A source without ``timetable_windows``: the production validator refuses it."""

    timetable_windows = None  # type: ignore[assignment]


def empty_content_store(root: str | Path) -> ContentStore:
    """A verified but sample-free store over its own manifest, outside fixtures."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    manifest = root / "manifest.json"
    manifest.write_text(
        json.dumps({"schema": "examdata.integration.content-manifest/1"}),
        encoding="utf-8")
    return ContentStore(root, manifest)


def fixture_content_store() -> ContentStore:
    """The real fixture-rooted store; the production path must refuse it."""
    root = FIXTURE_ROOT / "binary"
    return ContentStore(root, root / "manifest.json")


def failing_provider(provider_id: str, capability: Capability = Capability.COURSES, *,
                     system: ExamSystem = ExamSystem.CIE) -> Any:
    """A registered provider whose ``query`` always raises (sanitized failure)."""
    from examdata.integration.providers.fixtures import FailingProvider

    provider = FailingProvider(provider_id)
    provider.descriptor = ProviderDescriptor(
        provider_id=provider_id, exam_system=system,
        display_name="W4a synthetic failing provider",
        capabilities=frozenset({capability}), supported_filters={},
        availability=Availability.AVAILABLE,
        limitations=("query always raises a synthetic error",))
    return provider


def dataset_with_registry(registry: Any, *, base: Any = None) -> Any:
    """The fixture dataset with its registry replaced (every other field kept)."""
    import dataclasses

    from examdata.integration.api.dataset import Dataset, default_dataset

    base = base if base is not None else default_dataset(operations_root=None)
    kwargs = {f.name: getattr(base, f.name) for f in dataclasses.fields(Dataset) if f.init}
    kwargs["registry"] = registry
    return Dataset(**kwargs)


def production_config(deployment_root: str | Path, *, api_key: str = "sk-w4a-synthetic-0000",
                      **overrides: Any) -> Any:
    """A production config over a test deployment root (import kept lazy)."""
    from examdata.integration.api import assembly

    return assembly.ProductionConfig(
        deployment_root=str(deployment_root), api_key=api_key, **overrides)
