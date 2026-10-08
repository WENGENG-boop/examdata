"""Build the B06 private rehearsal candidate (plan 12 / B06).

B06 is "migrate frontend source discovery": the frontend no longer owns the
source-fetching business logic. The staged page keeps calling its own origin;
the candidate frontend server proxies ``/api/v2/*`` to the Python read API,
keeps the legacy ``/resources`` document shape as a compatibility bridge by
projecting the v2 items back onto legacy rows, and keeps the legacy
``/gateway/`` allowlist for the still-legacy paths.

Unlike B05 (one added module), B06 rewrites exactly three modules at the target
layout - ``api/dataset.py`` (the discovery projection), ``api/view.py`` (the
frontend-shaped query semantics) and ``api/app.py`` (the resources route and
payload wiring) - and adds the ``frontend/`` tree: the fifteen staged frontend
files carried byte-for-byte plus two new files (``server.mjs``, its
``tests/server.test.mjs``). The manifest proves the rest is carried verbatim:
every other parent file recomputed under the candidate root hashes
identically, the parent tree is unchanged, and the child's digest is exactly
the parent's on-disk file set plus the seventeen new frontend files.

Lineage is explicit: the parent candidate's manifest hash and tree digest are
recorded, and this candidate gets its own fresh tree digest. Nothing outside
the two Phase A write roots is read, copied or written. The original `examdata`
tree is never touched. This candidate is private only: not merged, not
deployed.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import shutil
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[3]        # C:/Users/weo/Desktop/api
RUN_ID = "b06-rehearsal-2026-10-07"
STAGING = ROOT / "integration-staging"
RUN_DIR = STAGING / "runtime" / RUN_ID
CANDIDATES = RUN_DIR / "candidates"

PARENT_RUN = "b05-rehearsal-2026-10-07"
PARENT_DESTINATION = "b05-adapters-v1"
PARENT = STAGING / "runtime" / PARENT_RUN / "candidates" / PARENT_DESTINATION
PARENT_MANIFEST_NAME = "B05_CANDIDATE_MANIFEST.json"

DESTINATION = "b06-frontend-v1"
MANIFEST_NAME = "B06_CANDIDATE_MANIFEST.json"

STAGED_FRONTEND = STAGING / "frontend"

#: The modules this packet rewrites, and their run-local edited sources.
EDITED = {
    "src/examdata/integration/api/dataset.py": RUN_DIR / "tools" / "dataset.py",
    "src/examdata/integration/api/view.py": RUN_DIR / "tools" / "view.py",
    "src/examdata/integration/api/app.py": RUN_DIR / "tools" / "app.py",
}
EDITED_RELS = tuple(sorted(EDITED))

#: The staged frontend files carried byte-for-byte into ``frontend/``.
FRONTEND_STAGED = (
    "PROVENANCE.json",
    "README.md",
    "app.js",
    "client.mjs",
    "fixture-server.mjs",
    "fixtures/PROVENANCE.json",
    "fixtures/catalog.json",
    "fixtures/resources.json",
    "fixtures/syllabi.json",
    "index.html",
    "search.mjs",
    "styles.css",
    "tests/client.test.mjs",
    "tests/flow.test.mjs",
    "tests/search.test.mjs",
)

#: The two new frontend files this packet authors, and their run-local sources.
FRONTEND_NEW = {
    "frontend/server.mjs": RUN_DIR / "tools" / "server.mjs",
    "frontend/tests/server.test.mjs": RUN_DIR / "tools" / "tests" / "server.test.mjs",
}

NEW_FILES_RELS = sorted([f"frontend/{rel}" for rel in FRONTEND_STAGED] + list(FRONTEND_NEW))

DIGEST_RULE = (
    "sha256 over 'path\\0sha256\\n' for every file under the root, sorted by path, "
    "excluding __pycache__/.pytest_cache and excluding the named manifest itself"
)

SKIP_DIRS = {"__pycache__", ".pytest_cache"}

# Files this packet's rehearsal will exercise; recorded so a later reader can
# see what the candidate was expected to carry.
EXPECTED_FILES = sorted([
    *EDITED_RELS,
    *NEW_FILES_RELS,
    PARENT_MANIFEST_NAME,
    "src/examdata/integration/api/compose.py",
    "src/examdata/integration/__init__.py",
    "src/examdata/__init__.py",
])


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_digest(base: pathlib.Path, exclude: tuple[str, ...] = ()) -> dict:
    """Deterministic digest over the files under ``base`` (path + content)."""
    entries: list[tuple[str, str]] = []
    for p in sorted(base.rglob("*")):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.is_file():
            rel = p.relative_to(base).as_posix()
            if rel in exclude:
                continue
            entries.append((rel, sha256(p)))
    digest = hashlib.sha256()
    for rel, h in entries:
        digest.update(f"{rel}\0{h}\n".encode("utf-8"))
    return {
        "files": len(entries),
        "excludes": list(exclude),
        "sha256": digest.hexdigest(),
    }


def file_set(base: pathlib.Path) -> set[str]:
    out: set[str] = set()
    for p in sorted(base.rglob("*")):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.is_file():
            out.add(p.relative_to(base).as_posix())
    return out


def copy_tree(src: pathlib.Path, dst: pathlib.Path) -> list[str]:
    copied: list[str] = []
    for p in sorted(src.rglob("*")):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        rel = p.relative_to(src)
        out = dst / rel
        if p.is_dir():
            out.mkdir(parents=True, exist_ok=True)
        else:
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, out)
            copied.append(rel.as_posix())
    return copied


def _compiles(text: str, name: str) -> bool:
    try:
        compile(text, name, "exec")
        return True
    except SyntaxError:
        return False


def _node_check(path: pathlib.Path) -> dict:
    try:
        result = subprocess.run(["node", "--check", str(path)],
                                capture_output=True, text=True, timeout=60)
        return {"path": str(path), "ok": result.returncode == 0,
                "stderr": result.stderr.strip()}
    except Exception as exc:                     # noqa: BLE001 - recorded, never raised
        return {"path": str(path), "ok": False, "stderr": str(exc)}


def _frontend_provenance(base: pathlib.Path) -> list[dict]:
    """Check the 13 recorded frontend hashes against the staged source and the copy."""
    records: list[dict] = []
    root_doc = json.loads((base / "frontend" / "PROVENANCE.json").read_text(encoding="utf-8"))
    for entry in root_doc["files"]:
        rel = entry["path"]
        staged = STAGED_FRONTEND / rel
        copy = base / "frontend" / rel
        records.append({
            "path": f"frontend/{rel}",
            "recorded_sha256": entry["staged_sha256"],
            "staged_sha256": sha256(staged),
            "candidate_sha256": sha256(copy),
        })
    fix_doc = json.loads(
        (base / "frontend" / "fixtures" / "PROVENANCE.json").read_text(encoding="utf-8"))
    for entry in fix_doc["files"]:
        rel = f"fixtures/{entry['path']}"
        staged = STAGED_FRONTEND / rel
        copy = base / "frontend" / rel
        records.append({
            "path": f"frontend/{rel}",
            "recorded_sha256": entry["sha256"],
            "staged_sha256": sha256(staged),
            "candidate_sha256": sha256(copy),
        })
    return records


def build() -> dict:
    if not PARENT.is_dir():
        raise SystemExit(f"parent B05 candidate is missing: {PARENT}")
    parent_manifest = PARENT / PARENT_MANIFEST_NAME
    if not parent_manifest.is_file():
        raise SystemExit(f"parent manifest is missing: {parent_manifest}")
    for rel, source in EDITED.items():
        if not source.is_file():
            raise SystemExit(f"edited source is missing for {rel}: {source}")
    for rel, source in FRONTEND_NEW.items():
        if not source.is_file():
            raise SystemExit(f"new frontend source is missing for {rel}: {source}")
    for rel in FRONTEND_STAGED:
        if not (STAGED_FRONTEND / rel).is_file():
            raise SystemExit(f"staged frontend file is missing: {rel}")

    parent_manifest_doc = json.loads(parent_manifest.read_text(encoding="utf-8"))
    parent_recorded_tree = parent_manifest_doc.get("candidate_tree", {})

    base = CANDIDATES / DESTINATION
    if base.exists():
        shutil.rmtree(base)
    base.mkdir(parents=True)

    parent_digest_before = tree_digest(PARENT, exclude=(PARENT_MANIFEST_NAME,))
    parent_full_before = tree_digest(PARENT)
    parent_manifest_sha_before = sha256(parent_manifest)
    parent_files = file_set(PARENT)
    copied = copy_tree(PARENT, base)

    # 1. rewrite the three edited modules from the run-local sources
    edited_records: list[dict] = []
    edited_compiles: dict[str, bool] = {}
    for rel in EDITED_RELS:
        source = EDITED[rel]
        out = base / rel
        source_bytes = source.read_bytes()
        out.write_bytes(source_bytes)
        edited_records.append({
            "path": rel,
            "source": str(source),
            "parent_sha256": sha256(PARENT / rel),
            "source_sha256": sha256(source),
            "written_sha256": sha256(out),
        })
        edited_compiles[rel] = _compiles(source_bytes.decode("utf-8"), rel)

    # 2. carry the fifteen staged frontend files byte-for-byte
    staged_records: list[dict] = []
    for rel in FRONTEND_STAGED:
        source = STAGED_FRONTEND / rel
        out = base / "frontend" / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        source_bytes = source.read_bytes()
        out.write_bytes(source_bytes)
        staged_records.append({
            "path": f"frontend/{rel}",
            "staged_sha256": sha256(source),
            "written_sha256": sha256(out),
        })

    # 3. write the two new frontend files
    new_records: list[dict] = []
    for rel, source in sorted(FRONTEND_NEW.items()):
        out = base / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        source_bytes = source.read_bytes()
        out.write_bytes(source_bytes)
        new_records.append({
            "path": rel,
            "source": str(source),
            "source_sha256": sha256(source),
            "written_sha256": sha256(out),
        })

    node_checks = {
        rel: _node_check(base / rel)
        for rel in ("frontend/server.mjs", "frontend/tests/server.test.mjs")
    }
    provenance_records = _frontend_provenance(base)

    parent_digest = tree_digest(PARENT, exclude=(PARENT_MANIFEST_NAME,))
    parent_full_after = tree_digest(PARENT)
    candidate_digest = tree_digest(base, exclude=(MANIFEST_NAME,))
    carried_digest = tree_digest(
        base, exclude=(MANIFEST_NAME,) + tuple(NEW_FILES_RELS) + EDITED_RELS)
    parent_verbatim_digest = tree_digest(PARENT, exclude=EDITED_RELS)

    candidate_files = file_set(base)
    new_files = sorted(candidate_files - parent_files)
    common_files = sorted(parent_files & candidate_files)
    changed = sorted(rel for rel in common_files
                     if sha256(PARENT / rel) != sha256(base / rel))
    missing = [rel for rel in EXPECTED_FILES if not (base / rel).is_file()]

    checks = {
        "parent_manifest_carried": (base / PARENT_MANIFEST_NAME).is_file(),
        "target_package_present": (base / "src" / "examdata" / "integration").is_dir(),
        "expected_files_present": not missing,
        "parent_tree_unchanged": parent_digest_before == parent_digest,
        "parent_full_tree_unchanged": parent_full_before == parent_full_after,
        "parent_manifest_unchanged": parent_manifest_sha_before == sha256(parent_manifest),
        "parent_manifest_internal_digest_matches": (
            parent_recorded_tree.get("files") == parent_digest_before["files"]
            and parent_recorded_tree.get("sha256") == parent_digest_before["sha256"]
            and parent_recorded_tree.get("excludes") == list(parent_digest_before["excludes"])
        ),
        "carried_verbatim_matches_parent": (
            parent_verbatim_digest["files"] == carried_digest["files"]
            and parent_verbatim_digest["sha256"] == carried_digest["sha256"]
        ),
        "new_files_exactly_seventeen_vs_parent": new_files == NEW_FILES_RELS,
        "only_the_three_edited_files_changed": changed == list(EDITED_RELS),
        "edited_files_match_sources": all(
            r["written_sha256"] == r["source_sha256"] for r in edited_records),
        "edited_files_actually_changed": all(
            r["parent_sha256"] != r["source_sha256"] for r in edited_records),
        "edited_files_compile": all(edited_compiles.values()),
        "staged_frontend_bytes_match_source": all(
            r["staged_sha256"] == r["written_sha256"] for r in staged_records),
        "staged_frontend_files_are_fifteen": len(staged_records) == 15,
        "new_frontend_files_match_sources": all(
            r["written_sha256"] == r["source_sha256"] for r in new_records),
        "new_frontend_files_are_two": len(new_records) == 2,
        "frontend_provenance_hashes_match": (
            len(provenance_records) == 13
            and all(r["recorded_sha256"] == r["staged_sha256"] == r["candidate_sha256"]
                    for r in provenance_records)
        ),
        "new_frontend_js_parse": all(r["ok"] for r in node_checks.values()),
        "candidate_digest_is_parent_plus_new_frontend": (
            candidate_digest["files"] == parent_full_after["files"] + len(NEW_FILES_RELS)),
        "candidate_digest_excludes_manifest": candidate_digest["excludes"] == [MANIFEST_NAME],
    }

    manifest = {
        "schema": "examdata.integration.b06_candidate/1",
        "run_id": RUN_ID,
        "packet": "B06",
        "destination": DESTINATION,
        "candidate_root": str(base),
        "scope": ("migrate frontend source discovery: the B05 candidate plus the "
                  "backend-side discovery projection, the frontend-shaped query "
                  "semantics and the resources wiring in three rewritten modules, "
                  "and the frontend/ tree (fifteen staged files byte-for-byte, one "
                  "rewritten server, one new server test)"),
        "lineage": {
            "parent_run": PARENT_RUN,
            "parent_destination": PARENT_DESTINATION,
            "parent_root": str(PARENT),
            "parent_manifest": PARENT_MANIFEST_NAME,
            "parent_manifest_sha256": sha256(parent_manifest),
            "parent_manifest_sha256_before_copy": parent_manifest_sha_before,
            "parent_tree": parent_digest,
            "parent_tree_including_manifest": parent_full_after,
            "relation": ("child of the B05 adapters candidate with three rewritten "
                         "modules (dataset.py, view.py, app.py) and seventeen added "
                         "frontend files"),
        },
        "edited_files": edited_records,
        "frontend": {
            "staged_root": str(STAGED_FRONTEND),
            "staged_files": staged_records,
            "new_files": new_records,
            "provenance_records": provenance_records,
            "node_check": node_checks,
        },
        "candidate_tree": candidate_digest,
        "carried_verbatim_tree": carried_digest,
        "parent_verbatim_tree": parent_verbatim_digest,
        "digest_rule": DIGEST_RULE,
        "counts": {
            "files_copied_from_parent": len(copied),
            "new_files_added_by_b06": len(new_files),
            "edited_files_rewritten_by_b06": len(EDITED),
            "carried_verbatim_files": carried_digest["files"],
            "digest_files": candidate_digest["files"],
            "candidate_files_on_disk_after_manifest": candidate_digest["files"] + 1,
        },
        "count_explanation": (
            f"B05's digest excluded its own manifest and covered "
            f"{parent_manifest_doc['counts']['digest_files']} files; the B05 candidate "
            f"carried {parent_manifest_doc['counts']['candidate_files_on_disk_after_manifest']} "
            f"on disk. B06 copies all {len(copied)} of them, rewrites {len(EDITED)} "
            f"modules (dataset.py, view.py, app.py) and adds {len(new_files)} frontend "
            f"files (15 staged byte-for-byte + server.mjs + tests/server.test.mjs), so "
            f"the B06 digest covers {candidate_digest['files']} files = "
            f"{carried_digest['files']} carried verbatim + {len(EDITED)} rewritten + "
            f"{len(new_files)} new. The on-disk count is "
            f"{candidate_digest['files'] + 1} = {candidate_digest['files']} digest files "
            f"+ this B06 manifest."
        ),
        "expected_files_missing": missing,
        "checks": checks,
        "note": ("private candidate only; not merged, not deployed; the original tree "
                 "was neither read, imported nor written; frozen B02/B03/B04/B05/R04 "
                 "evidence was not overwritten"),
    }
    (base / MANIFEST_NAME).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    digest_after = tree_digest(base, exclude=(MANIFEST_NAME,))
    repro = digest_after == candidate_digest

    return {
        "destination": DESTINATION,
        "candidate_root": str(base),
        "all_ok": all(checks.values()) and repro,
        "checks": checks,
        "digest_reproducible_after_manifest_write": repro,
        "candidate_manifest_sha256": sha256(base / MANIFEST_NAME),
        "counts": manifest["counts"],
        "candidate_tree": candidate_digest,
        "carried_verbatim_tree": carried_digest,
        "parent_tree_recorded": parent_digest,
        "parent_tree_including_manifest": parent_full_after,
        "new_files": new_files,
        "changed_files": changed,
        "edited_files": edited_records,
        "staged_frontend_sha_mismatches": [
            r for r in staged_records if r["staged_sha256"] != r["written_sha256"]],
        "node_checks": node_checks,
        "provenance_mismatches": [
            r for r in provenance_records
            if not (r["recorded_sha256"] == r["staged_sha256"] == r["candidate_sha256"])],
    }


def main() -> int:
    CANDIDATES.mkdir(parents=True, exist_ok=True)
    result = build()
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0 if result["all_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
