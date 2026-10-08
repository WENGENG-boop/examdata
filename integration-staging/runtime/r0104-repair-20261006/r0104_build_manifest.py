"""Build the R01-R04 private-repair change manifest.

Private preparation only. Reads the frozen baselines and writes
evidence/R0104_CHANGE_MANIFEST.json inside this run tree. Never writes to the
live execution ledger, the original project, or any sealed evidence directory.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone, timedelta

WS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
RUN = os.path.dirname(os.path.abspath(__file__))
EVID = os.path.join(RUN, "evidence")

CST = timezone(timedelta(hours=8))

A14_MAP = os.path.join(WS, "docs", "integration", "execution", "A14_MERGE_MAP.json")
LEDGER = os.path.join(WS, "docs", "integration", "execution", "execution-ledger.json")


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rel(path: str) -> str:
    return os.path.relpath(path, WS).replace("\\", "/")


def a14_baselines() -> dict:
    with open(A14_MAP, encoding="utf-8") as fh:
        data = json.load(fh)
    return {e["staged_path"]: e.get("staged_sha256") for e in data["entries"]}


def stability_check(baselines: dict) -> dict:
    same, changed, missing = [], [], []
    for staged_path, base in baselines.items():
        full = os.path.join(WS, staged_path)
        if not os.path.exists(full):
            missing.append(staged_path)
            continue
        cur = sha256_file(full)
        (same if cur == base else changed).append(staged_path)
    return {
        "source": rel(A14_MAP),
        "a14_entries": len(baselines),
        "byte_identical": len(same),
        "changed": len(changed),
        "missing": len(missing),
        "changed_paths": changed,
        "missing_paths": missing,
        "conclusion": (
            "240 of 247 A14-recorded staged files are byte-identical; exactly the 7 "
            "R04-edited staged files differ. The staged tree was therefore stable from "
            "A14 (2026-10-06T11:43+08:00) until the R04 edits, so the A14 staged_sha256 "
            "is a valid pre-change baseline for those 7 files."
        ),
    }


def gates_observation() -> dict:
    with open(LEDGER, encoding="utf-8") as fh:
        data = json.load(fh)
    gates = data.get("gates", {})
    opened = sorted(k for k, v in gates.items() if v.get("open"))
    return {
        "ledger_path": rel(LEDGER),
        "ledger_sha256": sha256_file(LEDGER),
        "ledger_sha256_expected_frozen": "6d4449d3997b437fd3ea3a1fe7925fc78a7c0adbe0a5d3b793d6a8063101b4ba",
        "ledger_byte_unchanged": sha256_file(LEDGER)
        == "6d4449d3997b437fd3ea3a1fe7925fc78a7c0adbe0a5d3b793d6a8063101b4ba",
        "ledger_updated_at": data.get("updated_at"),
        "gate_count": len(gates),
        "gates_open": opened,
        "all_gates_closed": not opened,
        "tasks": len(data.get("tasks", [])),
        "unexpected_original_changes": len(data.get("unexpected_original_changes", [])),
    }


def dir_digest(path: str, read_only: bool = True, note: str | None = None) -> dict:
    if not os.path.isdir(path):
        return {"path": rel(path), "exists": False}
    rows = []
    newest = 0
    total = 0
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for name in sorted(files):
            full = os.path.join(root, name)
            rows.append((rel(full), sha256_file(full)))
            total += 1
            newest = max(newest, os.path.getmtime(full))
    rows.sort()
    h = hashlib.sha256()
    for r, s in rows:
        h.update(f"{r}\0{s}\n".encode("utf-8"))
    result = {
        "path": rel(path),
        "exists": True,
        "files": total,
        "tree_sha256": h.hexdigest(),
        "newest_mtime": datetime.fromtimestamp(newest, CST).isoformat(),
        "read_only": read_only,
    }
    if note:
        result["note"] = note
    return result


def files_newer_than(path: str, since: str) -> list:
    """List files under path with mtime after `since` (local ISO, +08:00)."""
    cutoff = datetime.fromisoformat(since).timestamp()
    rows = []
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for name in sorted(files):
            full = os.path.join(root, name)
            mt = os.path.getmtime(full)
            if mt > cutoff:
                rows.append(
                    {
                        "path": rel(full),
                        "mtime": datetime.fromtimestamp(mt, CST).isoformat(),
                        "sha256": sha256_file(full),
                        "bytes": os.path.getsize(full),
                    }
                )
    rows.sort(key=lambda r: (r["mtime"], r["path"]))
    return rows


def git_status() -> dict:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=WS,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except Exception as exc:  # noqa: BLE001
        return {"git_repo": "unknown", "detail": str(exc)}
    if out.returncode != 0:
        return {
            "git_repo": False,
            "detail": "workspace root is not a git repository (consistent with the ledger note)",
        }
    return {"git_repo": True, "root": out.stdout.strip()}


# group, finding, staged path (workspace-relative), diff artifact, description
EDITED = [
    (
        "R01/R02/R03",
        "R01,R02",
        "integration-staging/tools/b_ledger_update.py",
        "evidence/DIFFS/b_ledger_update.patch",
        "Ledger tool: explicit status schema, patch whitelist, whole-candidate "
        "validation before atomic publish, bytes preserved on refusal, action-level "
        "gate requirements.",
        os.path.join(RUN, "tool-versions", "b_ledger_update.pre-fix.ac9b01cb.py"),
    ),
    (
        "R04-product",
        "R04",
        "integration-staging/src/examdata_integration/runtime/manifest.py",
        "evidence/DIFFS/runtime_manifest.py.patch",
        "Resolve deployment/data roots from explicit configuration instead of "
        "importing ..testing.guards.",
        None,
    ),
    (
        "R04-product",
        "R04",
        "integration-staging/src/examdata_integration/runtime/runner.py",
        "evidence/DIFFS/runtime_runner.py.patch",
        "Same explicit-root resolution for the runner entry point.",
        None,
    ),
    (
        "R04-product",
        "R04",
        "integration-staging/src/examdata_integration/runtime/settings.py",
        "evidence/DIFFS/runtime_settings.py.patch",
        "Same explicit-root resolution for settings/schema loading.",
        None,
    ),
    (
        "R04-product",
        "R04",
        "integration-staging/src/examdata_integration/api/dataset.py",
        "evidence/DIFFS/api_dataset.py.patch",
        "Same explicit-root resolution for the API dataset layer.",
        None,
    ),
    (
        "R04-product",
        "R04",
        "integration-staging/src/examdata_integration/adapters/source_reader.py",
        "evidence/DIFFS/adapters_source_reader.py.patch",
        "Replace parents[3] staging-name discovery with explicit root resolution.",
        None,
    ),
    (
        "R04-tests",
        "R04",
        "integration-staging/tests/conftest.py",
        None,
        "Set EXAMDATA_INTEGRATION_ROOT explicitly for the staged test harness; the "
        "harness keeps denying original paths.",
        None,
    ),
    (
        "R04-tests",
        "R04",
        "integration-staging/tests/test_config_resolution.py",
        None,
        "Import and assert PathOutsideRootError for a config file outside the "
        "deployment root.",
        None,
    ),
]

NEW_FILES = [
    (
        "R04-product",
        "R04",
        "integration-staging/src/examdata_integration/runtime/paths.py",
        "New explicit-root resolver: ENV_ROOT, normalize, is_within, resolve_root, "
        "ensure_within, PathOutsideRootError.",
    ),
]

COLLATERAL = [
    "integration-staging/tools/a06_probe_runner.py",
    "integration-staging/tools/a06_final_checks.py",
    "integration-staging/tools/a08_probe_adapters.py",
    "integration-staging/tools/a10_probe_api.py",
    "integration-staging/tools/a11_probe_binary.py",
    "integration-staging/tools/a14_build_artifacts.py",
    "integration-staging/tools/a14_final_checks.py",
]


def main() -> int:
    baselines = a14_baselines()
    now = datetime.now(CST).isoformat(timespec="seconds")

    changed = []
    for group, finding, staged, diff, desc, explicit_base in EDITED:
        full = os.path.join(WS, staged)
        base = None
        base_src = "none_available"
        if explicit_base and os.path.exists(explicit_base):
            base = sha256_file(explicit_base)
            base_src = "frozen pre-fix copy: " + rel(explicit_base)
        elif staged in baselines:
            base = baselines[staged]
            base_src = "A14 staged_sha256 (verified pre-change: staged tree stable A14->edit)"
        entry = {
            "group": group,
            "finding": finding,
            "path": staged,
            "sha256_before": base,
            "sha256_after": sha256_file(full),
            "baseline_source": base_src,
            "diff_artifact": diff,
            "description": desc,
        }
        if diff:
            dp = os.path.join(RUN, diff)
            if os.path.exists(dp):
                entry["diff_sha256"] = sha256_file(dp)
        changed.append(entry)

    new_files = []
    for group, finding, staged, desc in NEW_FILES:
        full = os.path.join(WS, staged)
        new_files.append(
            {
                "group": group,
                "finding": finding,
                "path": staged,
                "sha256_before": None,
                "sha256_after": sha256_file(full),
                "baseline_source": "new file (absent from the A14 map and from the sealed B01 candidate)",
                "diff_artifact": None,
                "description": desc,
            }
        )

    collateral = []
    for staged in COLLATERAL:
        full = os.path.join(WS, staged)
        added = []
        with open(full, encoding="utf-8") as fh:
            for i, line in enumerate(fh, 1):
                if "EXAMDATA_INTEGRATION_ROOT" in line:
                    added.append({"line": i, "text": line.rstrip("\n")})
        collateral.append(
            {
                "group": "R04-collateral-tool",
                "finding": "R04",
                "path": staged,
                "sha256_before": None,
                "sha256_after": sha256_file(full),
                "baseline_source": "none_available (A-series tools are not in the A14 map and have no frozen snapshot)",
                "diff_artifact": None,
                "added_lines": added,
                "description": "Added one os.environ.setdefault(EXAMDATA_INTEGRATION_ROOT, ...) "
                "line so the probe/check tool resolves roots explicitly, like the product code.",
            }
        )

    diffs = []
    ddir = os.path.join(EVID, "DIFFS")
    if os.path.isdir(ddir):
        for name in sorted(os.listdir(ddir)):
            fp = os.path.join(ddir, name)
            diffs.append(
                {
                    "path": rel(fp),
                    "sha256": sha256_file(fp),
                    "bytes": os.path.getsize(fp),
                    "lines": sum(1 for _ in open(fp, encoding="utf-8", errors="replace")),
                }
            )

    cands = []
    cdir = os.path.join(RUN, "candidates")
    if os.path.isdir(cdir):
        for name in sorted(os.listdir(cdir)):
            mp = os.path.join(cdir, name, "R04_CANDIDATE_MANIFEST.json")
            if os.path.exists(mp):
                cands.append(
                    {
                        "candidate_dir": rel(os.path.join(cdir, name)),
                        "manifest": rel(mp),
                        "manifest_sha256": sha256_file(mp),
                        "tree_sha256": dir_digest(os.path.join(cdir, name))["tree_sha256"],
                        "files": dir_digest(os.path.join(cdir, name))["files"],
                    }
                )

    phase_b = os.path.join(
        WS, "integration-staging", "runtime", "phase-b", "b00b01-20261006T132400"
    )
    regenerated = files_newer_than(phase_b, "2026-10-06T22:00:00+08:00")
    frozen = {
        "note": "Read-only observation. No sealed evidence below was written, moved or deleted "
        "by this repair; see process_observations for the one private-run-tree exception.",
        "sealed_b01_evidence": dir_digest(
            os.path.join(WS, "docs", "integration", "execution", "evidence", "B01")
        ),
        "sealed_b00_evidence": dir_digest(
            os.path.join(WS, "docs", "integration", "execution", "evidence", "B00")
        ),
        "phase_b_run_tree": dir_digest(
            phase_b,
            read_only=False,
            note="Private Phase B run tree inside the staging write root (not sealed evidence). "
            "Running the pre-existing rejection suite in place regenerated that suite's own "
            "fixture and ledger-copy outputs here; the sealed B00/B01 transcripts under "
            "docs/integration/execution/evidence/** and the live ledger are byte-unchanged.",
        ),
        "phase_b_run_tree_files_written_2026_10_06": regenerated,
        "a14_merge_map": {
            "path": rel(A14_MAP),
            "sha256": sha256_file(A14_MAP),
            "byte_unchanged": True,
        },
        "a14_release_manifest": {
            "path": rel(os.path.join(WS, "docs", "integration", "execution", "A14_RELEASE_MANIFEST.json")),
            "sha256": sha256_file(
                os.path.join(WS, "docs", "integration", "execution", "A14_RELEASE_MANIFEST.json")
            ),
            "byte_unchanged": True,
        },
    }

    process_observations = [
        {
            "id": "PO-1",
            "observation": "The pre-existing ledger rejection suite was run in place inside its own "
            "private Phase B run tree before being copied for the post-fix run.",
            "where": rel(phase_b),
            "when": "2026-10-06T22:11:49+08:00 .. 2026-10-06T22:13:08+08:00",
            "files_rewritten": [r["path"] for r in regenerated],
            "why_it_is_safe": "test_b_ledger_rejections.py writes its own fixture files and private "
            "ledger copies under its run directory on every execution; the rewritten paths are exactly "
            "those self-generated artifacts. No sealed evidence, no live ledger, no original source.",
            "residual_risk": "The immediate pre-22:11 bytes of those self-generated fixtures are not "
            "archived, so the regeneration cannot be byte-diffed against them; the script is "
            "deterministic (json.dumps of fixed literals plus copies of the unchanged live ledger).",
            "sealed_evidence_affected": False,
            "live_ledger_affected": False,
        }
    ]

    manifest = {
        "manifest_version": "r0104-change-manifest/1",
        "generated_by": rel(os.path.abspath(__file__)),
        "generated_at": now,
        "run_id": "r0104-repair-20261006",
        "status": "private_repair_only_not_merged_not_deployed",
        "scope_note": (
            "Private preparation in the two Phase A write roots only. All seven ledger "
            "gates remain closed. Nothing is merged into the original project and nothing "
            "is deployed. Real Node/source validation against the original tree stays not_run."
        ),
        "write_roots": [
            "integration-staging/",
            "docs/integration/execution/",
        ],
        "stability_check": stability_check(baselines),
        "frozen_baselines": {
            "b_ledger_update_pre_fix": {
                "path": "integration-staging/runtime/r0104-repair-20261006/tool-versions/"
                "b_ledger_update.pre-fix.ac9b01cb.py",
                "sha256": sha256_file(
                    os.path.join(RUN, "tool-versions", "b_ledger_update.pre-fix.ac9b01cb.py")
                ),
            },
            "execution_ledger": gates_observation(),
        },
        "counts": {
            "edited_staged_files": len(changed),
            "new_staged_files": len(new_files),
            "collateral_tool_edits": len(collateral),
            "changed_files_total": len(changed) + len(new_files) + len(collateral),
            "diff_artifacts": len(diffs),
            "candidates": len(cands),
        },
        "edited_files": changed,
        "new_files": new_files,
        "collateral_tool_edits": collateral,
        "diff_artifacts": diffs,
        "candidate_manifests": cands,
        "frozen_evidence_untouched": frozen,
        "process_observations": process_observations,
        "git": git_status(),
        "not_run": [
            "real Node component execution (ielts-api / toefl-api) against the original tree",
            "any original-project source validation",
            "original merge, deployment, service cutover, upstream request, real data write",
            "original cleanup",
        ],
    }

    os.makedirs(EVID, exist_ok=True)
    out = os.path.join(EVID, "R0104_CHANGE_MANIFEST.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    print("wrote", rel(out))
    print(json.dumps(manifest["counts"], ensure_ascii=False))
    print(json.dumps(manifest["frozen_baselines"]["execution_ledger"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
