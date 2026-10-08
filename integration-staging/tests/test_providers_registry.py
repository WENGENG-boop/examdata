"""A05 registry tests: capability filtering, alias routing, dispatch semantics.

The registry is the guard that stops an unsupported operation, an unavailable
provider or an uninterpretable filter from ever being mistaken for a genuine
empty result (plan A05 pass condition: no fake empty successes, no accidental
CIE routing for IELTS ids).
"""
from __future__ import annotations

import pytest

from examdata_integration.contracts.enums import ExamSystem
from examdata_integration.providers import (
    AliasRoutingError,
    Availability,
    Capability,
    DuplicateProviderError,
    FailingProvider,
    NullProvider,
    ProviderDescriptor,
    ProviderRegistry,
    ProviderResult,
    UnavailableProvider,
    UnknownAliasError,
    UnknownProviderError,
)


class SpyProvider:
    """Records whether dispatch actually called it."""

    def __init__(self, provider_id="spy", capabilities=(Capability.DISCOVERY,),
                 filters=None, result=None, availability=Availability.AVAILABLE):
        self.calls = []
        self.descriptor = ProviderDescriptor(
            provider_id=provider_id, exam_system=ExamSystem.CIE, display_name="spy",
            capabilities=frozenset(capabilities),
            supported_filters={c: frozenset(filters or []) for c in capabilities},
            availability=availability)
        self._result = result

    def query(self, capability, *, filters=None, target=None):
        cap = Capability.coerce(capability)
        self.calls.append((cap, dict(filters or {}), target))
        if self._result is not None:
            return self._result
        return ProviderResult.success(self.descriptor.provider_id, cap.value,
                                      items=[{"called": True}])


def test_register_list_and_descriptors():
    registry = ProviderRegistry()
    spy = SpyProvider()
    registry.register(spy)
    assert registry.provider_ids() == ["spy"]
    assert registry.descriptors()[0].provider_id == "spy"
    assert registry.get("spy") is spy


def test_duplicate_registration_is_refused():
    registry = ProviderRegistry()
    registry.register(SpyProvider())
    with pytest.raises(DuplicateProviderError):
        registry.register(SpyProvider())


def test_unknown_provider_in_dispatch_is_failed():
    registry = ProviderRegistry()
    registry.register(SpyProvider())
    result = registry.dispatch(Capability.DISCOVERY, provider_ids=["spy", "ghost"])
    ghost = [r for r in result.results if r.provider_id == "ghost"][0]
    assert ghost.status.value == "failed"
    assert ghost.error_code == "unknown_provider"
    assert result.status == "partial"  # spy still succeeded


def test_capability_filtering_precedes_dispatch():
    registry = ProviderRegistry()
    spy = SpyProvider(capabilities=(Capability.DISCOVERY,))
    registry.register(spy)
    result = registry.dispatch(Capability.COURSES, provider_ids=["spy"])
    assert result.status == "error"
    assert result.error["code"] == "unsupported_capability"
    assert spy.calls == [], "an unsupported capability must not reach the provider"


def test_unsupported_is_not_an_empty_success():
    registry = ProviderRegistry()
    registry.register(SpyProvider(capabilities=(Capability.DISCOVERY,)))
    result = registry.dispatch(Capability.TAGS)
    assert result.items == []
    assert result.status == "error"
    assert result.error["code"] == "unsupported_capability"


def test_filter_rejection_precedes_dispatch():
    registry = ProviderRegistry()
    spy = SpyProvider(capabilities=(Capability.QUESTIONS,), filters=["subject"])
    registry.register(spy)
    result = registry.dispatch(Capability.QUESTIONS, provider_ids=["spy"], filters={"year": 2024})
    provider_row = result.results[0]
    assert provider_row.status.value == "filter_rejected"
    assert provider_row.filter_key == "year"
    assert result.error["code"] == "unsupported_filter"
    assert spy.calls == [], "an uninterpretable filter must not reach the provider"


def test_interpretable_filter_reaches_provider():
    registry = ProviderRegistry()
    spy = SpyProvider(capabilities=(Capability.QUESTIONS,), filters=["subject"])
    registry.register(spy)
    result = registry.dispatch(Capability.QUESTIONS, provider_ids=["spy"],
                               filters={"subject": "9999"})
    assert result.status == "ok"
    assert spy.calls == [(Capability.QUESTIONS, {"subject": "9999"}, None)]


def test_empty_success_is_ok_and_carries_no_error():
    registry = ProviderRegistry()
    registry.register(NullProvider())
    result = registry.dispatch(Capability.DISCOVERY, provider_ids=["null_fixture"])
    assert result.status == "ok"
    assert result.items == []
    assert result.error is None


