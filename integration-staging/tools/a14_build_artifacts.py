#!/usr/bin/env python3
"""A14 build: file-by-file merge map, proposed release manifest, v2 API reference.

Usage:
  python a14_build_artifacts.py            # (re)generate all four artifacts
  python a14_build_artifacts.py --check    # verify artifacts against disk; rc!=0 on drift

Artifacts (all inside the two Phase A writable roots):
  docs/integration/execution/A14_MERGE_MAP.json       file-by-file merge map (machine-readable)
  docs/integration/execution/A14_MERGE_MAP.md         the same map, reviewable tables
  docs/integration/execution/A14_RELEASE_MANIFEST.json proposed release bundle manifest
  integration-staging/docs/v2-api-reference.md        endpoint table generated from the
                                                      staged app factory's OpenAPI document

The merge map is a *proposal*. It names, for every staged candidate file, the eventual
original target path, the base hash the staged file was prepared from (where one exists),
the Phase B action, and the exact reversal. Nothing here is merged; the original tree is
read-only to this executor.

The map is not a whole-tree replacement: every entry is one file, and every entry can be
reversed on its own. Original files that the merge must modify (the shared app.py, config
surface, docs, frontend server) are listed separately under `planned_original_edits` with
their observed hashes and the packet that owns the edit; they have no staged file yet
because the edit itself is Phase B work.

Read-only towards the original project: the tool hashes original files and reads two
provenance manifests; it never writes outside the two allowlisted roots.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True

HERE = Path(__file__).resolve()
TOOLS = HERE.parent                  # integration-staging/tools
STAGING = TOOLS.parent               # integration-staging
WS = STAGING.parent                  # project root
EXEC = WS / "docs" / "integration" / "execution"
STAGED_DOCS = STAGING / "docs"

MAP_JSON = EXEC / "A14_MERGE_MAP.json"
MAP_MD = EXEC / "A14_MERGE_MAP.md"
RELEASE_JSON = EXEC / "A14_RELEASE_MANIFEST.json"
V2_REF = STAGED_DOCS / "v2-api-reference.md"

MAP_VERSION = "merge-map/1"
RELEASE_VERSION = "release-manifest-proposal/1"

PY_SRC = STAGING / "src" / "examdata_integration"
PY_TARGET = "examdata/src/examdata/integration"

STAGED_ROOTS = {
    "python": STAGING / "src" / "examdata_integration",
    "tests": STAGING / "tests",
    "contracts": STAGING / "contracts",
    "fixtures": STAGING / "fixtures",
    "frontend": STAGING / "frontend",
    "config": STAGING / "config",
    "docs": STAGING / "docs",
}

# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def rel_ws(path: Path) -> str:
    return path.relative_to(WS).as_posix()


SKIP_DIR_NAMES = frozenset({"__pycache__", "pytest-temp", "pytest-cache", "a14-rehearsal"})


def walk(root: Path) -> list[Path]:
    """Product files only: caches, test scratch and the rehearsal sandbox are
    never merge candidates."""
    if not root.exists():
        return []
    return sorted(
        p for p in root.rglob("*")
        if p.is_file() and p.suffix != ".pyc"
        and not (SKIP_DIR_NAMES & set(p.parts)))


def tree_hash(pairs: list[tuple[str, str]]) -> str:
    """Deterministic hash over (relative path, sha256) pairs."""
    blob = "\n".join(f"{rel}:{digest}" for rel, digest in sorted(pairs))
    return sha256_bytes(blob.encode("utf-8"))


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# base observations (read-only towards the original tree)
# --------------------------------------------------------------------------- #


def observe_target(target_rel: str) -> dict:
    path = WS / target_rel
    if not path.exists():
        return {"exists": False, "sha256": None, "size": None}
    if path.is_dir():
        return {"exists": True, "sha256": None, "size": None, "is_dir": True}
    return {"exists": True, "sha256": sha256_file(path), "size": path.stat().st_size}


def make_base(source_rel: str | None, recorded: str | None,
              recorded_at: str | None, recorded_note: str | None = None) -> dict | None:
    """Base record for a staged file copied from an original path."""
    if not source_rel:
        return None
    path = WS / source_rel
    current = sha256_file(path) if path.is_file() else None
    return {
        "source_path": source_rel,
        "sha256_recorded": recorded,
        "recorded_at": recorded_at,
        "sha256_current": current,
        "exists": path.is_file(),
        "drift": bool(recorded and current and recorded != current),
        "note": recorded_note,
    }


def frontend_bases() -> dict[str, dict]:
    manifest = load_json(STAGING / "frontend" / "PROVENANCE.json")
    out: dict[str, dict] = {}
    for entry in manifest.get("files", []):
        if entry.get("source_path"):
            out[entry["path"]] = make_base(
                entry["source_path"], entry.get("source_sha256"), manifest.get("generated_at"))
    return out


def copied_fixture_bases() -> dict[str, dict]:
    manifest = load_json(STAGING / "fixtures" / "PROVENANCE.json")
    out: dict[str, dict] = {}
    for entry in manifest.get("entries", []):
        dest = entry.get("destination_path")
        if not dest or not dest.startswith("integration-staging/fixtures/"):
            continue
        key = dest[len("integration-staging/fixtures/"):]
        out[key] = make_base(
            entry.get("source_path"),
            entry.get("source_sha256_after") or entry.get("source_sha256_before"),
            entry.get("copied_at_local"),
            f"fixture_id={entry.get('fixture_id')}; label={entry.get('label')}")
    return out


# --------------------------------------------------------------------------- #
# merge-map entries
# --------------------------------------------------------------------------- #


class MapBuilder:
    def __init__(self) -> None:
        self.entries: list[dict] = []
        self.not_merged: list[dict] = []
        self.problems: list[str] = []

    def add(self, *, group: str, staged: Path, target: str, kind: str,
            action: str, reversal: str, verification: list[str],
            base: dict | None = None, note: str | None = None) -> None:
        if not staged.is_file():
            self.problems.append(f"{rel_ws(staged)}: staged file missing")
            return
        entry = {
            "id": f"MM-{len(self.entries) + 1:04d}",
            "group": group,
            "staged_path": rel_ws(staged),
            "staged_sha256": sha256_file(staged),
            "size": staged.stat().st_size,
            "kind": kind,
            "proposed_target": target,
            "target_observed": observe_target(target),
            "base": base,
            "phase_b_action": action,
            "reversal": reversal,
            "verification": verification,
        }
        if note:
            entry["note"] = note
        self.entries.append(entry)

    def skip(self, *, staged: Path, reason: str, group: str) -> None:
        self.not_merged.append({
            "staged_path": rel_ws(staged),
            "group": group,
            "reason": reason,
        })


VERIF = {
    "python": [
        "integration-staging/tests (full staged suite: 887 passed at A13 close)",
        "docs/integration/execution/A12_ROUTE_COMPATIBILITY_WORKSHEET.json (route-level legacy parity)",
        "A14 rehearsal: apply/rollback of this file entry (evidence/A14/rehearsal_stdout.txt)",
    ],
    "tests": [
        "the merged tests must pass on the merged tree (plan B09 final acceptance)",
        "A14 rehearsal: apply/rollback of this file entry",
    ],
    "contracts": [
        "tests/test_contracts_schemas.py, tests/test_contracts_identity.py, tests/test_contracts_quality.py",
    ],
    "fixtures": [
        "tests/test_fixture_provenance.py, tests/test_adapters_provenance.py, tests/test_frontend_staged_copy.py",
    ],
    "frontend": [
        "integration-staging/frontend/tests/*.test.mjs (node --test, 27 tests at A13 close)",
    ],
    "config": [
        "tests/test_config_resolution.py, tests/test_config_manifest.py",
    ],
    "docs": [
        "static inspection in A14_REPORT.md; docs publish only after the Phase B release (plan 9.3)",
    ],
}

REQUIREMENTS = [
    {
        "group": "python",
        "requirement": (
            "B01/B02 choose the final module names (plan 3.5). The proposal roots the staged "
            "package at examdata/src/examdata/integration/ (a new subpackage) because the staged "
            "adapters/ and api/ names collide with the existing examdata packages. Re-rooting "
            "module-by-module later is mechanical: every entry is one file. No original file is "
            "overwritten by any python entry; B04 registers the v2 router in the final app.py."),
    },
    {
        "group": "tests",
        "requirement": (
            "Rebase path constants (tests compute STAGING from __file__) onto the merged tree, and "
            "reconcile conftest.py: drop the staging path pins and the original-package import "
            "block, keep the private data-root pinning for integration fixtures. The two harness "
            "self-tests (test_harness_isolation.py, test_node_import_guard.py) only stay if B01 "
            "keeps the corresponding guards."),
    },
    {
        "group": "contracts",
        "requirement": (
            "Keep the schemas/examples at repo level (examdata/contracts/) and copy them into the "
            "release bundle (plan 10.4 lists contracts/schemas). Regenerate only through the "
            "generator (tools/a04_generate_schemas.py), never by hand."),
    },
    {
        "group": "fixtures",
        "requirement": (
            "Fixtures are private test data: no fixture may be presented as real source data, "
            "copied snapshots keep their provenance manifest, and synthetic labels stay visible "
            "(plan 8). The fixture provenance manifests record staging destination paths and must "
            "be reconciled to the merged locations."),
    },
    {
        "group": "frontend",
        "requirement": (
            "B06: reconcile app.js/index.html/README/tests with Kimi's final frontend (the staged "
            "copies are based on the hashes in frontend/PROVENANCE.json). Ensure the merged static "
            "server does not expose frontend/tests/ or frontend/fixtures/, and keep the reversible "
            "examdata.v2-client switch."),
    },
    {
        "group": "config",
        "requirement": (
            "B02: merge the example files into the project configuration surface without changing "
            "existing environment variable names; legacy aliases (IELTS_API_DIR, TOEFL_API_DIR) "
            "keep working and still fail loudly on conflict."),
    },
    {
        "group": "docs",
        "requirement": (
            "Plan 9.3: shared documentation is updated only after the Phase B release. These staged "
            "drafts are the proposed versions; B10 decides final names and folds in the remaining "
            "packets (materials/timetable, deployment)."),
    },
]

NOT_MERGED_REASONS = {
    "tools": "Phase A executor tooling (probes, close patches, checks). Not a product artifact; B01 may reuse individual tools internally.",
    "runtime": "Private staging runtime state (caches, temp, private data roots, ledger patches). Never merged.",
    "components": "Synthetic fixture component for the staged Node runner (fake-cli) and its manifest. The runner and the manifest format merge with src/; the fake component must not be packaged.",
    "pytest.ini": "Staging test configuration (testpaths, pythonpath=src, private cache dirs). The merged project uses its own test configuration.",
    "README.md": "Staging-tree orientation document. Superseded after merge by the proposed docs/ set.",
}


def build_entries(builder: MapBuilder) -> None:
    fe_bases = frontend_bases()
    fx_bases = copied_fixture_bases()

    # --- python package ---------------------------------------------------- #
    for f in walk(PY_SRC):
        rel = f.relative_to(PY_SRC).as_posix()
        note = None
        if rel == "testing/guards.py":
            note = ("Phase A isolation guard (blocks importing the original examdata package). "
                    "B01 must neutralise that block before merging; keep the file only if the "
                    "merged tests still need the guard.")
        elif rel.startswith("testing/"):
            note = "Phase A harness support; referenced by staged tests and conftest."
        builder.add(
            group="python", staged=f, target=f"{PY_TARGET}/{rel}", kind="new_file",
            action="add_file", reversal="delete_file", verification=VERIF["python"], note=note)

    # --- tests -------------------------------------------------------------- #
    for f in walk(STAGING / "tests"):
        rel = f.relative_to(STAGING / "tests").as_posix()
        note = None
        if rel == "conftest.py":
            note = ("reconcile: drop the staging path pins and the original-package block; keep "
                    "private data-root pinning for the integration fixtures")
        elif rel in ("test_harness_isolation.py", "test_node_import_guard.py"):
            note = "harness self-test: merge only if B01 keeps the corresponding guard"
        builder.add(
            group="tests", staged=f, target=f"examdata/tests/integration/{rel}", kind="new_file",
            action="add_file", reversal="delete_file", verification=VERIF["tests"], note=note)

    # --- contracts ---------------------------------------------------------- #
    for f in walk(STAGING / "contracts"):
        rel = f.relative_to(STAGING / "contracts").as_posix()
        builder.add(
            group="contracts", staged=f, target=f"examdata/contracts/{rel}", kind="new_file",
            action="add_file", reversal="delete_file", verification=VERIF["contracts"])

    # --- fixtures ----------------------------------------------------------- #
    for f in walk(STAGING / "fixtures"):
        rel = f.relative_to(STAGING / "fixtures").as_posix()
        base = fx_bases.get(rel)
        kind = "copied_snapshot" if base else "new_file"
        note = None
        if rel.endswith("PROVENANCE.json") or rel.endswith("PROVENANCE.md") or rel == "README.md":
            note = "fixture provenance/documentation; destination paths recorded inside are staging paths and must be reconciled"
        builder.add(
            group="fixtures", staged=f, target=f"examdata/tests/integration/fixtures/{rel}",
            kind=kind, action="add_file" if kind == "new_file" else "verify_copy",
            reversal="delete_file", verification=VERIF["fixtures"], base=base, note=note)

    # --- frontend ----------------------------------------------------------- #
    for f in walk(STAGING / "frontend"):
        rel = f.relative_to(STAGING / "frontend").as_posix()
        if rel.endswith("PROVENANCE.json"):
            builder.skip(staged=f, group="frontend",
                         reason="staging provenance consumed by B01; not a product file")
            continue
        base = fe_bases.get(rel)
        if base:
            kind = "copied_snapshot" if base["sha256_recorded"] == sha256_file(f) else "modified_copy"
            action = "verify_copy" if kind == "copied_snapshot" else "reconcile_modify"
            reversal = "restore_base_bytes"
        else:
            kind, action, reversal = "new_file", "add_file", "delete_file"
        note = None
        if rel.startswith("tests/") or rel.startswith("fixtures/"):
            note = ("test-only asset: the merged static server must not expose frontend/tests/ or "
                    "frontend/fixtures/")
        builder.add(group="frontend", staged=f, target=f"frontend/{rel}", kind=kind,
                    action=action, reversal=reversal, verification=VERIF["frontend"],
                    base=base, note=note)

    # --- config ------------------------------------------------------------- #
    config_targets = {
        "staging-config.example.json": "examdata/config.example.json",
        "staging.env.example": "examdata/.env.example",
    }
    for name, target in config_targets.items():
        builder.add(group="config", staged=STAGING / "config" / name, target=target,
                    kind="new_file", action="add_file", reversal="delete_file",
                    verification=VERIF["config"],
                    note="example only; contains no secrets and no live paths")
    builder.skip(staged=STAGING / "config" / "README.md", group="config",
                 reason="staging notes; the configuration precedence text is folded into docs/integration-guide.md")

    # --- docs (proposed merged documentation) ------------------------------- #
    doc_notes = {
        "README.md": "staged docs index; not published until after the Phase B release",
        "integration-guide.md": "proposed merged integration guide (plan 9.3 checklist)",
        "release-and-rollback.md": "proposed release and rollback instructions (plan 10.4)",
        "v2-api-reference.md": "generated from the staged app factory's OpenAPI document",
    }
    for f in walk(STAGED_DOCS):
        rel = f.relative_to(STAGED_DOCS).as_posix()
        builder.add(group="docs", staged=f, target=f"examdata/docs/{rel}", kind="new_file",
                    action="add_file", reversal="delete_file", verification=VERIF["docs"],
                    note=doc_notes.get(rel))

    # --- explicitly not merged ---------------------------------------------- #
    for group in ("tools", "runtime", "components"):
        for f in walk(STAGING / group):
            builder.skip(staged=f, group=group, reason=NOT_MERGED_REASONS[group])
    builder.skip(staged=STAGING / "pytest.ini", group="root", reason=NOT_MERGED_REASONS["pytest.ini"])
    builder.skip(staged=STAGING / "README.md", group="root", reason=NOT_MERGED_REASONS["README.md"])


# --------------------------------------------------------------------------- #
# planned original edits (no staged file yet; the edit itself is Phase B work)
# --------------------------------------------------------------------------- #

PLANNED_EDITS = [
    {
        "target_path": "examdata/src/examdata/api/app.py",
        "packet": "B04",
        "change": "register the staged v2 routes in the shared application (include_router / factory hook) without removing or shadowing any legacy route; keep path ordering and operation IDs",
        "reversal": "restore the recorded base bytes (hash above)",
        "note": "shared file; Kimi-owned and protected in Phase A",
    },
    {
        "target_path": "examdata/pyproject.toml",
        "packet": "B02",
        "change": "provisional: package-data/packaging delta only if the merge needs it ([tool.setuptools.packages.find] already covers examdata.integration.*); no new runtime dependencies are proposed",
        "reversal": "restore the recorded base bytes",
        "note": "shared file; Kimi-owned and protected in Phase A",
    },
    {
        "target_path": "examdata/cli.py",
        "packet": "B02/B10",
        "change": "provisional: add unified commands only after scanning for command-name conflicts; keep query commands separate from refresh/write commands",
        "reversal": "restore the recorded base bytes",
        "note": "shared file; no staged replacement exists",
    },
    {
        "target_path": "frontend/server.mjs",
        "packet": "B06",
        "change": "provisional: serve the staged v2 client behind the reversible flag and keep tests/ and fixtures/ out of the static surface",
        "reversal": "restore the recorded base bytes",
        "note": "frontend is Kimi-owned; the staged copy replaces source requests only in the copy",
    },
    {
        "target_path": "examdata/docs/API.md",
        "packet": "B10",
        "change": "provisional: publish the v2 reference and the compatibility summary after the release (plan 9.3)",
        "reversal": "restore the recorded base bytes",
        "note": "documentation updates happen only after the Phase B release",
    },
    {
        "target_path": "docs/PROJECT_STATUS.md",
        "packet": "B10",
        "change": "provisional: replace the planning status with the delivered status after the merge",
        "reversal": "restore the recorded base bytes",
        "note": "workspace-level document; read-only in Phase A",
    },
]


def build_planned_edits() -> list[dict]:
    out = []
    for item in PLANNED_EDITS:
        observed = observe_target(item["target_path"])
        out.append({
            "target_path": item["target_path"],
            "base_sha256": observed["sha256"],
            "base_exists": observed["exists"],
            "observed_at": None,  # filled by the caller (single timestamp)
            "packet": item["packet"],
            "change": item["change"],
            "reversal": item["reversal"],
            "note": item["note"],
        })
    return out


# --------------------------------------------------------------------------- #
# active-owner deferred files
# --------------------------------------------------------------------------- #

ACTIVE_OWNER_DEFERRED = [
    {
        "path": "examdata/src/examdata/materials/**",
        "reason": "Kimi-owned active feature; protected in Phase A (worksheet rows deferred_active_owner)",
        "revisit_at": "B05 after explicit human release",
    },
    {
        "path": "examdata/src/examdata/timetable/**",
        "reason": "Kimi-owned active feature (historical timetables); protected in Phase A",
        "revisit_at": "B05 after explicit human release",
    },
    {
        "path": "examdata/src/examdata/api/app.py",
        "reason": "shared route module; Kimi edits it concurrently; no staged file replaces it",
        "revisit_at": "B04",
    },
    {
        "path": "examdata/src/examdata/api/{unified,ielts,toefl}.py",
        "reason": "legacy route modules preserved verbatim; the compatibility adapters call them only by contract",
        "revisit_at": "B02/B04",
    },
    {
        "path": "examdata/pyproject.toml, examdata/cli.py, examdata/README.md",
        "reason": "shared project files; protected in Phase A",
        "revisit_at": "B02/B10",
    },
    {
        "path": "frontend/**",
        "reason": "Kimi-owned frontend; the staged copy is reconciled at B06, never overwritten",
        "revisit_at": "B06",
    },
    {
        "path": "ielts-api/**, toefl-api/**",
        "reason": "original Node components: not executed, not copied, not packaged in Phase A",
        "revisit_at": "B02 (component packaging)",
    },
    {
        "path": "ielts-data/**, cie-location-batch/**, cie-index-batch-2026-10-01/**, cie-question-crops/**",
        "reason": "business data and stopped batch state; no live database or batch access in Phase A",
        "revisit_at": "B08 after a separate data authorization",
    },
    {
        "path": "docs/integration/MASTER_EXECUTION_PLAN_EN.md, docs/integration/EXECUTOR_PROMPT_EN.md, docs/integration/ROUTE_INVENTORY_CURRENT.json, docs/PROJECT_STATUS.md",
        "reason": "governing planning inputs; read-only",
        "revisit_at": "B10 (status documents only)",
    },
]


def build_map() -> dict:
    builder = MapBuilder()
    build_entries(builder)
    stamp = now_iso()
    entries = builder.entries
    planned = build_planned_edits()
    for item in planned:
        item["observed_at"] = stamp

    groups: dict[str, dict] = {}
    for entry in entries:
        g = groups.setdefault(entry["group"], {"files": 0, "bytes": 0, "kinds": {},
                                               "actions": {}, "reversal": {}})
        g["files"] += 1
        g["bytes"] += entry["size"]
        g["kinds"][entry["kind"]] = g["kinds"].get(entry["kind"], 0) + 1
        g["actions"][entry["phase_b_action"]] = g["actions"].get(entry["phase_b_action"], 0) + 1
        g["reversal"][entry["reversal"]] = g["reversal"].get(entry["reversal"], 0) + 1

    drift = [e["staged_path"] for e in entries
             if e.get("base") and e["base"].get("drift")]
    copied = [e for e in entries if e["kind"] == "copied_snapshot"]
    modified = [e for e in entries if e["kind"] == "modified_copy"]

    payload = {
        "map_version": MAP_VERSION,
        "generated_by": "integration-staging/tools/a14_build_artifacts.py",
        "generated_at": stamp,
        "mode": "PHASE_A_ISOLATED_ONLY",
        "status": "proposed_staged_not_merged_not_deployed",
        "scope_note": (
            "One entry per staged file: eventual original target path, the base hash it was "
            "prepared from (where one exists), the Phase B action, and the exact reversal. "
            "No whole-tree replacement: every entry is individually applicable and individually "
            "reversible."),
        "baseline": {
            "examdata_head": "8da3a0917e017a6cbf5d3e58e1fbeb9d0b0b83c8",
            "examdata_head_observed_at": "2026-10-05T18:02+08:00",
            "kimi_editable": True,
            "policy": "point-in-time hashes; the active owner may change original files at any time and no drift is repaired by this executor",
        },
        "target_layout": {
            "python": PY_TARGET + "/...",
            "tests": "examdata/tests/integration/...",
            "contracts": "examdata/contracts/...",
            "fixtures": "examdata/tests/integration/fixtures/...",
            "frontend": "frontend/...",
            "config": ["examdata/config.example.json", "examdata/.env.example"],
            "docs": "examdata/docs/...",
            "layout_decision": (
                "proposal only: B01/B02 choose the final module names after checking Kimi's final "
                "tree (plan 3.5); re-rooting is mechanical because every entry is one file"),
        },
        "counts": {
            "entries": len(entries),
            "bytes": sum(e["size"] for e in entries),
            "groups": groups,
            "copied_snapshot": len(copied),
            "modified_copy": len(modified),
            "not_merged": len(builder.not_merged),
            "planned_original_edits": len(planned),
            "base_files_observed": sum(1 for e in entries if e.get("base")),
            "base_drift": len(drift),
        },
        "entries": entries,
        "planned_original_edits": planned,
        "not_merged": builder.not_merged,
        "active_owner_deferred": ACTIVE_OWNER_DEFERRED,
        "requirements_for_merge": REQUIREMENTS,
        "problems": builder.problems,
    }
    return payload


# --------------------------------------------------------------------------- #
# merge map markdown
# --------------------------------------------------------------------------- #


def render_map_md(payload: dict) -> str:
    lines: list[str] = []
    lines.append("<!-- generated_by: integration-staging/tools/a14_build_artifacts.py -->")
    lines.append(f"<!-- generated_at: {payload['generated_at']} -->")
    lines.append("")
    lines.append("# A14 — proposed file-by-file merge map")
    lines.append("")
    lines.append("**Status:** proposed, staged only — **not merged, not deployed**. All seven Phase B")
    lines.append("gates remain closed. Generated by `integration-staging/tools/a14_build_artifacts.py`.")
    lines.append("")
    lines.append("One entry per staged file: the eventual original target path, the base hash it was")
    lines.append("prepared from (where one exists), the Phase B action, and the exact reversal. There is")
    lines.append("no whole-tree replacement; every entry can be applied and reversed on its own. The")
    lines.append("machine-readable form is `A14_MERGE_MAP.json`.")
    lines.append("")
    counts = payload["counts"]
    lines.append(f"- merge candidates: **{counts['entries']}** files "
                 f"({counts['bytes']} bytes), {counts['copied_snapshot']} copied snapshots, "
                 f"{counts['modified_copy']} modified copies")
    lines.append(f"- not merged (staging-only): **{counts['not_merged']}** files")
    lines.append(f"- planned original edits (no staged file yet): **{counts['planned_original_edits']}**")
    lines.append(f"- base hashes recorded: **{counts['base_files_observed']}**; base drift observed: "
                 f"**{counts['base_drift']}**")
    lines.append("")
    lines.append("## Groups")
    lines.append("")
    lines.append("| group | files | bytes | kinds | actions | reversal |")
    lines.append("| --- | ---: | ---: | --- | --- | --- |")
    for name in sorted(counts["groups"]):
        g = counts["groups"][name]
        kinds = ", ".join(f"{k}×{v}" for k, v in sorted(g["kinds"].items()))
        actions = ", ".join(f"{k}×{v}" for k, v in sorted(g["actions"].items()))
        reversal = ", ".join(f"{k}×{v}" for k, v in sorted(g["reversal"].items()))
        lines.append(f"| `{name}` | {g['files']} | {g['bytes']} | {kinds} | {actions} | {reversal} |")
    lines.append("")
    lines.append("## Requirements per group")
    lines.append("")
    for item in payload["requirements_for_merge"]:
        lines.append(f"- **`{item['group']}`** — {item['requirement']}")
    lines.append("")

    for name in sorted(counts["groups"]):
        rows = [e for e in payload["entries"] if e["group"] == name]
        lines.append(f"## `{name}` — {len(rows)} files")
        lines.append("")
        lines.append("| # | staged | proposed target | kind | action | base | reversal |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- |")
        for e in rows:
            base = e.get("base")
            if base:
                base_cell = (f"`{base['source_path']}` "
                             f"`{(base['sha256_recorded'] or '')[:12]}`")
                if base.get("drift"):
                    base_cell += " **drift**"
            else:
                base_cell = "absent at baseline" if not e["target_observed"]["exists"] else "—"
            lines.append(
                f"| {e['id'][3:]} | `{e['staged_path']}` | `{e['proposed_target']}` | "
                f"{e['kind']} | {e['phase_b_action']} | {base_cell} | {e['reversal']} |")
        notes = [e for e in rows if e.get("note")]
        if notes:
            lines.append("")
            lines.append("Notes:")
            lines.append("")
            for e in notes:
                lines.append(f"- `{e['staged_path']}` — {e['note']}")
        lines.append("")

    lines.append("## Planned original edits (no staged file yet)")
    lines.append("")
    lines.append("These original files must change in Phase B; the change itself is the packet's work,")
    lines.append("so only the base hash and the reversal are recorded here.")
    lines.append("")
    lines.append("| target | packet | base sha256 | change | reversal |")
    lines.append("| --- | --- | --- | --- | --- |")
    for item in payload["planned_original_edits"]:
        base = f"`{(item['base_sha256'] or 'missing')[:12]}`" if item["base_exists"] else "missing"
        lines.append(f"| `{item['target_path']}` | {item['packet']} | {base} | "
                     f"{item['change']} | {item['reversal']} |")
    lines.append("")

    lines.append("## Not merged (staging-only)")
    lines.append("")
    lines.append("| staged | group | reason |")
    lines.append("| --- | --- | --- |")
    for item in payload["not_merged"]:
        lines.append(f"| `{item['staged_path']}` | {item['group']} | {item['reason']} |")
    lines.append("")

    lines.append("## Active-owner deferred files")
    lines.append("")
    lines.append("| path | reason | revisit |")
    lines.append("| --- | --- | --- |")
    for item in payload["active_owner_deferred"]:
        lines.append(f"| `{item['path']}` | {item['reason']} | {item['revisit_at']} |")
    lines.append("")
    if payload["problems"]:
        lines.append("## Problems")
        lines.append("")
        for p in payload["problems"]:
            lines.append(f"- {p}")
        lines.append("")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- #
# v2 API reference (generated from the staged app factory)
# --------------------------------------------------------------------------- #


def build_v2_reference() -> str:
    import os  # R04: explicit deployment root for product code

    src = str(STAGING / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    os.environ.setdefault("EXAMDATA_INTEGRATION_ROOT", str(STAGING))
    from examdata_integration.api.app import create_app  # noqa: E402
    from examdata_integration.api import links  # noqa: E402

    app = create_app()
    spec = app.openapi()
    routes = sorted((path, method, op) for path, ops in spec["paths"].items()
                    for method, op in ops.items())

    lines: list[str] = []
    lines.append("<!-- generated_by: integration-staging/tools/a14_build_artifacts.py -->")
    lines.append("")
    lines.append("# v2 API reference (staged proposal)")
    lines.append("")
    lines.append("Generated from the OpenAPI document of the isolated Phase A application factory")
    lines.append("(`examdata_integration.api.app.create_app`) over private synthetic fixtures. This is")
    lines.append("**not** a deployed endpoint list: the v2 routes are registered in the shared")
    lines.append("application only in Phase B (B04), and the production dataset replaces the fixtures.")
    lines.append("")
    lines.append(f"- prefix: `{links.PREFIX}`")
    lines.append(f"- envelope schema: `examdata.v2/1`")
    lines.append(f"- routes in this document: **{len(routes)}**")
    lines.append(f"- app title: {spec['info']['title']}")
    lines.append("")
    lines.append("| method | path | operationId | tags | summary |")
    lines.append("| --- | --- | --- | --- | --- |")
    for path, method, op in routes:
        tags = ", ".join(op.get("tags", []))
        summary = (op.get("summary") or "").replace("|", "\\|")
        lines.append(f"| {method.upper()} | `{path}` | `{op.get('operationId', '')}` | {tags} | {summary} |")
    lines.append("")
    lines.append("Every JSON response is the `examdata.v2/1` envelope; binary content and crop routes")
    lines.append("stream fixture samples with the same error envelope for 404/413/416. The error map,")
    lines.append("pagination and completeness semantics are defined by the staged contracts")
    lines.append("(`examdata_integration/contracts`, `api/envelope.py`, `api/pagination.py`).")
    lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# release manifest
# --------------------------------------------------------------------------- #

PYPROJECT_DEPS = [
    "httpx", "beautifulsoup4", "lxml", "sqlalchemy", "pydantic", "pydantic-settings",
    "pymupdf", "typer", "rich", "fastapi", "uvicorn",
]

NODE_COMPONENTS = [
    {"component_id": "ielts_api", "path": "ielts-api", "entry_point": "ielts-cli.mjs",
     "runtime": "node", "packaging": "B02 records the final baseline and packages the component"},
    {"component_id": "toefl_api", "path": "toefl-api", "entry_point": "toefl-cli.mjs",
     "runtime": "node", "packaging": "B02 records the final baseline and packages the component"},
]

SMOKE_CHECKS = [
    {
        "name": "offline doctor",
        "staged_command": "examdata/.venv/Scripts/python.exe -c \"import sys; sys.path.insert(0,'integration-staging/src'); from examdata_integration.runtime import doctor; print(doctor.report())\"",
        "proves": "configuration resolves and components are discoverable without touching a source",
        "proven_in": "integration-staging/tests/test_config_manifest.py, test_config_resolution.py",
    },
    {
        "name": "v2 app factory",
        "staged_command": "examdata/.venv/Scripts/python.exe integration-staging/tools/a10_probe_api.py",
        "proves": "OpenAPI and runtime responses agree; envelope and error map hold",
        "proven_in": "docs/integration/execution/evidence/A10/api_stdout.txt",
    },
    {
        "name": "Node runner",
        "staged_command": "examdata/.venv/Scripts/python.exe integration-staging/tools/a06_probe_runner.py",
        "proves": "controlled runner: allowlist, budgets, classification, no orphan process",
        "proven_in": "docs/integration/execution/evidence/A06/",
    },
    {
        "name": "catalog build, publish, rollback",
        "staged_command": "examdata/.venv/Scripts/python.exe integration-staging/tools/a14_rehearsal.py",
        "proves": "revision pointer publication and rollback on private fixtures",
        "proven_in": "docs/integration/execution/evidence/A14/rehearsal_stdout.txt",
    },
    {
        "name": "frontend fixture flows",
        "staged_command": "node --test integration-staging/frontend/tests/*.test.mjs",
        "proves": "staged client and fixture server flows over 127.0.0.1 only",
        "proven_in": "docs/integration/execution/evidence/A13/node_tests_stdout.txt",
    },
]

ROLLBACK_UNITS = [
    {
        "unit": "code release",
        "reversal": "per-file: restore the recorded base bytes for every modified entry, delete every added entry (A14_MERGE_MAP.json reversal column)",
        "rehearsed": "A14 file rehearsal",
    },
    {
        "unit": "component manifest",
        "reversal": "restore the previous manifest file; component discovery is re-read from disk, no cached state",
        "rehearsed": "A14 manifest rehearsal",
    },
    {
        "unit": "data revision pointer",
        "reversal": "RevisionPublisher.rollback() points current back at the retained previous revision; both revisions stay readable",
        "rehearsed": "A14 pointer rehearsal",
    },
    {
        "unit": "database backup",
        "reversal": "restore the recorded backup, then reconcile writes made after it (never restore over new writes without freezing them)",
        "rehearsed": "not_run — no live database is touched in Phase A; B08",
    },
    {
        "unit": "frontend switch",
        "reversal": "set examdata.v2-client=off (reversible marker) or remove it to switch back on; no file change needed",
        "rehearsed": "A14 frontend switch rehearsal",
    },
    {
        "unit": "job checkpoint",
        "reversal": "nothing to reverse: the operations readers are read-only and never rewrite a checkpoint",
        "rehearsed": "A14 checkpoint rehearsal",
    },
]

EXCLUSIONS = [
    "live databases and business data (examdata .db files, ielts-data corpus, CIE batch state)",
    "credentials, API keys, tokens and any secret",
    "Kimi-owned active modules (materials, timetable) and Kimi's in-flight shared-file edits",
    "the synthetic fixture component (components/fake-node-cli) and its manifest",
    "Phase A tooling, private runtime state and staging provenance manifests",
]


def build_release_manifest(map_payload: dict) -> dict:
    import importlib.metadata as md

    deps = {}
    for name in PYPROJECT_DEPS:
        try:
            deps[name] = md.version(name)
        except Exception:
            deps[name] = "not observed in the shared venv"
    try:
        deps["pytest"] = md.version("pytest")
    except Exception:
        deps["pytest"] = "not observed"

    node = []
    for item in NODE_COMPONENTS:
        entry_point = WS / item["path"] / item["entry_point"]
        node.append({
            **item,
            "entry_point_sha256": sha256_file(entry_point) if entry_point.is_file() else None,
            "observed_at": map_payload["generated_at"],
            "hash_note": "point-in-time observation; the final baseline hash is recorded at packaging time (B02/B09)",
            "executed_in_phase_a": False,
        })

    py_pairs = [(e["proposed_target"], e["staged_sha256"])
                for e in map_payload["entries"] if e["group"] == "python"]
    test_pairs = [(e["proposed_target"], e["staged_sha256"])
                  for e in map_payload["entries"] if e["group"] == "tests"]
    fixture_pairs = [(e["proposed_target"], e["staged_sha256"])
                     for e in map_payload["entries"] if e["group"] == "fixtures"]
    contract_pairs = [(e["proposed_target"], e["staged_sha256"])
                      for e in map_payload["entries"] if e["group"] == "contracts"]
    frontend_pairs = [(e["proposed_target"], e["staged_sha256"])
                      for e in map_payload["entries"] if e["group"] == "frontend"]

    return {
        "manifest_version": RELEASE_VERSION,
        "generated_by": "integration-staging/tools/a14_build_artifacts.py",
        "generated_at": map_payload["generated_at"],
        "status": "proposed_staged_not_merged_not_deployed",
        "release_id": "examdata-integration-phasea-proposal",
        "bundle_note": (
            "Proposal for the release bundle in plan 10.4. Everything listed is staged; the "
            "bundle has not been built, installed, merged or deployed, and remote deployment "
            "remains not_run."),
        "python": {
            "distribution": "examdata",
            "version": "0.1.0 (existing); B02 decides whether the integration ships in the same distribution",
            "staged_package": PY_TARGET,
            "packaging_proposal": (
                "[tool.setuptools.packages.find] where=[\"src\"] already covers the new "
                "examdata.integration.* subpackage; no new runtime dependency is introduced by the "
                "staged modules (stdlib plus the existing fastapi/starlette stack). If any module "
                "later ships data inside the package, add package-data entries then."),
            "wheel": {
                "built": False,
                "blocked_by": (
                    "setuptools/wheel/build are absent from the shared venv and plan 14 forbids "
                    "installing into it; an isolated build would need a network fetch of the build "
                    "backend, which is prohibited in Phase A"),
                "b09_command": (
                    "examdata/.venv/Scripts/python.exe -m pip wheel --no-index --no-deps "
                    "--wheel-dir <release-dir> examdata  # run only in an authorized environment "
                    "that has a build backend, then clean-install test per plan 10.4"),
            },
            "modules": {"count": len(py_pairs), "tree_sha256": tree_hash(py_pairs)},
        },
        "node_components": node,
        "component_manifest": {
            "format": "examdata.component-manifest/1",
            "authored_in": "B02",
            "note": ("the staged components/manifest.json is a synthetic fixture for the runner "
                     "tests and is not shipped; the real manifest is authored from the final "
                     "baseline in B02"),
        },
        "frontend": {
            "count": len(frontend_pairs),
            "tree_sha256": tree_hash(frontend_pairs),
            "merge_requirement": "B06 reconciliation; tests/ and fixtures/ must stay out of the served surface",
        },
        "contracts_schemas": {
            "count": len(contract_pairs),
            "tree_sha256": tree_hash(contract_pairs),
            "proposed_location": "examdata/contracts/ (repo level; copied into the release bundle)",
        },
        "tests": {
            "count": len(test_pairs),
            "tree_sha256": tree_hash(test_pairs),
            "note": "shipped for the merged test suite; path constants are rebased in B01",
        },
        "fixtures": {
            "count": len(fixture_pairs),
            "tree_sha256": tree_hash(fixture_pairs),
            "note": "private test data; synthetic and copied-snapshot labels are preserved",
        },
        "dependency_versions": {
            "source": "read-only importlib.metadata query against the shared venv",
            "declared_in": "examdata/pyproject.toml (existing requires)",
            "observed": deps,
        },
        "configuration_example": {
            "staged": ["integration-staging/config/staging-config.example.json",
                       "integration-staging/config/staging.env.example"],
            "proposed_targets": ["examdata/config.example.json", "examdata/.env.example"],
            "contains_secrets": False,
        },
        "migration_tools": [
            {"tool": "examdata_integration.catalog.builder", "role": "build a catalog revision from staged/approved sources"},
            {"tool": "examdata_integration.catalog.revision.RevisionPublisher", "role": "publish/rollback the revision pointer atomically"},
            {"tool": "integration-staging/tools/a14_rehearsal.py", "role": "apply/rollback rehearsal on private fixtures"},
        ],
        "smoke_checks": SMOKE_CHECKS,
        "rollback_instructions": {
            "document": "integration-staging/docs/release-and-rollback.md",
            "units": ROLLBACK_UNITS,
        },
        "exclusions": EXCLUSIONS,
        "gates": {
            "remote_deployment_authorized": False,
            "original_paths_released": False,
            "database_migration_authorized": False,
            "cie_resume_authorized": False,
        },
        "not_run": [
            "wheel build and clean-directory installation test (B09)",
            "real-data migration and restore (B08)",
            "deployment to any target (no authorization)",
        ],
    }


# --------------------------------------------------------------------------- #
# write / check
# --------------------------------------------------------------------------- #


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def write_json(path: Path, payload: dict) -> None:
    write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def strip_stamp(text: str) -> str:
    return "\n".join(line for line in text.splitlines()
                     if "generated_at" not in line and "generated_at:" not in line)


def check() -> int:
    problems: list[str] = []
    if not MAP_JSON.is_file():
        problems.append(f"missing {rel_ws(MAP_JSON)}")
        payload = None
    else:
        payload = load_json(MAP_JSON)

    if payload is not None:
        if payload.get("map_version") != MAP_VERSION:
            problems.append(f"map_version unexpected: {payload.get('map_version')!r}")
        entries = payload.get("entries", [])
        if payload.get("problems"):
            problems.append(f"map carries problems: {payload['problems']}")
        for entry in entries:
            staged = WS / entry["staged_path"]
            if not staged.is_file():
                problems.append(f"{entry['staged_path']}: staged file missing")
                continue
            if sha256_file(staged) != entry["staged_sha256"]:
                problems.append(f"{entry['staged_path']}: staged sha256 drifted from the map")
            base = entry.get("base")
            if base:
                source = WS / base["source_path"]
                if not source.is_file():
                    problems.append(f"{entry['staged_path']}: base file {base['source_path']} missing")
                elif sha256_file(source) != base["sha256_current"]:
                    problems.append(f"{entry['staged_path']}: base observation is stale "
                                    f"({base['source_path']} changed since the map was written)")
        for item in payload.get("planned_original_edits", []):
            target = WS / item["target_path"]
            if item["base_exists"] and (not target.is_file()
                                        or sha256_file(target) != item["base_sha256"]):
                problems.append(f"planned edit {item['target_path']}: base observation stale")
        # the map must cover every file in the merge-candidate roots
        covered = {e["staged_path"] for e in entries}
        for group, root in STAGED_ROOTS.items():
            for f in walk(root):
                rel = rel_ws(f)
                if rel in covered:
                    continue
                if any(item["staged_path"] == rel for item in payload.get("not_merged", [])):
                    continue
                problems.append(f"{rel}: staged file is neither mapped nor listed as not_merged")

        md = render_map_md(payload)
        if not MAP_MD.is_file():
            problems.append(f"missing {rel_ws(MAP_MD)}")
        elif strip_stamp(MAP_MD.read_text(encoding="utf-8")) != strip_stamp(md):
            problems.append(f"{rel_ws(MAP_MD)} is stale (regenerate)")

    if not RELEASE_JSON.is_file():
        problems.append(f"missing {rel_ws(RELEASE_JSON)}")
    else:
        release = load_json(RELEASE_JSON)
        if release.get("manifest_version") != RELEASE_VERSION:
            problems.append(f"release manifest_version unexpected: {release.get('manifest_version')!r}")
        if release.get("status") != "proposed_staged_not_merged_not_deployed":
            problems.append("release manifest is not labelled as a staged proposal")
        for name, record in (release.get("dependency_versions", {}).get("observed") or {}).items():
            if record == "not observed in the shared venv":
                problems.append(f"dependency {name} not observed in the shared venv")

    if not V2_REF.is_file():
        problems.append(f"missing {rel_ws(V2_REF)}")
    else:
        if strip_stamp(V2_REF.read_text(encoding="utf-8")) != strip_stamp(build_v2_reference()):
            problems.append(f"{rel_ws(V2_REF)} is stale (regenerate)")

    if problems:
        print("A14_BUILD_ARTIFACTS: FAIL")
        for p in problems:
            print(f"- {p}")
        return 1

    counts = payload["counts"]
    print("A14_BUILD_ARTIFACTS: PASS")
    print(f"- merge map: {counts['entries']} entries, {counts['not_merged']} not merged, "
          f"{counts['planned_original_edits']} planned original edits, "
          f"base drift {counts['base_drift']}")
    print(f"- release manifest: {rel_ws(RELEASE_JSON)}")
    print(f"- v2 reference: {rel_ws(V2_REF)}")
    return 0


def main() -> int:
    if "--check" in sys.argv[1:]:
        return check()

    v2_text = build_v2_reference()
    write_text(V2_REF, v2_text)

    payload = build_map()
    write_json(MAP_JSON, payload)
    write_text(MAP_MD, render_map_md(payload))

    release = build_release_manifest(payload)
    write_json(RELEASE_JSON, release)

    counts = payload["counts"]
    print("wrote " + rel_ws(V2_REF))
    print("wrote " + rel_ws(MAP_JSON))
    print("wrote " + rel_ws(MAP_MD))
    print("wrote " + rel_ws(RELEASE_JSON))
    print(f"merge map: {counts['entries']} entries across {len(counts['groups'])} groups; "
          f"not merged {counts['not_merged']}; planned original edits "
          f"{counts['planned_original_edits']}; base drift {counts['base_drift']}")
    if payload["problems"]:
        print("PROBLEMS:")
        for p in payload["problems"]:
            print(f"- {p}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
