"""Shared helpers for the B07R2 review-fix candidate tests (private run only).

Every test module imports this module first. Importing it proves that the
``examdata`` package under test resolves to the candidate root named by
``B07R2_EXPECT_CANDIDATE_ROOT`` (the frozen v1 candidate for the RED run, the
repaired v2 candidate afterwards) and pins ``EXAMDATA_INTEGRATION_ROOT`` to
that tree, so the public API resolves its own synthetic fixtures. Any mismatch
raises at import time and fails the whole run: no test can silently validate
the wrong tree.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping

import pytest

import examdata

CANDIDATE_ROOT = Path(examdata.__file__).resolve().parents[2]
_raw_expected = os.environ.get("B07R2_EXPECT_CANDIDATE_ROOT", "").strip()
if not _raw_expected:
    raise RuntimeError(
        "B07R2_EXPECT_CANDIDATE_ROOT must name the candidate root under test")
EXPECTED_ROOT = Path(_raw_expected).resolve()
if CANDIDATE_ROOT != EXPECTED_ROOT:
    raise RuntimeError(
        f"examdata resolves to {CANDIDATE_ROOT!r}, not the intended candidate "
        f"{EXPECTED_ROOT!r}: refusing to run candidate-dependent tests")
os.environ["EXAMDATA_INTEGRATION_ROOT"] = str(CANDIDATE_ROOT)

import examdata.integration.operations as operations_pkg  # noqa: E402
from examdata.integration.catalog.model import CatalogEntry  # noqa: E402
from examdata.integration.contracts.base import UNKNOWN  # noqa: E402
from examdata.integration.contracts.canonical import IDENTITY_KEYS  # noqa: E402
from examdata.integration.contracts.enums import EntityKind  # noqa: E402
from examdata.integration.operations import checkpoints as checkpoints_mod  # noqa: E402
from examdata.integration.operations import coverage as coverage_mod  # noqa: E402
from examdata.integration.operations import jobs as jobs_mod  # noqa: E402
from examdata.integration.operations import published as published_mod  # noqa: E402
from examdata.integration.operations.jobs import scan_checkpoint_root  # noqa: E402
from examdata.integration.operations.published import (  # noqa: E402
    MANIFEST_NAME,
    Exclusion,
    ExpectedManifest,
    ExpectedScope,
    PartialExpectation,
)


def assert_origin(module: Any, name: str) -> None:
    """Fail when ``module`` was imported from outside the intended candidate."""
    path = Path(module.__file__).resolve()
    if not str(path).startswith(str(EXPECTED_ROOT) + os.sep):
        raise AssertionError(
            f"{name} imported from {path!r}, outside the intended candidate "
            f"{EXPECTED_ROOT!r}")


_MODULES: dict[str, Any] = {
    "examdata": examdata,
    "operations": operations_pkg,
    "operations.jobs": jobs_mod,
    "operations.checkpoints": checkpoints_mod,
    "operations.coverage": coverage_mod,
    "operations.published": published_mod,
}
for _name, _module in _MODULES.items():
    assert_origin(_module, _name)


def module_origins() -> dict[str, str]:
    """The resolved file path behind every module this run validates."""
    return {name: str(Path(mod.__file__).resolve()) for name, mod in _MODULES.items()}


# --------------------------------------------------------------------------- #
# Synthetic quality presets (the exact shapes the review's reproductions use).
# --------------------------------------------------------------------------- #
QUALITY_VERIFIED = {
    "content": "complete",
    "answer_presence": "present",
    "answer_verification": "source_verified",
}
QUALITY_COMPLETE_UNVERIFIED = {
    "content": "complete",
    "answer_presence": "present",
    "answer_verification": "unverified",
}
QUALITY_PARTIAL_UNVERIFIED = {
    "content": "partial",
    "answer_presence": "present",
    "answer_verification": "unverified",
}
QUALITY_CONFLICTING = {
    "content": "complete",
    "answer_presence": "present",
    "answer_verification": "conflicting",
}
QUALITY_MISSING_CONTENT = {
    "content": "missing",
    "answer_presence": "missing",
}


_HASH_IDENTITY_KEYS = frozenset(
    {"sha256", "document_sha256", "input_revision", "content_sha256"})


def _default_identity(system: str, kind: str, public_id: str) -> dict[str, Any]:
    """A complete, resolved identity for ``(system, kind)``: every frozen key
    carries a non-empty, non-``UNKNOWN`` value (hash keys are 64-hex)."""
    try:
        keys = IDENTITY_KEYS.get(EntityKind.coerce(kind))
    except ValueError:
        keys = None
    if not keys:
        return {"system": system, "kind": kind, "native_id": public_id}
    values: dict[str, Any] = {}
    for key in keys:
        if key == "system":
            values[key] = system
        elif key == "kind":
            values[key] = kind
        elif key in _HASH_IDENTITY_KEYS:
            values[key] = hashlib.sha256(public_id.encode("utf-8")).hexdigest()
        elif key == "bbox":
            values[key] = [0, 0, 1, 1]
        elif key == "page":
            values[key] = 1
        elif key == "native_id":
            values[key] = public_id
        else:
            values[key] = f"{public_id}:{key}"
    return values


def make_entry(public_id: str, *, system: str = "cie", kind: str = "question",
               identity: Mapping[str, Any] | None = None,
               quality: Mapping[str, Any] | None = None,
               evidence: Iterable[str] | None = None) -> CatalogEntry:
    """One synthetic catalog entry, built from in-memory data only.

    Convention: a fixture that omits ``identity``/``evidence`` stands in for a
    real, evidence-backed entry - a complete resolved identity, and the
    authoritative ``copied_snapshot`` label whenever it carries a non-empty
    ``quality`` mapping; pass ``identity={}`` or an explicit ``evidence=``
    (including ``[]``) to exercise the unresolved/unsupported cases.
    """
    if identity is None:
        identity_fields = _default_identity(system, kind, public_id)
    else:
        identity_fields = dict(identity)
        if identity_fields:
            identity_fields = {**_default_identity(system, kind, public_id),
                               **identity_fields}
    if evidence is None:
        labels = ["copied_snapshot"] if quality else []
    else:
        labels = list(evidence)
    return CatalogEntry(
        public_id=public_id,
        kind=kind,
        system=system,
        identity_fields=identity_fields,
        native_locator={"native_kind": "synthetic-fixture", "ref": public_id},
        searchable={"stem": f"synthetic fixture for {public_id}"},
        source_revision="rev-b07r2-synthetic",
        quality_summary=dict(quality or {}),
        content_class="synthetic",
        evidence_labels=labels,
    )


def make_scope(scope_id: str, *, system: str = "cie", kind: str = "question",
               expected: int | None = None, note: str | None = None,
               exclusions: Iterable[tuple[str, str]] = (),
               partial: Iterable[tuple[str, str]] = ()) -> ExpectedScope:
    return ExpectedScope(
        id=scope_id,
        system=system,
        kind=kind,
        expected=expected,
        note=note,
        exclusions=tuple(Exclusion(public_id=pid, reason=reason)
                         for pid, reason in exclusions),
        partial=tuple(PartialExpectation(public_id=pid, reason=reason)
                      for pid, reason in partial),
    )


def make_manifest(*scopes: ExpectedScope, label: str = MANIFEST_NAME) -> ExpectedManifest:
    return ExpectedManifest(scopes=tuple(scopes), source_label=label)


def row_for_scope(view: Any, scope_id: str) -> dict[str, Any]:
    wanted = f"coverage:published:{scope_id}"
    rows = [row for row in view.rows if row.get("public_id") == wanted]
    assert len(rows) == 1, f"expected exactly one row for {scope_id!r}, got {rows!r}"
    return rows[0]


# --------------------------------------------------------------------------- #
# Synthetic filesystem builders.
# --------------------------------------------------------------------------- #
def write_json(path: str | Path, document: Any) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    return target


def write_bytes(path: str | Path, data: bytes) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return target


def cie_checkpoint_document(**overrides: Any) -> dict[str, Any]:
    """A minimal CIE batch checkpoint document (synthetic, in-memory)."""
    document: dict[str, Any] = {
        "stage": "running",
        "loop_stage": "queued",
        "current_subject": "synth-subject",
        "totals": {"done": 1},
        "updated_at": "2026-10-06T08:18:31+0800",
    }
    document.update(overrides)
    return document


# --------------------------------------------------------------------------- #
# Budget-aware call helpers: a missing budget API is a loud failure, not an
# accidental pass.
# --------------------------------------------------------------------------- #
def scan(root: str | Path, **budgets: Any):
    """Call ``scan_checkpoint_root`` with the given budgets."""
    try:
        return scan_checkpoint_root(root, **budgets)
    except TypeError as exc:
        pytest.fail(f"scan_checkpoint_root does not accept {sorted(budgets)}: {exc}")


def listwalker(root: str | Path, **kwargs: Any) -> list[Path]:
    """Materialise the bounded walker's output (tests only)."""
    try:
        iterator = checkpoints_mod.iter_checkpoint_paths(root, **kwargs)
    except TypeError as exc:
        pytest.fail(f"iter_checkpoint_paths does not accept {sorted(kwargs)}: {exc}")
    return list(iterator)


def bounded_read(path: str | Path, **kwargs: Any):
    """Call the bounded reader, or fail loudly when the API is missing."""
    func = getattr(checkpoints_mod, "read_checkpoint_bounded", None)
    if func is None:
        pytest.fail("checkpoints.read_checkpoint_bounded is not implemented")
    return func(path, **kwargs)


def bounded_read_error() -> type:
    """The typed oversize error, or fail loudly when the API is missing."""
    cls = getattr(checkpoints_mod, "CheckpointTooLargeError", None)
    if cls is None:
        pytest.fail("checkpoints.CheckpointTooLargeError is not implemented")
    return cls