def test_unavailable_provider_is_error_alone_and_partial_with_an_available_one():
    registry = ProviderRegistry()
    registry.register(UnavailableProvider())
    registry.register(SpyProvider(provider_id="spy", capabilities=(Capability.COURSES,)))

    alone = registry.dispatch(Capability.COURSES, provider_ids=["optional_unavailable"])
    assert alone.status == "error"
    assert alone.error["code"] == "provider_unavailable"
    assert alone.error["retryable"] is True

    mixed = registry.dispatch(Capability.COURSES,
                              provider_ids=["optional_unavailable", "spy"])
    assert mixed.status == "partial"
    assert len(mixed.items) == 1
    assert any("optional_unavailable" in w for w in mixed.warnings)


def test_all_providers_fail_is_an_error_not_empty_200():
    registry = ProviderRegistry()
    registry.register(FailingProvider())
    registry.register(NullProvider(provider_id="null", capabilities=frozenset({Capability.COURSES})))
    result = registry.dispatch(Capability.COURSES, provider_ids=["failing_fixture"])
    assert result.status == "error"
    assert result.items == []
    assert result.error["code"] == "provider_failed"


def test_provider_exception_is_sanitized():
    registry = ProviderRegistry()
    registry.register(FailingProvider())
    result = registry.dispatch(Capability.COURSES, provider_ids=["failing_fixture"])
    provider_row = result.results[0]
    assert provider_row.status.value == "failed"
    assert "RuntimeError" in provider_row.detail
    # the public aggregate error must not leak the local path the provider raised with
    assert "private" not in (result.error["message"] or "")


def test_non_providerresult_is_failed():
    class BadProvider:
        def __init__(self):
            self.descriptor = ProviderDescriptor(
                provider_id="bad", exam_system=ExamSystem.CIE, display_name="bad",
                capabilities=frozenset({Capability.DISCOVERY}))

        def query(self, capability, *, filters=None, target=None):
            return "not a result"

    registry = ProviderRegistry()
    registry.register(BadProvider())
    result = registry.dispatch(Capability.DISCOVERY)
    assert result.results[0].status.value == "failed"


def test_no_provider_requested_is_explicit_error():
    registry = ProviderRegistry()
    result = registry.dispatch(Capability.COURSES, provider_ids=[])
    assert result.status == "error"
    assert result.error["code"] == "no_provider_requested"


def test_error_precedence_is_deterministic():
    registry = ProviderRegistry()
    registry.register(SpyProvider(provider_id="unsupported",
                                  capabilities=(Capability.DISCOVERY,)))
    registry.register(FailingProvider())
    result = registry.dispatch(Capability.COURSES,
                               provider_ids=["failing_fixture", "unsupported"])
    # unsupported outranks failed, regardless of request order
    assert result.error["code"] == "unsupported_capability"


# --------------------------------------------------------------------------- #
# alias routing
# --------------------------------------------------------------------------- #
def test_alias_routes_to_its_owner_and_is_casefolded():
    registry = ProviderRegistry()
    registry.register(SpyProvider(provider_id="cie", capabilities=(Capability.COURSES,)))
    registry.register(SpyProvider(provider_id="ielts", capabilities=(Capability.COURSES,)))
    registry.register_alias("cambridge:book-1", "ielts")
    assert registry.route("cambridge:book-1") == "ielts"
    assert registry.route("  CAMBRIDGE:Book-1  ") == "ielts"
    assert registry.aliases_for("ielts") == ["cambridge:book-1"]


def test_alias_does_not_default_to_first_provider():
    registry = ProviderRegistry()
    registry.register(SpyProvider(provider_id="cie", capabilities=(Capability.COURSES,)))
    registry.register(SpyProvider(provider_id="ielts", capabilities=(Capability.COURSES,)))
    with pytest.raises(UnknownAliasError):
        registry.route("cambridge:book-1")


def test_alias_conflict_is_refused():
    registry = ProviderRegistry()
    registry.register(SpyProvider(provider_id="cie", capabilities=(Capability.COURSES,)))
    registry.register(SpyProvider(provider_id="ielts", capabilities=(Capability.COURSES,)))
    registry.register_alias("shared", "ielts")
    with pytest.raises(AliasRoutingError):
        registry.register_alias("shared", "cie")
    assert registry.route("shared") == "ielts"


def test_alias_for_unknown_provider_is_refused():
    registry = ProviderRegistry()
    with pytest.raises(UnknownProviderError):
        registry.register_alias("x", "ghost")


def test_unregister_removes_aliases():
    registry = ProviderRegistry()
    registry.register(SpyProvider(provider_id="ielts", capabilities=(Capability.COURSES,)))
    registry.register_alias("book-1", "ielts")
    registry.unregister("ielts")
    assert not registry.owns_alias("book-1")
    with pytest.raises(UnknownProviderError):
        registry.get("ielts")


def test_capability_providers_filters_by_declared_capability():
    registry = ProviderRegistry()
    registry.register(SpyProvider(provider_id="a", capabilities=(Capability.COURSES,)))
    registry.register(SpyProvider(provider_id="b", capabilities=(Capability.DISCOVERY,)))
    registry.register(SpyProvider(provider_id="c", capabilities=(Capability.COURSES,)))
    assert registry.capability_providers(Capability.COURSES) == ["a", "c"]
    assert registry.capability_providers(Capability.TAGS) == []
