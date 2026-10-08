"""The provider protocol and descriptor (plan 4.1, A05).

A provider adapts one examination system's storage to the ten read capabilities.
It never guesses: it declares what it supports and what filters it can
interpret, so the registry can reject an unsupported operation *before* dispatch
and never silently drop a filter it does not understand (plan 5.7).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, runtime_checkable

from ..contracts.enums import ExamSystem
from .capabilities import CAPABILITIES, Availability, Capability
from .results import ProviderResult


@dataclass(frozen=True)
class ProviderDescriptor:
    """What a provider is and what it can do; safe to publish (plan 5.4)."""

    provider_id: str
    exam_system: ExamSystem
    display_name: str
    capabilities: frozenset[Capability]
    supported_filters: Mapping[Capability, frozenset[str]] = field(default_factory=dict)
    availability: Availability = Availability.AVAILABLE
    limitations: tuple[str, ...] = ()

    def supports(self, capability: Capability) -> bool:
        return Capability.coerce(capability) in self.capabilities

    def filters_for(self, capability: Capability) -> frozenset[str]:
        return frozenset(self.supported_filters.get(Capability.coerce(capability), frozenset()))

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "exam_system": self.exam_system.value,
            "display_name": self.display_name,
            "availability": self.availability.value,
            "capabilities": [c.value for c in CAPABILITIES if c in self.capabilities],
            "supported_filters": {
                c.value: sorted(self.filters_for(c)) for c in CAPABILITIES if c in self.capabilities
            },
            "limitations": list(self.limitations),
        }


@runtime_checkable
class Provider(Protocol):
    """One examination system's read adapter.

    `query` is the single dispatch entry point; `capability` selects the
    operation. A provider that does not implement a capability must still answer
    with a typed unsupported result rather than raising.
    """

    descriptor: ProviderDescriptor

    def query(self, capability: Capability, *, filters: Mapping[str, Any] | None = None,
              target: str | None = None) -> ProviderResult:  # pragma: no cover - protocol
        ...


__all__ = ["ProviderDescriptor", "Provider"]
