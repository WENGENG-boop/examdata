"""W4a — the explicit fixture/production assembly seam (``api/assembly.py``).

The brief (W4 part A.1) asks for two clearly separated dataset assembly paths:
the private fixture path the frozen probe keeps seeing, and a production path
that requires injected real components and **fails closed** with typed,
sanitized errors - never falling back to ``fixture_providers()``, fixture
feature sources, sample content or static mock jobs.

Every production-path check here uses injected synthetic components (a
non-fixture provider, a computed snapshot, a stub feature source, a verified
sample-free content store) inside the test's own temporary deployment root;
no production claim is made about real data.

On the frozen parent (no ``api/assembly.py``) each test fails through the lazy
module accessor instead of erroring at collection.
"""
from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

import pytest

import b07r2_common as c  # import first: pins EXAMDATA_INTEGRATION_ROOT + candidate origin
from examdata.integration.contracts.enums import ExamSystem
from examdata.integration.providers.capabilities import Capability
from examdata.integration.providers.fixtures import FixtureProvider
from examdata.integration.providers.protocol import ProviderDescriptor
from fastapi.testclient import TestClient

import w4a_common as w

_IMPORT_ERROR: BaseException | None = None
try:
    assembly: Any = importlib.import_module("examdata.integration.api.assembly")
except Exception as exc:  # pragma: no cover - RED on the frozen parent
    assembly = None
    _IMPORT_ERROR = exc


def _assembly() -> Any:
    if assembly is None:
        pytest.fail(f"api.assembly is not implemented on this revision: {_IMPORT_ERROR!r}")
    return assembly


def _deployment(tmp_path: Path) -> Path:
    root = tmp_path / "deployment"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _assemble(tmp_path: Path) -> Any:
    a = _assembly()
    deployment = _deployment(tmp_path)
    operations_root = deployment / "operations"
    operations_root.mkdir(exist_ok=True)
    return a.assemble_production(
        w.production_config(deployment),
        providers=w.synthetic_registry(),
        snapshot=w.synthetic_snapshot(),
        features=w.StubFeatureSource(),
        content_store=w.empty_content_store(tmp_path / "content"),
        operations_root=operations_root,
    )


# --------------------------------------------------------------------------- #
# fixture path: explicit, labelled, probe-compatible
# --------------------------------------------------------------------------- #
def test_fixture_path_is_explicitly_labelled() -> None:
    a = _assembly()
    dataset = a.build_fixture_dataset(operations_root=None)
    assert a.assembled_mode(dataset) == a.FIXTURE_MODE
    description = a.describe_assembly(dataset)
    assert description["mode"] == a.FIXTURE_MODE
    assert description["banner"] == a.FIXTURE_BANNER
    assert "FIXTURE" in description["banner"]
    assert description["evidence"] == "synthetic_fixture"
    assert description["revision"] == dataset.revision
    assert description["counts"] == dict(dataset.snapshot.counts)


def test_fixture_app_is_labelled_and_serves_synthetic_evidence() -> None:
    a = _assembly()
    app = a.create_fixture_app(operations_root=None)
    assert app.state.assembly_mode == a.FIXTURE_MODE
    assert app.state.assembly_banner == a.FIXTURE_BANNER
    client = TestClient(app)
    payload = client.get("/api/v2/info").json()
    assert payload["data"]["evidence"] == "synthetic_fixture"
    assert payload["data"]["capabilities"]["available"]


def test_fixture_builder_delegates_to_the_untouched_default_dataset(
        monkeypatch: pytest.MonkeyPatch) -> None:
    a = _assembly()
    calls: list[dict[str, Any]] = []

    def _fake_default(**kwargs: Any) -> str:
        calls.append(dict(kwargs))
        return "sentinel-dataset"

    monkeypatch.setattr(a, "default_dataset", _fake_default)
    assert a.build_fixture_dataset(operations_root=None) == "sentinel-dataset"
    assert calls == [{"operations_root": None}]


