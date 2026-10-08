"""Shared contract plumbing: base model, dict round-trip helpers, gap record.

Kept separate from `models.py` and `quality.py` so neither has to import the
other (a question carries quality, and quality carries gaps).
"""
from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from enum import Enum
from typing import Any, ClassVar, Mapping

from .canonical import UNKNOWN, UnknownType


class ContractError(ValueError):
    """A payload is structurally invalid for the requested model."""


def plain(value: Any) -> Any:
    """Recursively convert a model into JSON-serialisable plain data."""
    if isinstance(value, Enum):
        return value.value
    if value is UNKNOWN:
        return "unknown"
    if is_dataclass(value):
        return {f.name: plain(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, Mapping):
        return {k: plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    return value


def req(payload: Mapping[str, Any], key: str, where: str) -> Any:
    """Return a structurally required field or raise ContractError."""
    if key not in payload:
        raise ContractError(f"{where}: missing required field {key!r}")
    return payload[key]


@dataclass
class ContractModel:
    """Base class providing dict round-trip and validation plumbing."""

    SCHEMA: ClassVar[str] = "contract/1"

    def to_dict(self) -> dict[str, Any]:
        return {"schema": self.SCHEMA, **plain(self)}

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ContractModel":
        raise NotImplementedError

    def validate(self) -> list[str]:
        return []


@dataclass
class Gap(ContractModel):
    """A visible gap: never silently dropped, never upgraded to a pass."""

    SCHEMA = "gap/1"

    code: str = ""
    scope: str = ""
    detail: str | None = None

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "Gap":
        return cls(code=payload.get("code", ""), scope=payload.get("scope", ""),
                   detail=payload.get("detail"))


__all__ = ["ContractError", "ContractModel", "Gap", "plain", "req", "UNKNOWN", "UnknownType"]
