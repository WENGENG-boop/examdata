"""Quick W1 semantics probe (private run only; not part of the deliverable)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

CANDIDATE = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(CANDIDATE / "src"))

from examdata.integration.catalog.model import CatalogEntry  # noqa: E402
from examdata.integration.contracts.base import UNKNOWN  # noqa: E402
from examdata.integration.contracts.models import Coverage  # noqa: E402
from examdata.integration.operations.published import (  # noqa: E402
    Exclusion,
    ExpectedManifest,
    ExpectedScope,
    PartialExpectation,
    build_published,
)


def ident(pid: str, parent=UNKNOWN):
    return {"system": "cie", "container_native_identity": "cont-1",
            "native_id": pid, "number_path": "1", "parent_native_id": parent}


def entry(pid, *, identity=None, quality=None, evidence=None):
    return CatalogEntry(
        public_id=pid, kind="question", system="cie",
        identity_fields=(ident(pid) if identity is None else dict(identity)),
        native_locator={"native_kind": "probe", "ref": pid},
        searchable={"stem": pid}, source_revision="probe",
        quality_summary=dict(quality or {}), content_class="synthetic",
        evidence_labels=list(evidence or ()),
    )


def scope(scope_id="cie-questions", *, expected=None, exclusions=(), partial=()):
    return ExpectedScope(
        id=scope_id, system="cie", kind="question", expected=expected,
        exclusions=tuple(Exclusion(*e) for e in exclusions),
        partial=tuple(PartialExpectation(*p) for p in partial))


def manifest(*scopes):
    return ExpectedManifest(scopes=tuple(scopes), source_label="probe.json")


def row(view):
    return view.rows[0]


def show(case, view, extra=None):
    r = row(view)
    print(f"--- {case}")
    print(json.dumps({
        "observed": r["observed"], "expected": r["expected"],
        "excluded": r["excluded"], "unknown": r["unknown"],
        "partial": r["partial"], "verified": r["verified"],
        "unmet": r["unmet"], "overfilled": r["overfilled"],
        "status": r["derived_status"], "percentage": r["percentage"],
        "problems": r["problems"],
        "identity_complete": r["identity_complete"],
        "validate": Coverage.from_dict(r).validate(),
        "view_problems": [p["code"] for p in view.problems],
    }, sort_keys=True))
    if extra:
        print("   extra:", extra)


Q_VERIFIED_NO_EVIDENCE = {"content": "complete", "answer_presence": "present",
                          "answer_verification": "source_verified"}

# C01.1 empty evidence labels
show("C01.1 empty evidence labels",
     build_published([entry("q:cie:a", quality=Q_VERIFIED_NO_EVIDENCE, evidence=[])],
                     manifest(scope(expected=1))))

# C01.2 answer_presence missing + source_verified
show("C01.2 missing answer + source_verified",
     build_published([entry("q:cie:a", quality={"content": "complete",
                                                "answer_presence": "missing",
                                                "answer_verification": "source_verified"},
                            evidence=["copied_snapshot"])],
                     manifest(scope(expected=1))))

# C01.3 empty identity mapping
show("C01.3 empty identity mapping",
     build_published([entry("q:cie:a", identity={}, quality=Q_VERIFIED_NO_EVIDENCE,
                            evidence=["copied_snapshot"])],
                     manifest(scope(expected=1))))

# positive control: fully backed
show("positive fully backed",
     build_published([entry("q:cie:a", quality=Q_VERIFIED_NO_EVIDENCE,
                            evidence=["copied_snapshot"])],
                     manifest(scope(expected=1))))

# C02.1 nonexistent manifest reference
show("C02.1 nonexistent partial reference",
     build_published([entry("q:cie:a", quality=Q_VERIFIED_NO_EVIDENCE,
                            evidence=["copied_snapshot"])],
                     manifest(scope(expected=1, partial=(("q:cie:ghost", "gone"),)))))

# C02.2 duplicate public ids (conflicting content)
show("C02.2 conflicting duplicate",
     build_published([entry("q:cie:a", quality=Q_VERIFIED_NO_EVIDENCE,
                            evidence=["copied_snapshot"]),
                      entry("q:cie:a", quality={}, evidence=[])],
                     manifest(scope(expected=1))))

# C02.2b identical duplicates
show("C02.2b identical duplicate",
     build_published([entry("q:cie:a", quality=Q_VERIFIED_NO_EVIDENCE,
                            evidence=["copied_snapshot"]),
                      entry("q:cie:a", quality=Q_VERIFIED_NO_EVIDENCE,
                            evidence=["copied_snapshot"])],
                     manifest(scope(expected=1))))

# zero-expected empty
show("zero-expected empty", build_published([], manifest(scope(expected=0))))

# zero-expected with published entries
show("zero-expected with published",
     build_published([entry("q:cie:a", quality=Q_VERIFIED_NO_EVIDENCE,
                            evidence=["copied_snapshot"])],
                     manifest(scope(expected=0))))

# all excluded
show("all excluded",
     build_published([entry("q:cie:a", quality={}, evidence=[]),
                      entry("q:cie:b", quality={}, evidence=[])],
                     manifest(scope(expected=2, exclusions=(("q:cie:a", "dup"),
                                                            ("q:cie:b", "dup"))))))

# underfilled
show("underfilled",
     build_published([entry("q:cie:a", quality=Q_VERIFIED_NO_EVIDENCE,
                            evidence=["copied_snapshot"])],
                     manifest(scope(expected=3))))

# overfilled
show("overfilled",
     build_published([entry("q:cie:a", quality=Q_VERIFIED_NO_EVIDENCE,
                            evidence=["copied_snapshot"]),
                      entry("q:cie:b", quality=Q_VERIFIED_NO_EVIDENCE,
                            evidence=["copied_snapshot"])],
                     manifest(scope(expected=1))))

# unknown denominator
show("unknown denominator",
     build_published([entry("q:cie:a", quality=Q_VERIFIED_NO_EVIDENCE,
                            evidence=["copied_snapshot"])],
                     manifest(scope(expected=None))))

# manual_adjudicated without decision -> downgraded
show("manual_adjudicated without decision",
     build_published([entry("q:cie:a",
                            quality={"content": "complete", "answer_presence": "present",
                                     "answer_verification": "manual_adjudicated"},
                            evidence=[])],
                     manifest(scope(expected=1))))

# wrong-scope reference
view = build_published(
    [entry("q:cie:a", quality=Q_VERIFIED_NO_EVIDENCE, evidence=["copied_snapshot"])],
    manifest(ExpectedScope(id="edexcel-questions", system="edexcel", kind="question",
                           expected=1,
                           exclusions=(Exclusion("q:cie:a", "wrong scope"),))))
print("--- wrong-scope reference")
print(json.dumps({"rows": len(view.rows), "problems": view.problems}, sort_keys=True))

print("probe done")