# --------------------------------------------------------------------------- #
# production path: assembled from injected synthetic components
# --------------------------------------------------------------------------- #
def test_production_assembly_with_injected_components(tmp_path: Path) -> None:
    a = _assembly()
    assembled = _assemble(tmp_path)
    assert assembled.mode == a.PRODUCTION_MODE
    dataset = assembled.dataset
    assert a.assembled_mode(dataset) == a.PRODUCTION_MODE
    assert dataset.evidence == a.PRODUCTION_DEFAULT_EVIDENCE == "real_source"
    assert dataset.revision == dataset.snapshot.dataset_revision
    assert dataset.available_revisions == (dataset.snapshot.dataset_revision,)
    assert assembled.content_store.problems == []
    statuses = {row["family"]: row["status"] for row in assembled.capabilities}
    assert statuses["info"] == "available"
    assert statuses["jobs"] == "available"
    assert statuses["tags"] == "unavailable_by_design"


def test_create_production_app_serves_the_injected_dataset(tmp_path: Path) -> None:
    a = _assembly()
    assembled = _assemble(tmp_path)
    app = a.create_production_app(assembled)
    assert app.state.assembly_mode == a.PRODUCTION_MODE
    assert app.state.assembly_banner == a.PRODUCTION_BANNER
    client = TestClient(app)
    info = client.get("/api/v2/info").json()
    assert info["data"]["evidence"] == "real_source"
    assert info["data"]["dataset_revision"] == assembled.dataset.revision


def test_production_envelope_keeps_declared_system_unavailability(tmp_path: Path) -> None:
    a = _assembly()
    assembled = _assemble(tmp_path)
    client = TestClient(a.create_production_app(assembled))
    payload = client.get("/api/v2/exam-systems").json()
    systems = {row["system"]: row for row in payload["data"]["items"]}
    assert systems["cie"]["evidence"] == "real_source"
    assert systems["toefl"]["availability"] == "unavailable"
    assert systems["gaokao"]["availability"] == "unavailable"


# --------------------------------------------------------------------------- #
# fail-closed: configuration
# --------------------------------------------------------------------------- #
def test_missing_api_key_fails_closed(tmp_path: Path) -> None:
    a = _assembly()
    with pytest.raises(a.MissingConfigurationError) as excinfo:
        a.ProductionConfig(deployment_root=str(tmp_path), api_key="")
    assert excinfo.value.code == "api_key_missing"
    with pytest.raises(a.MissingConfigurationError) as excinfo:
        a.ProductionConfig.from_environment(env={}, deployment_root=tmp_path)
    assert excinfo.value.code == "api_key_missing"


def test_configuration_rejects_empty_root_and_fixture_label(tmp_path: Path) -> None:
    a = _assembly()
    with pytest.raises(a.ProductionValidationError) as excinfo:
        a.ProductionConfig(deployment_root="", api_key="sk-w4a-x")
    assert excinfo.value.code == "invalid_configuration"
    with pytest.raises(a.FixtureMarkerRefused) as excinfo:
        a.ProductionConfig(deployment_root=str(tmp_path), api_key="sk-w4a-x",
                           evidence_label="synthetic_fixture")
    assert excinfo.value.code == "fixture_markers_refused"


def test_from_environment_reads_private_settings(tmp_path: Path) -> None:
    a = _assembly()
    config = a.ProductionConfig.from_environment(
        env={"EXAMDATA_API_KEY": "sk-w4a-env-0000",
             "EXAMDATA_NETWORK_MODE": "offline",
             "EXAMDATA_OPERATIONS_ROOT": str(tmp_path / "ops")},
        deployment_root=tmp_path)
    assert config.api_key == "sk-w4a-env-0000"
    assert config.network_mode == "offline"
    assert Path(config.deployment_root).is_absolute()
    assert config.operations_root == str(tmp_path / "ops")
    assert config.evidence_label == a.PRODUCTION_DEFAULT_EVIDENCE


