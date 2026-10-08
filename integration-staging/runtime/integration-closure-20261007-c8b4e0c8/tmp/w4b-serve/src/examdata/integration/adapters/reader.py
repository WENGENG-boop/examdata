"""Read a raw index document into memory without touching protected sources.

The reader is the only place an adapter opens a file. It is deliberately small
and total: a missing file, an unreadable file, malformed JSON, a non-synthetic
document or an unknown schema version each produce an explicit
:class:`AdapterProblem` instead of an exception, and the caller receives
``(None, problems)`` rather than a half-parsed document.

Only files a caller explicitly hands in are read; the reader never walks a tree,
never resolves a path outside the staged root and never fetches anything.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from ..contracts.enums import GapScope
from .problems import AdapterProblem, ProblemCode, problem

SUPPORTED_SCHEMA_VERSIONS = frozenset({"1"})


def read_index(path: str | Path) -> tuple[dict[str, Any] | None, list[AdapterProblem]]:
    """Read and validate one raw index file. Never raises for a data problem."""
    p = Path(path)
    if not p.is_file():
        return None, [problem(ProblemCode.MISSING_INDEX, GapScope.SYSTEM,
                              f"index file {p.name!r} does not exist")]
    try:
        text = p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return None, [problem(ProblemCode.UNREADABLE_INDEX, GapScope.SYSTEM,
                              f"index file {p.name!r} could not be read: {type(exc).__name__}")]
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, [problem(ProblemCode.INVALID_JSON, GapScope.SYSTEM,
                              f"index file {p.name!r} is not valid JSON: {exc.msg}")]
    return validate_index(data, source_name=p.name)


def validate_index(data: Any, *, source_name: str = "<memory>") -> tuple[dict[str, Any] | None, list[AdapterProblem]]:
    """Validate an already-parsed index document (used by the reader and tests)."""
    if not isinstance(data, Mapping):
        return None, [problem(ProblemCode.INVALID_JSON, GapScope.SYSTEM,
                              f"index {source_name!r} is not a JSON object")]
    if data.get("fixture_kind") != "synthetic":
        return None, [problem(ProblemCode.WRONG_FIXTURE_KIND, GapScope.SYSTEM,
                              f"index {source_name!r} is not labelled synthetic; the staged "
                              f"adapter layer only accepts synthetic fixtures")]
    version = str(data.get("schema_version"))
    if version not in SUPPORTED_SCHEMA_VERSIONS:
        return None, [problem(ProblemCode.UNSUPPORTED_SCHEMA_VERSION, GapScope.SYSTEM,
                              f"index {source_name!r} declares schema_version {version!r}; "
                              f"supported: {sorted(SUPPORTED_SCHEMA_VERSIONS)}")]
    return dict(data), []


__all__ = ["read_index", "validate_index", "SUPPORTED_SCHEMA_VERSIONS"]
