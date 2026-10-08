"""Build the B07 private rehearsal candidate (plan 12 / B07).

B07 is "integrate jobs, coverage, and diagnostics": the candidate gains a
read-only operations view over a configured synthetic operations root. Two new
modules are added under ``operations/`` - ``jobs.py`` (the read-only checkpoint
scan, per-batch job derivation, and public-text sanitization) and
``published.py`` (the explicit expected-manifest loader and the published
coverage view) - and exactly two modules are rewritten: ``api/dataset.py``
wires the operations view into the default dataset, and ``api/app.py`` serves
the coverage and jobs routes with sanitized public diagnostics.

The manifest proves the rest is carried verbatim: every other parent file
recomputed under the candidate root hashes identically, the parent tree is
unchanged, and the child's digest is exactly the parent's on-disk file set plus
the twelve new files (the two modules plus the ten-file synthetic
operations-root fixture subtree).

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

ROOT = pathlib.Path(__file__).resolve().parents[3]        # C:/Users/weo/Desktop/api
RUN_ID = "b07-rehearsal-2026-10-07"
STAGING = ROOT / "integration-staging"
RUN_DIR = STAGING / "runtime" / RUN_ID
CANDIDATES = RUN_DIR / "candidates"

PARENT_RUN = "b06-rehearsal-2026-10-07"
PARENT_DESTINATION = "b06-frontend-v1"
PARENT = STAGING / "runtime" / PARENT_RUN / "candidates" / PARENT_DESTINATION
PARENT_MANIFEST_NAME = "B06_CANDIDATE_MANIFEST.json"

DESTINATION = "b07-operations-v1"
MANIFEST_NAME = "B07_CANDIDATE_MANIFEST.json"

#: The modules this packet rewrites, and their run-local edited sources.
EDITED = {
    "src/examdata/integration/api/dataset.py": RUN_DIR / "tools" / "dataset.py",
    "src/examdata/integration/api/app.py": RUN_DIR / "tools" / "app.py",
}
EDITED_RELS = tuple(sorted(EDITED))

OPERATIONS_ROOT = RUN_DIR / "tools" / "operations-root"
FIXTURE_SUBDIR = "fixtures/synthetic/operations/operations-root"

#: The ten-file synthetic operations root carried into the candidate.
FIXTURE_FILES = (
    "PROVENANCE.json",
    "README.md",
    "cie-batch-8888-stale/checkpoint.json",
    "cie-batch-8888/checkpoint.json",
    "cie-location-batch/checkpoint.json",
    "expected-manifest.json",
    "run-ok-stale/checkpoint.json",
    "run-ok/checkpoint.json",
    "run-partial/checkpoint.json",
    "unsupported/checkpoint.json",
)

#: The two new operations modules this packet authors, and their run-local sources.
NEW_MODULES = {
    "src/examdata/integration/operations/jobs.py": RUN_DIR / "tools" / "jobs.py",
    "src/examdata/integration/operations/published.py": RUN_DIR / "tools" / "published.py",
}

NEW_FILES = {
    **NEW_MODULES,
    **{f"{FIXTURE_SUBDIR}/{rel}": OPERATIONS_ROOT / rel for rel in FIXTURE_FILES},
}
NEW_FILES_RELS = sorted(NEW_FILES)

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
    "src/examdata/integration/operations/__init__.py",
    "src/examdata/integration/operations/checkpoints.py",
    "src/examdata/integration/operations/coverage.py",
    "fixtures/synthetic/operations/PROVENANCE.json",
    "fixtures/synthetic/operations/README.md",
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


def _fixture_provenance(base: pathlib.Path) -> list[dict]:
    """Check the nine recorded fixture hashes against the source and the copy."""
    records: list[dict] = []
    root_doc = json.loads(
        (base / FIXTURE_SUBDIR / "PROVENANCE.json").read_text(encoding="utf-8"))
    for entry in root_doc["entries"]:
        rel = entry["path"]
        staged = OPERATIONS_ROOT / rel
        copy = base / FIXTURE_SUBDIR / rel
        records.append({
            "path": f"{FIXTURE_SUBDIR}/{rel}",
            "recorded_sha256": entry["sha256"],
            "staged_sha256": sha256(staged),
            "candidate_sha256": sha256(copy),
        })
    return records


def _fixture_json_parses(base: pathlib.Path) -> dict[str, dict]:
    checks: dict[str, dict] = {}
    for rel in FIXTURE_FILES:
        if not rel.endswith(".json"):
            continue
        path = base / FIXTURE_SUBDIR / rel
        try:
            json.loads(path.read_text(encoding="utf-8"))
            checks[rel] = {"ok": True, "error": None}
        except Exception as exc:                 # noqa: BLE001 - recorded, never raised
            checks[rel] = {"ok": False, "error": str(exc)}
    return checks


def build() -> dict:
    if not PARENT.is_dir():
        raise SystemExit(f"parent B06 candidate is missing: {PARENT}")
    parent_manifest = PARENT / PARENT_MANIFEST_NAME
    if not parent_manifest.is_file():
        raise SystemExit(f"parent manifest is missing: {parent_manifest}")
    for rel, source in EDITED.items():
        if not source.is_file():
            raise SystemExit(f"edited source is missing for {rel}: {source}")
    for rel, source in NEW_FILES.items():
        if not source.is_file():
            raise SystemExit(f"new file source is missing for {rel}: {source}")

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

    # 1. rewrite the two edited modules from the run-local sources
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

    # 2. write the twelve new files (two modules + ten fixture files)
    new_records: list[dict] = []
    new_module_compiles: dict[str, bool] = {}
    for rel, source in sorted(NEW_FILES.items()):
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
        if rel.endswith(".py"):
            new_module_compiles[rel] = _compiles(source_bytes.decode("utf-8"), rel)

    provenance_records = _fixture_provenance(base)
    json_parse_checks = _fixture_json_parses(base)

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
    fixture_records = [r for r in new_records
                       if r["path"].startswith(f"{FIXTURE_SUBDIR}/")]

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
        "new_files_exactly_twelve_vs_parent": new_files == NEW_FILES_RELS,
        "only_the_two_edited_files_changed": changed == list(EDITED_RELS),
        "edited_files_match_sources": all(
            r["written_sha256"] == r["source_sha256"] for r in edited_records),
        "edited_files_actually_changed": all(
            r["parent_sha256"] != r["source_sha256"] for r in edited_records),
        "edited_files_compile": all(edited_compiles.values()),
        "new_files_match_sources": all(
            r["written_sha256"] == r["source_sha256"] for r in new_records),
        "new_modules_compile": all(new_module_compiles.values()),
        "fixture_files_are_ten": (
            len(fixture_records) == 10 and all(
                (OPERATIONS_ROOT / rel).is_file() for rel in FIXTURE_FILES)),
        "fixture_bytes_match_source": all(
            r["written_sha256"] == r["source_sha256"] for r in fixture_records),
        "operations_provenance_hashes_match": (
            len(provenance_records) == 9
            and all(r["recorded_sha256"] == r["staged_sha256"] == r["candidate_sha256"]
                    for r in provenance_records)
        ),
        "fixture_json_parses": all(c["ok"] for c in json_parse_checks.values()),
        "candidate_digest_is_parent_plus_new_operations": (
            candidate_digest["files"] == parent_full_after["files"] + len(NEW_FILES_RELS)),
        "candidate_digest_excludes_manifest": candidate_digest["excludes"] == [MANIFEST_NAME],
    }

    manifest = {
        "schema": "examdata.integration.b07_candidate/1",
        "run_id": RUN_ID,
        "packet": "B07",
        "destination": DESTINATION,
        "candidate_root": str(base),
        "scope": ("integrate jobs, coverage and diagnostics: the B06 candidate plus "
                  "read-only operations adapters (jobs.py, published.py) over a "
                  "configured synthetic operations root, the rewritten dataset/app "
                  "wiring for the coverage and jobs routes with sanitized public "
                  "diagnostics, and the ten-file operations-root fixture subtree"),
        "lineage": {
            "parent_run": PARENT_RUN,
            "parent_destination": PARENT_DESTINATION,
            "parent_root": str(PARENT),
            "parent_manifest": PARENT_MANIFEST_NAME,
            "parent_manifest_sha256": sha256(parent_manifest),
            "parent_manifest_sha256_before_copy": parent_manifest_sha_before,
            "parent_tree": parent_digest,
            "parent_tree_including_manifest": parent_full_after,
            "relation": ("child of the B06 frontend candidate with two rewritten api "
                         "modules (dataset.py, app.py) and twelve added operations "
                         "files (jobs.py, published.py, and the ten-file synthetic "
                         "operations-root fixture subtree)"),
        },
        "edited_files": edited_records,
        "operations": {
            "fixture_root": str(OPERATIONS_ROOT),
            "fixture_files": fixture_records,
            "provenance_records": provenance_records,
            "json_parse": json_parse_checks,
            "new_modules": [r for r in new_records if r["path"].endswith(".py")],
        },
        "candidate_tree": candidate_digest,
        "carried_verbatim_tree": carried_digest,
        "parent_verbatim_tree": parent_verbatim_digest,
        "digest_rule": DIGEST_RULE,
        "counts": {
            "files_copied_from_parent": len(copied),
            "new_files_added_by_b07": len(new_files),
            "edited_files_rewritten_by_b07": len(EDITED),
            "carried_verbatim_files": carried_digest["files"],
            "digest_files": candidate_digest["files"],
            "candidate_files_on_disk_after_manifest": candidate_digest["files"] + 1,
        },
        "count_explanation": (
            f"B06's digest excluded its own manifest and covered "
            f"{parent_manifest_doc['counts']['digest_files']} files; the B06 candidate "
            f"carried {parent_manifest_doc['counts']['candidate_files_on_disk_after_manifest']} "
            f"on disk. B07 copies all {len(copied)} of them, rewrites {len(EDITED)} "
            f"modules (dataset.py, app.py) and adds {len(new_files)} operations files "
            f"(jobs.py, published.py, and the ten-file synthetic operations-root "
            f"fixture subtree), so the B07 digest covers {candidate_digest['files']} "
            f"files = {carried_digest['files']} carried verbatim + {len(EDITED)} "
            f"rewritten + {len(new_files)} new. The on-disk count is "
            f"{candidate_digest['files'] + 1} = {candidate_digest['files']} digest files "
            f"+ this B07 manifest."
        ),
        "expected_files_missing": missing,
        "checks": checks,
        "note": ("private candidate only; not merged, not deployed; the original tree "
                 "was neither read, imported nor written; frozen B02/B03/B04/B05/B06/R04 "
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
        "fixture_sha_mismatches": [
            r for r in fixture_records if r["written_sha256"] != r["source_sha256"]],
        "new_module_compiles": new_module_compiles,
        "json_parse_failures": [
            rel for rel, c in json_parse_checks.items() if not c["ok"]],
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