# --------------------------------------------------------------------------- #
# fail-closed: components
# --------------------------------------------------------------------------- #
class _FakeFixtureProvider(FixtureProvider):
    """A real FixtureProvider instance that loads no file (descriptor only).

    ``FixtureProvider.__init__`` reads a synthetic fixture file; overriding it
    keeps ``isinstance(provider, FixtureProvider)`` true - which is exactly what
    the production path must refuse - without touching any fixture data.
    """

    provider_id = "w4a_fake_fixture_provider"

    def __init__(self) -> None:
        self.descriptor = ProviderDescriptor(
            provider_id=self.provider_id,
            exam_system=ExamSystem.CIE,
            display_name="W4a fake fixture provider",
            capabilities=frozenset({Capability.COURSES}),
        )

    def query(self, capability: Any, **kwargs: Any) -> Any:  # pragma: no cover
        raise AssertionError("a fixture provider must never be queried in production mode")


def _fixture_provider_instance() -> Any:
    return _FakeFixtureProvider()


def test_production_refuses_invalid_and_missing_components(tmp_path: Path) -> None:
    a = _assembly()
    config = w.production_config(_deployment(tmp_path))
    snapshot = w.synthetic_snapshot()
    registry = w.synthetic_registry()
    features = w.StubFeatureSource()
    from examdata.integration.catalog.model import CatalogSnapshot

    with pytest.raises(a.ProductionValidationError) as excinfo:
        a.build_production_dataset("not-a-config", providers=registry,
                                   snapshot=snapshot, features=features)
    assert excinfo.value.code == "invalid_configuration"

    with pytest.raises(a.ProductionValidationError) as excinfo:
        a.build_production_dataset(config, providers="not-a-registry",
                                   snapshot=snapshot, features=features)
    assert excinfo.value.code == "providers_invalid"

    with pytest.raises(a.MissingComponentError) as excinfo:
        a.build_production_dataset(config, providers=w.empty_registry(),
                                   snapshot=snapshot, features=features)
    assert excinfo.value.code == "providers_missing"
    assert isinstance(excinfo.value, a.ProductionAssemblyError)

    with pytest.raises(a.FixtureFallbackRefused) as excinfo:
        a.build_production_dataset(config,
                                   providers=w.synthetic_registry(
                                       w.SyntheticProvider("w4a_mixed_provider"),
                                       _fixture_provider_instance()),
                                   snapshot=snapshot, features=features)
    assert excinfo.value.code == "fixture_providers_refused"
    assert excinfo.value.details == {"provider_id": "w4a_fake_fixture_provider"}

    with pytest.raises(a.MissingComponentError) as excinfo:
        a.build_production_dataset(config, providers=registry, snapshot=None,
                                   features=features)
    assert excinfo.value.code == "snapshot_missing"

    with pytest.raises(a.ProductionValidationError) as excinfo:
        a.build_production_dataset(config, providers=registry,
                                   snapshot=CatalogSnapshot(), features=features)
    assert excinfo.value.code == "snapshot_invalid"


def test_production_refuses_fixture_feature_sources_and_markers(tmp_path: Path) -> None:
    a = _assembly()
    config = w.production_config(_deployment(tmp_path))
    snapshot = w.synthetic_snapshot()
    registry = w.synthetic_registry()
    from examdata.integration.adapters.active_owner import FixtureFeatureSource

    fixture_features = FixtureFeatureSource(
        syllabuses=[], materials=[], timetable_seasons=[], timetable_events=[],
        timetable_windows=[])
    with pytest.raises(a.FixtureFallbackRefused) as excinfo:
        a.build_production_dataset(config, providers=registry, snapshot=snapshot,
                                   features=fixture_features)
    assert excinfo.value.code == "fixture_feature_source_refused"

    with pytest.raises(a.MissingComponentError) as excinfo:
        a.build_production_dataset(config, providers=registry, snapshot=snapshot,
                                   features=None)
    assert excinfo.value.code == "invalid_assembly"

    with pytest.raises(a.ProductionValidationError) as excinfo:
        a.build_production_dataset(config, providers=registry, snapshot=snapshot,
                                   features=w.MissingAccessorSource())
    assert excinfo.value.code == "invalid_assembly"
    assert excinfo.value.details["family"] == "timetable_windows"

    polluted_rows = {"syllabuses": [{
        "public_id": "syllabus:w4a:polluted", "system": "cie",
        "evidence": "synthetic_fixture",
        "integration_status": "deferred_active_owner"}]}
    with pytest.raises(a.FixtureMarkerRefused) as excinfo:
        a.build_production_dataset(config, providers=registry, snapshot=snapshot,
                                   features=w.StubFeatureSource(polluted_rows))
    assert excinfo.value.code == "fixture_markers_refused"
    assert excinfo.value.details == {"family": "syllabuses", "row": 0,
                                     "field": "evidence"}

    deferred_rows = {"syllabuses": [{
        "public_id": "syllabus:w4a:deferred", "system": "cie",
        "integration_status": "deferred_active_owner"}]}
    with pytest.raises(a.FixtureMarkerRefused) as excinfo:
        a.build_production_dataset(config, providers=registry, snapshot=snapshot,
                                   features=w.StubFeatureSource(deferred_rows))
    assert excinfo.value.details["field"] == "integration_status"


