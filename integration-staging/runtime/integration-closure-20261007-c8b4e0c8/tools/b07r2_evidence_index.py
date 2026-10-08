#!/usr/bin/env python
"""Build reports/B07R2_EVIDENCE_INDEX.json: full artifact enumeration for the
b07-reviewfix-20261007-774e4dad run, sha256 per file.

Covered:
  - run root: reports/ (this index self-excluded), evidence/ (recursive,
    including the preserved cache-incident artifacts and pytest basetemps),
    tools/, tests/, logs/, root-level tools, and the v2 candidate manifest
    (the 222 candidate tree files are enumerated inside that manifest itself);
  - docs side: the B07R2_* report copies and the B07 review-fix evidence dir
    under docs/integration/execution/;
  - frozen inputs named in evidence/provenance_before_copy.json, re-hashed
    fresh here and compared with the values recorded at the provenance gate.

Two files carry no hash in this index, by construction:
  - this index itself (self-reference); both copies are listed under
    pinned_at_freeze;
  - logs/commands.log, which is rebuilt once more after this index is written
    (freeze-time rebuild).
Both final sha256 values are pinned in evidence/step7_freeze_hashes.txt.

No file is excluded from the enumeration beyond those two structural cases.

Usage: python tools/b07r2_evidence_index.py
"""
from __future__ import annotations

import hashlib
import json
import pathlib
from datetime import datetime, timezone

RUN = pathlib.Path(__file__).resolve().parents[1]
WS = RUN.parents[2]
OUT = RUN / "reports/B07R2_EVIDENCE_INDEX.json"
DOCS = WS / "docs/integration/execution"
DOCS_EVID = DOCS / "evidence/B07/b07-reviewfix-20261007-774e4dad"
PROVENANCE = RUN / "evidence/provenance_before_copy.json"
RECHECK = RUN / "evidence/step7_provenance_recheck.json"
SELF_REL = "reports/B07R2_EVIDENCE_INDEX.json"
SELF_DOCS_REL = "docs/integration/execution/B07R2_EVIDENCE_INDEX.json"
CANDIDATE_MANIFEST_REL = "candidates/b07-operations-v2/B07R2_CANDIDATE_MANIFEST.json"
DOC_COPY_NAMES = [
    "B07R2_DIFF_FROM_V1.md",
    "B07R2_FINDINGS_TO_TESTS_MATRIX.md",
    "B07R2_MERGE_PROPOSAL.json",
    "B07R2_MERGE_PROPOSAL.md",
    "B07R2_ROLLBACK_PROPOSAL.json",
    "B07R2_ROLLBACK_PROPOSAL.md",
    "B07R2_FINAL_REPORT.md",
]


