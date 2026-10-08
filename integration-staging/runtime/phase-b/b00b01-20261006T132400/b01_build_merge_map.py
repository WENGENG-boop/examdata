"""Build B01_MERGE_MAP.json from the frozen A14 merge map (F01 corrected).

Read-only on the original tree: the A14 map and the real CLI file are read, never
written. Output goes only to docs/integration/execution/evidence/B01/<run>/.

This is the release-independent half of B01. The three-way semantic reconciliation
against a *released* original tree is gate-blocked (gate:original_paths_released is
closed, no human release credential exists), so every entry is carried with an
explicit deferred disposition and reason rather than a fabricated pass. The one
correction that does not need the released tree is F01 (CLI target), applied here.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
from datetime import datetime

ROOT = pathlib.Path(__file__).resolve().parents[4]  # C:/Users/weo/Desktop/api
RUN_ID = "b00b01-20261006T132400"
A14 = ROOT / "docs/integration/execution/A14_MERGE_MAP.json"
SEALED_A14 = (ROOT / "docs/integration/execution/evidence/B00" / RUN_ID /
              "a_sealed_A14_MERGE_MAP.json")
OUT_DIR = ROOT / "docs/integration/execution/evidence/B01" / RUN_ID
REAL_CLI = ROOT / "examdata/src/examdata/cli.py"
PYPROJECT = ROOT / "examdata/pyproject.toml"

DEFERRED_REASON = (
    "three-way semantic reconciliation requires the released original tree; "
    "gate:original_paths_released is closed (no human release credential in this "
    "session), so this entry is carried from A14 with no disposition change and is "
    "NOT reconciled or merged"
)


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    stamp = datetime.now().astimezone().replace(microsecond=0).isoformat()
    a14_bytes = A14.read_bytes()
    a14 = json.loads(a14_bytes.decode("utf-8"))

    # F01 evidence, observed read-only.
    cli_exists = REAL_CLI.exists()
    cli_sha = sha256(REAL_CLI) if cli_exists else None
    cli_size = REAL_CLI.stat().st_size if cli_exists else None
    pp_text = PYPROJECT.read_text(encoding="utf-8")
    entry_point = None
    for line in pp_text.splitlines():
        s = line.strip()
        if s.startswith("examdata") and ":" in s and "=" in s:
            entry_point = s
            break

    # ---- entries: carry all 247 with an explicit deferred disposition+reason ----
    entries = []
    for e in a14["entries"]:
        b01 = dict(e)
        b01["b01_disposition"] = "deferred_pending_release"
        b01["b01_reason"] = DEFERRED_REASON
        b01["b01_reconciliation"] = {
            "kind": "not_attempted_gate_blocked",
            "gate": "original_paths_released",
            "three_way": False,
            "two_way": False,
        }
        entries.append(b01)

    # ---- planned_original_edits: F01 correction on the CLI target --------------
    planned = []
    f01_old = None
    for pe in a14["planned_original_edits"]:
        p = dict(pe)
        if p["target_path"] == "examdata/cli.py":
            f01_old = dict(p)
            p["target_path"] = "examdata/src/examdata/cli.py"
            p["base_sha256"] = cli_sha
            p["base_exists"] = cli_exists
            p["base_size"] = cli_size
            p["entry_point"] = entry_point
            p["entry_point_source"] = "examdata/pyproject.toml [project.scripts]"
            p["reversal"] = (
                "restore the B00 latest released base bytes of "
                "examdata/src/examdata/cli.py and verify no later modification is "
                "overwritten; do not restore the A14 snapshot"
            )
            p["note"] = ("F01 corrected: the real entry point is "
                         "examdata/src/examdata/cli.py (examdata.cli:app); the "
                         "previous target examdata/cli.py does not exist")
        p["b01_disposition"] = "carried_pending_release"
        p["b01_reason"] = (
            "planned original edit; not applied — gate:original_paths_released is "
            "closed. F01 target/rollback corrected here; execution deferred to B02/B10"
        )
        planned.append(p)

    f01 = {
        "finding": ("F01 (PHASE_A_INDEPENDENT_REVIEW_2026-10-06.md): A14 targeted "
                    "examdata/cli.py with base_exists=false but a "
                    "'restore the recorded base bytes' reversal; the real entry "
                    "point is examdata/src/examdata/cli.py "
                    "(pyproject.toml [project.scripts] examdata = 'examdata.cli:app')"),
        "old_target_path": "examdata/cli.py",
        "old_base_exists": False,
        "old_reversal": "restore the recorded base bytes",
        "new_target_path": "examdata/src/examdata/cli.py",
        "new_base_sha256": cli_sha,
        "new_base_exists": cli_exists,
        "new_base_size": cli_size,
        "entry_point": entry_point,
        "entry_point_source": "examdata/pyproject.toml [project.scripts]",
        "observed_at_local": stamp,
        "rollback_semantics": {
            "new_file": ("delete only if the candidate SHA256 still matches the "
                         "recorded staged digest; never 'restore bytes' for a file "
                         "that had no base"),
            "existing_file": ("restore the B00 latest released base and verify no "
                              "later modification is overwritten; do not restore an "
                              "A14 snapshot"),
        },
    }

    # ---- not_merged: carry all 92 with an explicit disposition+reason ----------
    not_merged = []
    for nm in a14["not_merged"]:
        n = dict(nm)
        n["b01_disposition"] = "excluded"
        n["b01_reason"] = ("excluded from the merge: " + nm.get("reason", "")).strip()
        not_merged.append(n)

    active = []
    for ao in a14["active_owner_deferred"]:
        a = dict(ao)
        a["b01_disposition"] = "deferred_active_owner"
        a["b01_reason"] = ("active owner path; still protected — gate:"
                           "original_paths_released is closed, no release recorded")
        active.append(a)

    out = {
        "map_version": "merge-map-b01/1",
        "generated_by": ("integration-staging/runtime/phase-b/" + RUN_ID +
                         "/b01_build_merge_map.py"),
        "generated_at_local": stamp,
        "mode": "PHASE_B_PENDING_RELEASE",
        "status": "proposed_staged_not_merged_not_deployed",
        "derived_from": {
            "path": "docs/integration/execution/A14_MERGE_MAP.json",
            "sha256": hashlib.sha256(a14_bytes).hexdigest(),
            "a14_map_byte_unchanged": True,
            "frozen_snapshot": ("docs/integration/execution/evidence/B00/" + RUN_ID +
                                "/a_sealed_A14_MERGE_MAP.json"),
            "frozen_snapshot_sha256": sha256(SEALED_A14) if SEALED_A14.exists() else None,
        },
        "reconciliation_kind": "carried_pending_release",
        "reconciliation_limitation": (
            "No released tree exists, so no three-way (old base -> new released "
            "original -> staged proposal) or two-way comparison was performed. Every "
            "A14 entry is carried unchanged with an explicit deferred disposition; "
            "F01 is the only correction applied because it is verifiable read-only."
        ),
        "f01_correction": f01,
        "counts": {
            "entries": len(entries),
            "not_merged": len(not_merged),
            "planned_original_edits": len(planned),
            "active_owner_deferred": len(active),
            "entries_reconciled": 0,
            "entries_deferred": len(entries),
        },
        "entries": entries,
        "planned_original_edits": planned,
        "not_merged": not_merged,
        "active_owner_deferred": active,
        "requirements_for_merge": a14["requirements_for_merge"],
        "problems": [],
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / "B01_MERGE_MAP.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")

    # Hard invariants: A14 unchanged, every entry dispositioned, F01 applied.
    checks = {
        "a14_byte_unchanged": sha256(A14) == out["derived_from"]["sha256"],
        "entries_all_dispositioned": all(
            e.get("b01_disposition") and e.get("b01_reason") for e in entries),
        "entries_count_247": len(entries) == 247,
        "not_merged_count_92": len(not_merged) == 92,
        "cli_target_corrected": not any(
            p["target_path"] == "examdata/cli.py" for p in planned),
        "cli_target_real": any(
            p["target_path"] == "examdata/src/examdata/cli.py" and p["base_exists"]
            for p in planned),
        "no_entry_promoted_to_pass": all(
            e["b01_disposition"] == "deferred_pending_release" for e in entries),
    }
    print(json.dumps({"out": str(out_path), "checks": checks,
                      "all_ok": all(checks.values())}, indent=2))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