def test_production_refuses_operations_root_outside_deployment(tmp_path: Path) -> None:
    a = _assembly()
    config = w.production_config(_deployment(tmp_path))
    outside = tmp_path / "outside-operations"
    outside.mkdir()
    with pytest.raises(a.ProductionValidationError) as excinfo:
        a.build_production_dataset(config, providers=w.synthetic_registry(),
                                   snapshot=w.synthetic_snapshot(),
                                   features=w.StubFeatureSource(),
                                   operations_root=outside)
    assert excinfo.value.code == "operations_root_outside_deployment"
    assert str(outside) not in excinfo.value.message


def test_assemble_production_requires_a_non_fixture_store(tmp_path: Path) -> None:
    a = _assembly()
    config = w.production_config(_deployment(tmp_path))
    registry = w.synthetic_registry()
    snapshot = w.synthetic_snapshot()
    features = w.StubFeatureSource()

    with pytest.raises(a.MissingComponentError) as excinfo:
        a.assemble_production(config, providers=registry, snapshot=snapshot,
                              features=features, content_store=None)
    assert excinfo.value.code == "content_store_missing"

    with pytest.raises(a.FixtureFallbackRefused) as excinfo:
        a.assemble_production(config, providers=registry, snapshot=snapshot,
                              features=features, content_store=w.fixture_content_store())
    assert excinfo.value.code == "fixture_content_store_refused"
    assert "fixture" in excinfo.value.message.lower()


def test_create_production_app_refuses_a_fixture_dataset(tmp_path: Path) -> None:
    a = _assembly()
    fixture_dataset = a.build_fixture_dataset(operations_root=None)
    bogus = a.ProductionAssembly(
        config=w.production_config(_deployment(tmp_path)),
        dataset=fixture_dataset,
        content_store=w.empty_content_store(tmp_path / "content"),
        capabilities=())
    with pytest.raises(a.FixtureFallbackRefused) as excinfo:
        a.create_production_app(bogus)
    assert excinfo.value.code == "fixture_dataset_refused"
    with pytest.raises(a.ProductionValidationError) as excinfo:
        a.create_production_app("not-an-assembly")
    assert excinfo.value.code == "invalid_assembly"


# --------------------------------------------------------------------------- #
# typed, sanitized errors
# --------------------------------------------------------------------------- #
def test_assembly_errors_are_typed_and_sanitized() -> None:
    a = _assembly()
    leaky = ("failed reading C:\\Users\\weo\\private\\secret.db with "
             "token REDACTED_LOCAL_CREDENTIAL")
    error = a.ProductionValidationError(leaky)
    text = str(error)
    assert "C:\\Users\\weo\\private" not in text
    assert "REDACTED_LOCAL_CREDENTIAL" not in text
    assert "<path>" in text
    assert "token=<redacted>" in text
    assert error.code == "invalid_assembly"
    assert error.to_dict() == {"code": "invalid_assembly", "message": text,
                               "details": {}}
    assert isinstance(error, a.ProductionAssemblyError)
    assert issubclass(a.FixtureFallbackRefused, a.ProductionAssemblyError)
    assert issubclass(a.MissingConfigurationError, a.ProductionAssemblyError)
    assert issubclass(a.FixtureMarkerRefused, a.ProductionAssemblyError)
    assert issubclass(a.MissingComponentError, a.ProductionAssemblyError)
