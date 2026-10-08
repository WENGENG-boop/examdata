"""Explicit dataset assembly: the fixture path and the production path (W4a).

The staged v2 app factory takes a :class:`~.dataset.Dataset`; this module owns
*which* dataset is assembled, as two clearly separated, labelled paths:

* **fixture mode** - :func:`build_fixture_dataset` delegates to the unchanged
  ``default_dataset()`` (the private rehearsal behaviour the frozen probe sees),
  and :func:`create_fixture_app` wraps ``create_app()`` with
  :data:`FIXTURE_BANNER`. Fixture mode is conspicuously labelled and never
  claims real data;
* **production mode** - :func:`build_production_dataset` /
  :func:`assemble_production` require injected real components (a non-fixture
  :class:`~..providers.registry.ProviderRegistry`, a :class:`CatalogSnapshot`,
  a non-fixture feature source, a verified :class:`ContentStore`, and
  production configuration with an API key). Every missing component fails
  closed with a typed, sanitized :class:`ProductionAssemblyError`; there is no
  fallback to ``fixture_providers()``, fixture feature rows, sample content,
  fake Node components or the static mock jobs, and no silent path from
  production mode back to fixture mode.

:func:`production_capabilities` renders, per endpoint family, what the
production path requires, what the fixture path serves today, what this private
phase installed, and what a real source must provide to be accepted - the raw
data of the W4 capability map.

Nothing here reads the original tree, the network or a database.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from ..adapters.active_owner import (
    DEFERRED_ACTIVE_OWNER,
    EVIDENCE_SYNTHETIC,
    FeatureSource,
    FixtureFeatureSource,
)
from ..catalog.model import CatalogSnapshot
from ..providers.fixtures import FixtureProvider
from ..providers.registry import ProviderRegistry
from ..runtime.paths import PathOutsideRootError, ensure_within, is_within
from ..runtime.settings import ConfigError, resolve_config
from . import links
from .binary import ContentStore
from .dataset import (
    DEFAULT_OPERATIONS_TTL_SECONDS,
    FIXTURE_ROOT,
    Dataset,
    OperationsObservationService,
    default_dataset,
)
from .envelope import sanitize_text

FIXTURE_MODE = "fixture"
PRODUCTION_MODE = "production"

FIXTURE_BANNER = (
    "PRIVATE FIXTURE MODE - synthetic rehearsal data only; production data is "
    "not served and this app must not be presented as production")
PRODUCTION_BANNER = (
    "PRODUCTION MODE - assembled from injected real components only; no fixture "
    "fallback is possible")

FIXTURE_EVIDENCE = EVIDENCE_SYNTHETIC
PRODUCTION_DEFAULT_EVIDENCE = "real_source"


class ProductionAssemblyError(RuntimeError):
    """A production assembly cannot proceed. Fails closed; never falls back."""

    default_code = "invalid_assembly"

    def __init__(self, message: str, *, code: str | None = None,
                 details: Mapping[str, Any] | None = None) -> None:
        clean = sanitize_text(str(message))
        super().__init__(clean)
        self.message = clean
        self.code = code or self.default_code
        self.details = {str(k): _clean_detail(v) for k, v in dict(details or {}).items()}

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "details": dict(self.details)}


class MissingComponentError(ProductionAssemblyError):
    """A required real component was not injected."""

    default_code = "invalid_assembly"


class MissingConfigurationError(ProductionAssemblyError):
    """Production configuration is absent or incomplete."""

    default_code = "invalid_configuration"


class FixtureFallbackRefused(ProductionAssemblyError):
    """A fixture artefact was offered where a production component is required."""

    default_code = "invalid_assembly"


class FixtureMarkerRefused(ProductionAssemblyError):
    """A row or label carries a synthetic/deferred marker in production mode."""

    default_code = "fixture_markers_refused"


class ProductionValidationError(ProductionAssemblyError):
    """A supplied component or configuration is invalid for production."""

    default_code = "invalid_assembly"


def _clean_detail(value: Any) -> Any:
    if isinstance(value, str):
        return sanitize_text(value)
    if isinstance(value, Mapping):
        return {str(k): _clean_detail(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean_detail(item) for item in value]
    return value


# --------------------------------------------------------------------------- #
# mode labelling
# --------------------------------------------------------------------------- #
def assembled_mode(dataset: Dataset) -> str:
    """The mode a dataset was assembled in, from its evidence label."""
    evidence = getattr(dataset, "evidence", None)
    return FIXTURE_MODE if evidence == EVIDENCE_SYNTHETIC else PRODUCTION_MODE


def describe_assembly(dataset: Dataset) -> dict[str, Any]:
    """A labelled, JSON-ready description of how a dataset was assembled."""
    mode = assembled_mode(dataset)
    snapshot = getattr(dataset, "snapshot", None)
    return {
        "mode": mode,
        "evidence": getattr(dataset, "evidence", None),
        "banner": FIXTURE_BANNER if mode == FIXTURE_MODE else PRODUCTION_BANNER,
        "revision": getattr(dataset, "revision", ""),
        "counts": dict(getattr(snapshot, "counts", {}) or {}),
    }


# --------------------------------------------------------------------------- #
# configuration
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ProductionConfig:
    """The configuration a production assembly runs under.

    Holds no fixture defaults: an empty deployment root or API key is refused
    at construction, and the synthetic evidence label can never be selected.
    """

    deployment_root: str
    api_key: str
    dataset_revision: str = ""
    network_mode: str = "offline"
    operations_root: str | None = None
    evidence_label: str = PRODUCTION_DEFAULT_EVIDENCE
    config_file: str | None = None

    def __post_init__(self) -> None:
        if not str(self.deployment_root or "").strip():
            raise ProductionValidationError(
                "production configuration requires a deployment root",
                code="invalid_configuration")
        if not str(self.api_key or "").strip():
            raise MissingConfigurationError(
                "production configuration requires an API key (set EXAMDATA_API_KEY)",
                code="api_key_missing")
        if self.evidence_label == EVIDENCE_SYNTHETIC:
            raise FixtureMarkerRefused(
                "the synthetic fixture evidence label cannot be used in production mode",
                code="fixture_markers_refused",
                details={"field": "evidence_label"})

    @classmethod
    def from_environment(cls, *, env: Mapping[str, str] | None = None,
                         config_file: str | Path | None = None,
                         dataset_revision: str = "",
                         deployment_root: str | Path | None = None,
                         evidence_label: str = PRODUCTION_DEFAULT_EVIDENCE
                         ) -> "ProductionConfig":
        """Resolve configuration from the canonical private settings.

        Uses :func:`..runtime.settings.resolve_config` (explicit argument, then
        ``EXAMDATA_INTEGRATION_ROOT``/``EXAMDATA_*`` environment, then config
        file, then defaults). A missing API key fails closed; nothing here
        reads an original tree or a network.
        """
        try:
            resolved = resolve_config(env=env, config_file=config_file,
                                      deployment_root=deployment_root)
        except (ConfigError, PathOutsideRootError, RuntimeError) as exc:
            raise ProductionValidationError(
                f"production configuration could not be resolved: {exc}",
                code="invalid_configuration",
                details={"cause": type(exc).__name__}) from exc
        return cls(
            deployment_root=str(resolved.deployment_root),
            api_key=str(resolved.get("api_key") or ""),
            dataset_revision=dataset_revision,
            network_mode=str(resolved.get("network_mode") or "offline"),
            operations_root=resolved.path("operations_root"),
            evidence_label=evidence_label,
            config_file=resolved.config_file,
        )


# --------------------------------------------------------------------------- #
# fixture path (explicit, labelled, probe-compatible)
# --------------------------------------------------------------------------- #
def build_fixture_dataset(**dataset_kwargs: Any) -> Dataset:
    """Build the labelled private fixture dataset.

    Delegates to the unchanged ``default_dataset()`` so the probe-compatible
    fixture behaviour has exactly one implementation; this module never builds
    fixture components itself and never imports ``fixture_providers``.
    """
    return default_dataset(**dataset_kwargs)


def create_fixture_app(**dataset_kwargs: Any) -> Any:
    """The conspicuously labelled fixture app path (a thin ``create_app`` wrap).

    ``create_app()`` itself stays untouched; this wrapper only labels the app
    state with :data:`FIXTURE_MODE` and :data:`FIXTURE_BANNER` so a running
    fixture instance can never be mistaken for production.
    """
    from .app import create_app

    dataset = build_fixture_dataset(**dataset_kwargs)
    app = create_app(dataset=dataset)
    app.state.assembly_mode = FIXTURE_MODE
    app.state.assembly_banner = FIXTURE_BANNER
    app.state.assembly_description = describe_assembly(dataset)
    return app


# --------------------------------------------------------------------------- #
# production path
# --------------------------------------------------------------------------- #
_FEATURE_FAMILIES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("syllabuses", "syllabuses", ("public_id",)),
    ("materials", "materials", ("public_id",)),
    ("timetable_seasons", "timetable_seasons", ("system",)),
    ("timetable_events", "timetable_events", ("system",)),
    ("timetable_windows", "timetable_windows", ("system",)),
)


def validate_production_features(source: Any) -> dict[str, int]:
    """Validate a production feature source; refuse fixture markers.

    Unlike the fixture-side validator this demands nothing synthetic: each of
    the five accessors must exist, return a list of mappings, and no row may
    carry the ``synthetic_fixture`` evidence marker or the
    ``deferred_active_owner`` integration marker.
    """
    counts: dict[str, int] = {}
    for family, method, identity_keys in _FEATURE_FAMILIES:
        accessor = getattr(source, method, None)
        if accessor is None or not callable(accessor):
            raise ProductionValidationError(
                f"feature source does not implement {method}()",
                code="invalid_assembly",
                details={"family": family, "field": "accessor"})
        rows = accessor()
        if not isinstance(rows, (list, tuple)):
            raise ProductionValidationError(
                f"{method}() must return a list of rows",
                code="invalid_assembly",
                details={"family": family, "field": "rows"})
        for position, row in enumerate(rows):
            if not isinstance(row, Mapping):
                raise ProductionValidationError(
                    f"{method}() returned a non-mapping row",
                    code="invalid_assembly",
                    details={"family": family, "row": position, "field": "row"})
            for key in identity_keys:
                value = row.get(key)
                if not isinstance(value, str) or not value.strip():
                    raise ProductionValidationError(
                        f"{family} row {position} has no non-empty {key!r}",
                        code="invalid_assembly",
                        details={"family": family, "row": position, "field": key})
            if row.get("evidence") == EVIDENCE_SYNTHETIC:
                raise FixtureMarkerRefused(
                    f"{family} row {position} carries the synthetic fixture evidence marker",
                    code="fixture_markers_refused",
                    details={"family": family, "row": position, "field": "evidence"})
            if row.get("integration_status") == DEFERRED_ACTIVE_OWNER:
                raise FixtureMarkerRefused(
                    f"{family} row {position} is labelled deferred_active_owner",
                    code="fixture_markers_refused",
                    details={"family": family, "row": position,
                             "field": "integration_status"})
        counts[family] = len(rows)
    return counts


def _require_production_config(config: Any) -> ProductionConfig:
    if not isinstance(config, ProductionConfig):
        raise ProductionValidationError(
            "build_production_dataset requires a ProductionConfig",
            code="invalid_configuration")
    return config


def _require_non_fixture_providers(providers: Any) -> ProviderRegistry:
    if not isinstance(providers, ProviderRegistry):
        raise ProductionValidationError(
            "providers must be a ProviderRegistry",
            code="providers_invalid")
    if not providers.provider_ids():
        raise MissingComponentError(
            "no providers are registered; production mode has nothing to serve",
            code="providers_missing")
    for provider_id in providers.provider_ids():
        if isinstance(providers.get(provider_id), FixtureProvider):
            raise FixtureFallbackRefused(
                f"registered provider {provider_id!r} is a synthetic fixture provider",
                code="fixture_providers_refused",
                details={"provider_id": provider_id})
    return providers


def _require_snapshot(snapshot: Any) -> CatalogSnapshot:
    if snapshot is None:
        raise MissingComponentError(
            "no catalog snapshot was injected; production mode has no identity index",
            code="snapshot_missing")
    if not isinstance(snapshot, CatalogSnapshot) or not snapshot.dataset_revision:
        raise ProductionValidationError(
            "the injected snapshot is not a revisioned CatalogSnapshot",
            code="snapshot_invalid")
    return snapshot


def _require_features(features: Any) -> Any:
    if features is None:
        raise MissingComponentError(
            "no feature source was injected; materials, syllabuses and timetables "
            "would fall back to staged fixtures",
            code="invalid_assembly",
            details={"component": "features"})
    if isinstance(features, FixtureFeatureSource):
        raise FixtureFallbackRefused(
            "the fixture feature source is not a production component",
            code="fixture_feature_source_refused")
    validate_production_features(features)
    return features


def _resolve_operations_root(config: ProductionConfig,
                             operations_root: Any) -> Path | None:
    root = operations_root if operations_root is not None else config.operations_root
    if root is None:
        return None
    try:
        return ensure_within(root, config.deployment_root, "operations root")
    except PathOutsideRootError as exc:
        raise ProductionValidationError(
            "the operations root lies outside the configured deployment root",
            code="operations_root_outside_deployment",
            details={"cause": type(exc).__name__}) from exc


def build_production_dataset(config: ProductionConfig, *, providers: Any,
                             snapshot: Any, features: Any,
                             operations_root: str | Path | None = None,
                             operations_ttl: float | None = None,
                             operations_clock: Callable[[], Any] | None = None
                             ) -> Dataset:
    """Assemble the production :class:`Dataset` from injected real components.

    Fails closed, in this order, with a typed :class:`ProductionAssemblyError`:
    configuration, API key, provider registry (present, non-empty, non-fixture),
    snapshot, feature source (present, non-fixture, unmarked rows). An
    operations root is optional but must lie inside the deployment root; when
    absent, no operations view is built and ``/jobs/{id}`` degrades to the
    labelled deferred record (a release follow-up pinned by the W4a tests).
    """
    config = _require_production_config(config)
    if not str(config.api_key or "").strip():
        raise MissingConfigurationError(
            "production configuration requires an API key (set EXAMDATA_API_KEY)",
            code="api_key_missing")
    registry = _require_non_fixture_providers(providers)
    snapshot = _require_snapshot(snapshot)
    features = _require_features(features)
    resolved_root = _resolve_operations_root(config, operations_root)

    service: OperationsObservationService | None = None
    operations = None
    if resolved_root is not None:
        ttl = (DEFAULT_OPERATIONS_TTL_SECONDS if operations_ttl is None
               else operations_ttl)
        service = OperationsObservationService(
            resolved_root, entries=snapshot.entries, ttl_seconds=ttl,
            clock=operations_clock, dataset_revision=snapshot.dataset_revision)
        operations = service.observe()
    return Dataset(snapshot=snapshot, registry=registry, features=features,
                   available_revisions=(snapshot.dataset_revision,),
                   evidence=config.evidence_label, operations=operations,
                   operations_service=service)


def _operations_configured(config: ProductionConfig, operations_root: Any) -> bool:
    root = operations_root if operations_root is not None else config.operations_root
    return root is not None


@dataclass(frozen=True)
class _FamilySpec:
    family: str
    components: tuple[str, ...]
    fixture_implementation: str
    installed_local_implementation: str
    real_source_acceptance: str
    unavailable_behaviour: str


_FAILS_CLOSED = (
    "fails closed at assembly with a typed ProductionAssemblyError naming the "
    "missing component; fixture providers, fixture rows, sample content and "
    "static mock jobs are never substituted")

_FAMILY_SPECS: tuple[_FamilySpec, ...] = (
    _FamilySpec(
        "info", ("providers", "snapshot"),
        "create_app() default: fixture providers joined to the fixture snapshot; "
        "evidence `synthetic_fixture`",
        "the assembled Dataset; /info reports the injected registry, snapshot counts, "
        "revision and evidence label",
        "a non-fixture ProviderRegistry plus a CatalogSnapshot built from real output",
        _FAILS_CLOSED),
    _FamilySpec(
        "exam-systems", ("providers",),
        "fixture registry descriptors plus the declared toefl/gaokao unavailability",
        "assembled registry descriptors; unavailable systems stay declared, never invented",
        "any registered non-fixture provider contributes a descriptor; a system without "
        "a provider stays declared unavailable",
        _FAILS_CLOSED),
    _FamilySpec(
        "providers", ("providers",),
        "fixture provider descriptors (cie/edexcel/ielts synthetic JSON)",
        "assembled registry descriptors with capabilities, supported filters and "
        "limitations as registered",
        "descriptor rows of registered non-fixture providers only; fixture providers "
        "are refused at assembly",
        _FAILS_CLOSED),
    _FamilySpec(
        "courses", ("providers", "snapshot"),
        "fixture provider courses joined to the fixture snapshot index",
        "list/detail read the assembled Dataset (snapshot index plus live provider answers)",
        "a real provider answering `courses` whose native locators resolve in the "
        "injected snapshot",
        _FAILS_CLOSED),
    _FamilySpec(
        "syllabuses", ("features", "content_store"),
        "labelled synthetic rows with completeness `unknown` (deferred_active_owner)",
        "the same labelled deferred rows through the feature seam; the real owner "
        "integration stays deferred and is never implied",
        "a feature source implementing the five accessors whose syllabus rows carry a "
        "non-empty public_id and no synthetic markers; content samples must verify in "
        "the injected ContentStore",
        _FAILS_CLOSED),
    _FamilySpec(
        "containers", ("providers", "snapshot"),
        "fixture provider containers joined to the fixture snapshot index",
        "list/detail and nested resources/questions read the assembled Dataset",
        "a real provider answering `containers` whose entries resolve in the snapshot",
        _FAILS_CLOSED),
    _FamilySpec(
        "resources", ("providers", "snapshot", "content_store"),
        "provider resources plus verified synthetic samples for content rows",
        "list/detail from the Dataset; /resources/{id}/content streams verified samples "
        "only and is never fabricated",
        "real resources whose content samples pass ContentStore verification "
        "(sha256, byte size, PDF/PNG magic)",
        _FAILS_CLOSED),
    _FamilySpec(
        "questions", ("providers", "snapshot", "content_store"),
        "provider answers/regions; crops from verified synthetic crop samples",
        "list/detail/answers/regions from the Dataset; crop and audio follow declared "
        "availability only",
        "a real provider answering questions/answers/regions; crop samples must verify "
        "in the ContentStore",
        _FAILS_CLOSED),
    _FamilySpec(
        "assets", ("snapshot", "content_store"),
        "fixture snapshot asset entries; /assets/{id}/content from verified samples",
        "list/detail from the snapshot; content only when a verified sample exists",
        "asset entries in a real snapshot plus content samples that pass verification",
        _FAILS_CLOSED),
    _FamilySpec(
        "tags", (),
        "labelled empty list (TAG_FIXTURES is empty in this phase)",
        "labelled empty list; the route never 404s and never fabricates rows",
        "no real tag source exists in this phase; a future source plugs into the same "
        "route without an assembly change",
        "unavailable by design: an empty labelled list, never fabricated rows"),
    _FamilySpec(
        "materials", ("features", "content_store"),
        "labelled synthetic rows with completeness `unknown` (deferred_active_owner)",
        "the same labelled deferred rows through the feature seam; the real owner "
        "integration stays deferred and is never implied",
        "a feature source implementing the five accessors whose material rows carry a "
        "non-empty public_id and no synthetic markers; content samples must verify",
        _FAILS_CLOSED),
    _FamilySpec(
        "timetables", ("features",),
        "labelled synthetic season/event/window rows with declared unknown boundaries",
        "the same labelled deferred rows through the feature seam; null dates and "
        "unknown boundaries are preserved, never defaulted",
        "a feature source implementing the five accessors whose timetable rows keep "
        "system identity and carry no synthetic markers",
        _FAILS_CLOSED),
    _FamilySpec(
        "coverage", ("providers", "snapshot"),
        "provider coverage plus snapshot counts, and the read-only operations block "
        "when an operations root is configured",
        "assembled coverage; the operations block exists only with a configured "
        "operations root",
        "a real provider answering `coverage` plus snapshot counts; a scope without "
        "data stays declared",
        _FAILS_CLOSED),
    _FamilySpec(
        "gaps", ("providers", "snapshot"),
        "gaps derived from the fixture snapshot and providers",
        "gaps derived from the assembled Dataset",
        "derived from real snapshot/providers; an unscanned scope is reported, never "
        "flattened to `complete`",
        _FAILS_CLOSED),
    _FamilySpec(
        "jobs", ("operations",),
        "the labelled static deferred job record (job_synthetic_coverage)",
        "read-only operations observation of the configured root under a bounded TTL; "
        "a failed refresh keeps the last good view marked stale or unknown",
        "an operations root inside the deployment root; checkpoint files are observed "
        "read-only and nothing is ever started, resumed or cancelled",
        "without an operations root the assembly still succeeds but /jobs/{id} reaches "
        "only the labelled deferred fixture record; real job diagnostics are "
        "unavailable until a root is configured (release follow-up)"),
)

_COMPONENT_LABELS = {
    "providers": "non-fixture ProviderRegistry",
    "snapshot": "revisioned CatalogSnapshot",
    "features": "non-fixture feature source",
    "content_store": "verified ContentStore outside the fixture tree",
    "operations": "operations root inside the deployment root",
}


def _family_routes(family: str) -> list[str]:
    return [spec.capability for spec in links.ROUTE_SPECS
            if spec.capability.split(".", 1)[0] == family]


def production_capabilities(*, config: ProductionConfig | None = None,
                            providers: Any = None, snapshot: Any = None,
                            features: Any = None, content_store: Any = None,
                            operations_root: str | Path | None = None
                            ) -> tuple[dict[str, Any], ...]:
    """Per-family capability rows: requirements, gaps and acceptance rules.

    Availability is computed against the components actually supplied; a
    missing component names itself in ``missing`` and the family's honest
    unavailable behaviour. ``unavailable_by_design`` families (tags) take no
    components. This is the raw data of the W4 capability map.
    """
    presence = {
        "providers": isinstance(providers, ProviderRegistry) and bool(
            providers.provider_ids()),
        "snapshot": isinstance(snapshot, CatalogSnapshot) and bool(
            snapshot.dataset_revision),
        "features": features is not None and not isinstance(
            features, FixtureFeatureSource),
        "content_store": isinstance(content_store, ContentStore),
        "operations": _operations_configured(config, operations_root)
        if config is not None else operations_root is not None,
    }
    rows: list[dict[str, Any]] = []
    for spec in _FAMILY_SPECS:
        family = spec.family
        components = {name: bool(presence.get(name)) for name in spec.components}
        missing = [name for name in spec.components if not presence.get(name)]
        if not spec.components:
            status = "unavailable_by_design"
        elif missing:
            status = "missing_component"
        else:
            status = "available"
        rows.append({
            "family": family,
            "v2_routes": _family_routes(family),
            "components_required": list(spec.components),
            "components_present": components,
            "missing": missing,
            "status": status,
            "route_registration": {
                "registered": True,
                "capabilities": _family_routes(family),
                "registering_factory": "create_app" if family != "tags" else "create_app",
            },
            "fixture_implementation": spec.fixture_implementation,
            "installed_local_implementation": spec.installed_local_implementation,
            "real_source_acceptance": spec.real_source_acceptance,
            "unavailable_behaviour": spec.unavailable_behaviour,
            "missing_component_labels": {name: _COMPONENT_LABELS[name]
                                         for name in missing},
        })
    return tuple(rows)


@dataclass(frozen=True)
class ProductionAssembly:
    """A fully assembled production app input: dataset, store, capabilities."""

    config: ProductionConfig
    dataset: Dataset
    content_store: ContentStore
    capabilities: tuple[dict[str, Any], ...]
    mode: str = PRODUCTION_MODE


def assemble_production(config: ProductionConfig, *, providers: Any, snapshot: Any,
                        features: Any, content_store: Any,
                        operations_root: str | Path | None = None,
                        operations_ttl: float | None = None,
                        operations_clock: Callable[[], Any] | None = None
                        ) -> ProductionAssembly:
    """Assemble the complete production input from injected real components.

    Requires an explicit :class:`ContentStore` whose root lies outside the
    fixture tree; a fixture store or a fixture dataset is refused, never
    silently swapped for a real one.
    """
    config = _require_production_config(config)
    if not isinstance(content_store, ContentStore):
        raise MissingComponentError(
            "production assembly requires an explicit ContentStore",
            code="content_store_missing")
    if is_within(content_store.root, FIXTURE_ROOT):
        raise FixtureFallbackRefused(
            "the fixture content store is not a production component",
            code="fixture_content_store_refused")
    dataset = build_production_dataset(
        config, providers=providers, snapshot=snapshot, features=features,
        operations_root=operations_root, operations_ttl=operations_ttl,
        operations_clock=operations_clock)
    capabilities = production_capabilities(
        config=config, providers=providers, snapshot=snapshot, features=features,
        content_store=content_store, operations_root=operations_root)
    return ProductionAssembly(config=config, dataset=dataset,
                              content_store=content_store,
                              capabilities=capabilities)


def create_production_app(assembly: ProductionAssembly) -> Any:
    """Build the app for an assembled production input.

    Refuses a fixture dataset (no production app may serve one) and labels the
    app state with :data:`PRODUCTION_MODE` and :data:`PRODUCTION_BANNER`.
    """
    from .app import create_app

    if not isinstance(assembly, ProductionAssembly):
        raise ProductionValidationError(
            "create_production_app requires a ProductionAssembly",
            code="invalid_assembly")
    if assembled_mode(assembly.dataset) == FIXTURE_MODE:
        raise FixtureFallbackRefused(
            "refusing to serve a synthetic-fixture dataset through the production "
            "app factory",
            code="fixture_dataset_refused")
    app = create_app(dataset=assembly.dataset, content_store=assembly.content_store)
    app.state.assembly_mode = PRODUCTION_MODE
    app.state.assembly_banner = PRODUCTION_BANNER
    app.state.assembly = assembly
    return app


__all__ = [
    "FIXTURE_MODE",
    "PRODUCTION_MODE",
    "FIXTURE_BANNER",
    "PRODUCTION_BANNER",
    "FIXTURE_EVIDENCE",
    "PRODUCTION_DEFAULT_EVIDENCE",
    "ProductionAssemblyError",
    "MissingComponentError",
    "MissingConfigurationError",
    "FixtureFallbackRefused",
    "FixtureMarkerRefused",
    "ProductionValidationError",
    "assembled_mode",
    "describe_assembly",
    "ProductionConfig",
    "build_fixture_dataset",
    "create_fixture_app",
    "validate_production_features",
    "build_production_dataset",
    "production_capabilities",
    "ProductionAssembly",
    "assemble_production",
    "create_production_app",
]
