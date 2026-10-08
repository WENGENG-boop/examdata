"""W1 C01/C02 reproduction script (private run only).

Runs the five confirmed defect scenarios from the integration review against a
given candidate root and prints a JSON verdict. ``reproduced`` means *the
defect is present* in that tree, so the frozen parent reports ``true`` for
every case and the repaired candidate reports ``false``.

Usage:
    python -B w1_reproduce.py <candidate-root>

The script always exits 0 when it ran; a crash (import error, missing API) is
a script failure, not a verdict.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any


def _prepare(candidate_root: Path) -> None:
    src = candidate_root / "src"
    if not src.is_dir():
        raise SystemExit(f"candidate root has no src/ directory: {candidate_root}")
    sys.path.insert(0, str(src))
    os.environ["EXAMDATA_INTEGRATION_ROOT"] = str(candidate_root)


def _question_identity(public_id: str) -> dict[str, Any]:
    """A fully resolved question identity (valid under both contract versions)."""
    return {
        "system": "cie",
        "container_native_identity": "container-w1-reproduce",
        "native_id": public_id,
        "number_path": "1",
        "parent_native_id": "parent-w1-reproduce",
    }


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        raise SystemExit("usage: w1_reproduce.py <candidate-root>")
    candidate_root = Path(argv[1]).resolve()
    _prepare(candidate_root)

    import examdata
    from examdata.integration.catalog.model import CatalogEntry
    from examdata.integration.operations.published import (
        Exclusion,
        ExpectedManifest,
        ExpectedScope,
        PartialExpectation,
        build_published,
    )

    def make_entry(public_id: str, *, quality: dict[str, Any],
                   evidence: list[str], stem: str | None = None,
                   identity: dict[str, Any] | None = None) -> CatalogEntry:
        return CatalogEntry(
            public_id=public_id,
            kind="question",
            system="cie",
            identity_fields=(dict(identity) if identity is not None
                             else _question_identity(public_id)),
            native_locator={"native_kind": "synthetic-w1", "ref": public_id},
            searchable={"stem": stem or public_id},
            source_revision="w1-reproduce",
            quality_summary=dict(quality),
            content_class="synthetic",
            evidence_labels=list(evidence),
        )

    def scope(*, expected: int | None, exclusions=(), partial=()) -> ExpectedScope:
        return ExpectedScope(
            id="cie-questions", system="cie", kind="question", expected=expected,
            exclusions=tuple(Exclusion(*item) for item in exclusions),
            partial=tuple(PartialExpectation(*item) for item in partial))

    def manifest(*scopes: ExpectedScope) -> ExpectedManifest:
        return ExpectedManifest(scopes=tuple(scopes), source_label="w1-reproduce.json")

    def case(identifier: str, reproduced: bool, **observed: Any) -> dict[str, Any]:
        return {"id": identifier, "reproduced": bool(reproduced), **observed}

    unsupported_claim = {"content": "complete", "answer_verification": "source_verified"}
    backed_claim = {"content": "complete", "answer_presence": "present",
                    "answer_verification": "source_verified"}
    cases: list[dict[str, Any]] = []

    # C01.1 — content=complete + answer_verification=source_verified with no
    # evidence labels: the claim must not validate and must not count verified.
    entry = make_entry("q_w1_c01_1", quality=unsupported_claim, evidence=[])
    view = build_published([entry], manifest(scope(expected=1)))
    row = view.rows[0]
    cases.append(case(
        "C01.1", entry.validate() == [] and row["verified"] == 1
        and row["derived_status"] == "complete" and row["percentage"] == 100.0,
        validate_clean=entry.validate() == [],
        verified=row["verified"], derived_status=row["derived_status"],
        percentage=row["percentage"], problems=[p["code"] for p in view.problems]))

    # C01.2 — answer_presence=missing together with source_verified: still a
    # contradiction, still not verified.
    entry = make_entry("q_w1_c01_2",
                       quality={"content": "complete", "answer_presence": "missing",
                                "answer_verification": "source_verified"},
                       evidence=["copied_snapshot"])
    view = build_published([entry], manifest(scope(expected=1)))
    row = view.rows[0]
    cases.append(case(
        "C01.2", row["verified"] == 1 and row["derived_status"] == "complete"
        and row["percentage"] == 100.0,
        validate_clean=entry.validate() == [],
        verified=row["verified"], derived_status=row["derived_status"],
        percentage=row["percentage"], problems=[p["code"] for p in view.problems]))

    # C01.3 — an empty identity mapping must not count as identity complete.
    entry = make_entry("q_w1_c01_3", quality=backed_claim,
                       evidence=["copied_snapshot"], identity={})
    view = build_published([entry], manifest(scope(expected=1)))
    row = view.rows[0]
    cases.append(case(
        "C01.3", row["identity_complete"] == 1 and row["derived_status"] == "complete",
        validate_clean=entry.validate() == [],
        identity_complete=row["identity_complete"], verified=row["verified"],
        derived_status=row["derived_status"],
        problems=[p["code"] for p in view.problems]))

    # C02.1 — a manifest partial reference to a nonexistent public id must not
    # coexist with complete coverage / 100%.
    entry = make_entry("q_w1_c02_1", quality=backed_claim,
                       evidence=["copied_snapshot"])
    view = build_published([entry], manifest(scope(
        expected=1, partial=(("q_w1_c02_ghost", "declared but never published"),))))
    row = view.rows[0]
    has_problem = any(p.get("code") == "manifest_id_not_published"
                      for p in view.problems)
    cases.append(case(
        "C02.1", has_problem and row["derived_status"] == "complete"
        and row["percentage"] == 100.0,
        problem_recorded=has_problem, derived_status=row["derived_status"],
        percentage=row["percentage"], problems=[p["code"] for p in view.problems]))

    # C02.2 — the same public id twice (conflicting content) must count as one
    # logical entry and the collision must be flagged.
    entries = [make_entry("q_w1_c02_dup", quality=backed_claim,
                          evidence=["copied_snapshot"], stem="first copy"),
               make_entry("q_w1_c02_dup", quality=backed_claim,
                          evidence=["copied_snapshot"], stem="second copy")]
    view = build_published(entries, manifest(scope(expected=2)))
    row = view.rows[0]
    has_duplicate_problem = any(p.get("code") == "duplicate_public_id"
                                for p in view.problems)
    cases.append(case(
        "C02.2", not has_duplicate_problem and row["observed"] == 2
        and row["verified"] == 2 and row["derived_status"] == "complete",
        duplicate_problem=has_duplicate_problem, observed=row["observed"],
        verified=row["verified"], derived_status=row["derived_status"],
        percentage=row["percentage"], problems=[p["code"] for p in view.problems]))

    verdict = {
        "candidate": str(candidate_root),
        "examdata": str(Path(examdata.__file__).resolve()),
        "cases": cases,
    }
    print(json.dumps(verdict, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
