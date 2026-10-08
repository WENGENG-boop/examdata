"""Provider capabilities (plan 3.3, 5.4, A05).

A *capability* is one read operation a provider may implement. The ten values
below are the plan's operation list: discovery, courses, containers, questions,
answers, resources, assets, regions, tags, coverage. A provider declares which
it implements; anything it does not declare is an explicitly unsupported
operation, never an empty success (plan A05 pass condition).

Stdlib only. Nothing here reads the original project, the network, or a database.
"""
from __future__ import annotations

from enum import Enum


class _StrEnum(str, Enum):
    def __str__(self) -> str:  # pragma: no cover - convenience only
        return self.value

    @classmethod
    def coerce(cls, value):
        if isinstance(value, cls):
            return value
        try:
            return cls(value)
        except ValueError as exc:
            raise ValueError(
                f"{cls.__name__}: {value!r} is not an allowed value "
                f"({sorted(m.value for m in cls)})"
            ) from exc


class Capability(_StrEnum):
    """The read operations a provider can advertise (plan A05)."""

    DISCOVERY = "discovery"
    COURSES = "courses"
    CONTAINERS = "containers"
    QUESTIONS = "questions"
    ANSWERS = "answers"
    RESOURCES = "resources"
    ASSETS = "assets"
    REGIONS = "regions"
    TAGS = "tags"
    COVERAGE = "coverage"


#: Deterministic order used for listing and for reports.
CAPABILITIES: tuple[Capability, ...] = tuple(Capability)

#: Capabilities whose request must name a target (an owning entity's native id).
TARGET_REQUIRED: frozenset[Capability] = frozenset({Capability.ANSWERS, Capability.REGIONS})


class Availability(_StrEnum):
    """How ready a provider is; only `unavailable` blocks dispatch."""

    AVAILABLE = "available"
    EXPERIMENTAL = "experimental"
    UNAVAILABLE = "unavailable"


__all__ = ["Capability", "CAPABILITIES", "TARGET_REQUIRED", "Availability"]
