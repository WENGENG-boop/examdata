"""The provider registry: capability filtering, alias routing, dispatch (A05).

Dispatch order is fixed and testable (plan A05):

1. unknown provider id            -> failed(unknown_provider)
2. capability not declared        -> unsupported        (capability filtering precedes dispatch)
3. provider unavailable           -> unavailable
4. uninterpretable filter         -> filter_rejected     (never silently ignored, plan 5.7)
5. call the provider; a raised exception becomes failed (sanitized)

Alias routing is explicit: a native alias belongs to exactly one provider. An
unknown alias is an error, never a default to the first registered provider, and
a conflicting rebind is refused. This is what stops an IELTS id (which may start
with `cambridge:`) from being routed to CIE by accident (plan 4.1).
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping

from ..contracts.canonical import normalize_alias
from .capabilities import Availability, Capability
from .protocol import Provider, ProviderDescriptor
from .results import DispatchResult, ProviderResult


class ProviderRegistryError(ValueError):
    """Base class for registry misuse."""


class DuplicateProviderError(ProviderRegistryError):
    pass


class UnknownProviderError(ProviderRegistryError):
    pass


class AliasRoutingError(ProviderRegistryError):
    pass


class UnknownAliasError(ProviderRegistryError):
    pass


class ProviderRegistry:
    """Registers providers, filters by capability, routes aliases and dispatches."""

    def __init__(self) -> None:
        self._providers: dict[str, Provider] = {}
        self._order: list[str] = []
        self._aliases: dict[str, str] = {}
        self._alias_original: dict[str, str] = {}

    # -- registration -------------------------------------------------------- #
    def register(self, provider: Provider) -> ProviderDescriptor:
        descriptor = provider.descriptor
        pid = descriptor.provider_id
        if not pid:
            raise ProviderRegistryError("provider descriptor has an empty provider_id")
        if pid in self._providers:
            raise DuplicateProviderError(f"provider {pid!r} is already registered")
        self._providers[pid] = provider
        self._order.append(pid)
        return descriptor

    def unregister(self, provider_id: str) -> None:
        if provider_id not in self._providers:
            raise UnknownProviderError(f"provider {provider_id!r} is not registered")
        del self._providers[provider_id]
        self._order.remove(provider_id)
        for key in [k for k, v in self._aliases.items() if v == provider_id]:
            del self._aliases[key]
            self._alias_original.pop(key, None)

    def get(self, provider_id: str) -> Provider:
        try:
            return self._providers[provider_id]
        except KeyError as exc:
            raise UnknownProviderError(f"provider {provider_id!r} is not registered") from exc

    def provider_ids(self) -> list[str]:
        return list(self._order)

    def descriptors(self) -> list[ProviderDescriptor]:
        return [self._providers[pid].descriptor for pid in self._order]

    # -- alias routing ------------------------------------------------------- #
    def register_alias(self, alias: str, provider_id: str) -> None:
        if provider_id not in self._providers:
            raise UnknownProviderError(
                f"cannot bind alias {alias!r}: provider {provider_id!r} is not registered")
        key = normalize_alias(alias)
        if not key:
            raise ProviderRegistryError("cannot register an empty alias")
        owner = self._aliases.get(key)
        if owner is not None and owner != provider_id:
            raise AliasRoutingError(
                f"alias {alias!r} already routes to {owner!r}; refusing to rebind to {provider_id!r}")
        self._aliases[key] = provider_id
        self._alias_original.setdefault(key, alias)

    def route(self, alias: str) -> str:
        """Return the provider id that owns `alias`; raise if it owns none."""
        key = normalize_alias(alias)
        try:
            return self._aliases[key]
        except KeyError as exc:
            raise UnknownAliasError(f"no provider owns alias {alias!r}") from exc

    def owns_alias(self, alias: str) -> bool:
        return normalize_alias(alias) in self._aliases

    def aliases_for(self, provider_id: str) -> list[str]:
        return sorted(self._alias_original[k] for k, v in self._aliases.items()
                      if v == provider_id)

    # -- capability filtering ------------------------------------------------ #
    def capability_providers(self, capability: Capability) -> list[str]:
        """Provider ids that declare `capability`, in registration order."""
        cap = Capability.coerce(capability)
        return [pid for pid in self._order if self._providers[pid].descriptor.supports(cap)]

    # -- dispatch ------------------------------------------------------------ #
    def dispatch(self, capability: Capability, *, provider_ids: Iterable[str] | None = None,
                 filters: Mapping[str, Any] | None = None,
                 target: str | None = None) -> DispatchResult:
        cap = Capability.coerce(capability)
        wanted_filters = dict(filters or {})
        requested = list(provider_ids) if provider_ids is not None else list(self._order)

        results: list[ProviderResult] = []
        for pid in requested:
            provider = self._providers.get(pid)
            if provider is None:
                results.append(ProviderResult.failed(
                    pid, cap.value, error_code="unknown_provider",
                    detail=f"provider {pid!r} is not registered"))
                continue

            descriptor = provider.descriptor
            if not descriptor.supports(cap):
                results.append(ProviderResult.unsupported(
                    pid, cap.value,
                    detail=f"provider {pid!r} does not implement {cap.value}"))
                continue
            if descriptor.availability is Availability.UNAVAILABLE:
                results.append(ProviderResult.unavailable(
                    pid, cap.value,
                    detail=f"provider {pid!r} is registered but not currently available"))
                continue

            unsupported = sorted(k for k in wanted_filters if k not in descriptor.filters_for(cap))
            if unsupported:
                results.append(ProviderResult.filter_rejected(
                    pid, cap.value, filter_key=unsupported[0],
                    detail=f"provider {pid!r} cannot interpret filter(s) {unsupported} for {cap.value}"))
                continue

            try:
                result = provider.query(cap, filters=wanted_filters, target=target)
            except Exception as exc:  # noqa: BLE001 - a provider must never crash dispatch
                results.append(ProviderResult.failed(
                    pid, cap.value, detail=f"{type(exc).__name__}: {exc}"))
                continue

            if not isinstance(result, ProviderResult):
                results.append(ProviderResult.failed(
                    pid, cap.value, detail="provider returned a non-ProviderResult value"))
                continue
            results.append(result)

        return DispatchResult(capability=cap.value, results=results)


__all__ = [
    "ProviderRegistry",
    "ProviderRegistryError",
    "DuplicateProviderError",
    "UnknownProviderError",
    "AliasRoutingError",
    "UnknownAliasError",
]