def sha256_file(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def display_path(p: pathlib.Path) -> str:
    try:
        return p.relative_to(WS).as_posix()
    except ValueError:
        return p.as_posix()


def entry(path: pathlib.Path, root: pathlib.Path) -> dict:
    return {
        "path": path.relative_to(root).as_posix(),
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
    }


def sorted_entries(paths, root: pathlib.Path) -> list[dict]:
    out = [entry(p, root) for p in paths]
    out.sort(key=lambda e: e["path"])
    return out


def main() -> int:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    all_files = [p for p in RUN.rglob("*") if p.is_file()]
    rels = {p: p.relative_to(RUN).as_posix() for p in all_files}

    def in_dir(prefix: str):
        pre = prefix + "/"
        return [p for p in all_files if rels[p].startswith(pre)]

    reports_list = [p for p in in_dir("reports") if rels[p] != SELF_REL]
    evidence_list = in_dir("evidence")
    tools_list = in_dir("tools")
    tests_list = in_dir("tests")
    logs_list = in_dir("logs")
    root_list = [p for p in all_files if "/" not in rels[p]]
    manifest_list = [p for p in all_files if rels[p] == CANDIDATE_MANIFEST_REL]
    candidate_tree_count = len(
        [p for p in in_dir("candidates") if rels[p] != CANDIDATE_MANIFEST_REL]
    )

    logs_entries: list[dict] = []
    commands_log_pinned = None
    for p in logs_list:
        if rels[p] == "logs/commands.log":
            commands_log_pinned = {
                "path": "logs/commands.log",
                "sha256": None,
                "bytes": p.stat().st_size,
                "sha256_at_index_time": sha256_file(p),
                "note": (
                    "rebuilt once more after this index was written (freeze-time "
                    "rebuild); final sha256 pinned in evidence/step7_freeze_hashes.txt"
                ),
            }
        else:
            logs_entries.append(entry(p, RUN))
    logs_entries.sort(key=lambda e: e["path"])

    docs_entries: list[dict] = []
    docs_missing: list[str] = []
    for name in DOC_COPY_NAMES:
        p = DOCS / name
        if p.is_file():
            docs_entries.append(entry(p, WS))
        else:
            docs_missing.append(name)

    docs_ev_entries = sorted_entries(
        [p for p in DOCS_EVID.rglob("*") if p.is_file()], WS
    )

    prov = json.loads(PROVENANCE.read_text(encoding="utf-8"))
    frozen_named = []
    for item in prov["frozen_inputs"]["named_files"]:
        p = pathlib.Path(item["path"])
        fresh = sha256_file(p) if p.is_file() else None
        frozen_named.append(
            {
                "path": display_path(p),
                "sha256_now": fresh,
                "sha256_recorded_at_gate": item["sha256"],
                "match": fresh == item["sha256"],
            }
        )

    recheck = json.loads(RECHECK.read_text(encoding="utf-8"))
    checks = recheck.get("checks", {})

    listed = (
        reports_list
        + evidence_list
        + tools_list
        + tests_list
        + [p for p in logs_list if rels[p] != "logs/commands.log"]
        + root_list
        + manifest_list
    )
    doc = {
        "schema": "examdata.integration.b07r2_evidence_index/1",
        "run_id": RUN.name,
        "recorded_at_utc": now,
        "run_root": RUN.as_posix(),
        "workspace_root": WS.as_posix(),
        "hash": "sha256 of raw file bytes, hex, streamed; no normalization",
        "status": "private, unmerged, undeployed; all seven gates closed",
        "run_root_files": {
            "reports": sorted_entries(reports_list, RUN),
            "evidence": sorted_entries(evidence_list, RUN),
            "tools": sorted_entries(tools_list, RUN),
            "tests": sorted_entries(tests_list, RUN),
            "logs": logs_entries,
            "root_tools": sorted_entries(root_list, RUN),
            "candidate_v2_manifest": sorted_entries(manifest_list, RUN),
        },
        "docs_side": {
            "docs_report_copies": docs_entries,
            "docs_report_copies_missing": docs_missing,
            "docs_evidence_copies": docs_ev_entries,
        },
        "frozen_inputs": {
            "source": "evidence/provenance_before_copy.json (recorded at the STEP 1 gate)",
            "named_files_fresh_rehash": frozen_named,
            "composite_tree_digests_recorded_at_gate": {
                k: prov["frozen_inputs"][k]
                for k in (
                    "frozen_b07_run_root",
                    "frozen_b07_docs_evidence_dir",
                    "independent_review_dir",
                )
            },
            "reverified_by": {
                "evidence": "evidence/step7_provenance_recheck.json",
                "sha256": sha256_file(RECHECK),
                "verdict": recheck.get("verdict", "unknown"),
                "checks": checks,
                "all_checks_true": bool(checks) and all(checks.values()),
            },
        },
        "pinned_at_freeze": {
            "note": (
                "These files carry no sha256 inside this index (self-reference and "
                "ordering, see module docstring). Both final sha256 values are "
                "recorded in evidence/step7_freeze_hashes.txt."
            ),
            "self_files": [
                {
                    "path": SELF_REL,
                    "sha256": None,
                    "role": "this index (run-root copy)",
                },
                {
                    "path": SELF_DOCS_REL,
                    "sha256": None,
                    "role": (
                        "this index (docs copy; made byte-identical by cp after "
                        "this index was written, verified with cmp at freeze)"
                    ),
                },
            ],
            "logs_commands_log": commands_log_pinned,
        },
        "counts": {
            "run_root_files_total_at_traversal": len(all_files),
            "run_root_files_total_note": (
                "traversal count taken before this index file was written; add 1 "
                "for the index itself"
            ),
            "listed_with_sha256": len(listed) + len(docs_entries) + len(docs_ev_entries),
            "frozen_named_files_checked": len(frozen_named),
            "frozen_named_files_all_match": all(e["match"] for e in frozen_named),
            "candidate_tree_files_not_listed_here": candidate_tree_count,
            "pinned_without_hash_inside_index": 3,
        },
    }

    OUT.write_text(
        json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT}")
    print(
        f"listed {doc['counts']['listed_with_sha256']} files with sha256; "
        f"frozen named files all match: {doc['counts']['frozen_named_files_all_match']}; "
        f"docs copies missing: {docs_missing or 'none'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
