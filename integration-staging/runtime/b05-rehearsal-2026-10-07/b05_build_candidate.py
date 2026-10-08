"""Build the B05 private rehearsal candidate (plan 12 / B05).

B05 is "materials, syllabuses and timetables through the active-owner seam": the
five feature families are read through one seam, ``adapters.active_owner``, and
served from clearly labelled synthetic fixtures without ever claiming a live
owner integration. The actual merge waits for the human release of the original
paths; what can be done privately is a *rehearsal* on a private target-layout
candidate.

Unlike B04 (one added module), B05 adds one new module at the target layout -
``src/examdata/integration/adapters/active_owner.py`` - and rewrites exactly two
modules to read their five feature families through the seam
(``api/dataset.py``, ``api/app.py``). The manifest proves the rest is carried
verbatim: every other parent file recomputed under the candidate root hashes
identically, the parent tree is unchanged, and the child's digest is exactly
the parent's on-disk file set plus the one new module.

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
RUN_ID = "b05-rehearsal-2026-10-07"
STAGING = ROOT / "integration-staging"
RUN_DIR = STAGING / "runtime" / RUN_ID
CANDIDATES = RUN_DIR / "candidates"

PARENT_RUN = "b04-rehearsal-2026-10-07"
PARENT_DESTINATION = "b04-routes-v1"
PARENT = STAGING / "runtime" / PARENT_RUN / "candidates" / PARENT_DESTINATION
PARENT_MANIFEST_NAME = "B04_CANDIDATE_MANIFEST.json"

DESTINATION = "b05-adapters-v1"
MANIFEST_NAME = "B05_CANDIDATE_MANIFEST.json"

#: The one module this packet authors, and its run-local source of truth.
NEW_MODULE_REL = "src/examdata/integration/adapters/active_owner.py"
NEW_MODULE_SOURCE = RUN_DIR / "tools" / "active_owner.py"

#: The modules this packet rewrites, and their run-local edited sources.
EDITED = {
    "src/examdata/integration/api/dataset.py": RUN_DIR / "tools" / "dataset.py",
    "src/examdata/integration/api/app.py": RUN_DIR / "tools" / "app.py",
}
EDITED_RELS = tuple(sorted(EDITED))

DIGEST_RULE = (
    "sha256 over 'path\\0sha256\\n' for every file under the root, sorted by path, "
    "excluding __pycache__/.pytest_cache and excluding the named manifest itself"
)

SKIP_DIRS = {"__pycache__", ".pytest_cache"}

# Files this packet's rehearsal will exercise; recorded so a later reader can
# see what the candidate was expected to carry.
EXPECTED_FILES = [
    NEW_MODULE_REL,
    "src/examdata/integration/adapters/__init__.py",
    "src/examdata/integration/api/compose.py",
    "src/examdata/integration/api/app.py",
    "src/examdata/integration/api/dataset.py",
    "src/examdata/integration/__init__.py",
    "src/examdata/__init__.py",
    PARENT_MANIFEST_NAME,
]


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


def build() -> dict:
    if not PARENT.is_dir():
        raise SystemExit(f"parent B04 candidate is missing: {PARENT}")
    parent_manifest = PARENT / PARENT_MANIFEST_NAME
    if not parent_manifest.is_file():
        raise SystemExit(f"parent manifest is missing: {parent_manifest}")
    if not NEW_MODULE_SOURCE.is_file():
        raise SystemExit(f"new module source is missing: {NEW_MODULE_SOURCE}")
    for rel, source in EDITED.items():
        if not source.is_file():
            raise SystemExit(f"edited source is missing for {rel}: {source}")

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

    module_source_bytes = NEW_MODULE_SOURCE.read_bytes()
    module_source_text = module_source_bytes.decode("utf-8")
    module_out = base / NEW_MODULE_REL
    module_out.parent.mkdir(parents=True, exist_ok=True)
    module_out.write_bytes(module_source_bytes)

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

    parent_digest = tree_digest(PARENT, exclude=(PARENT_MANIFEST_NAME,))
    parent_full_after = tree_digest(PARENT)
    candidate_digest = tree_digest(base, exclude=(MANIFEST_NAME,))
    carried_digest = tree_digest(
        base, exclude=(MANIFEST_NAME, NEW_MODULE_REL) + EDITED_RELS)
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
        "new_files_exactly_one": new_files == [NEW_MODULE_REL],
        "only_the_two_edited_files_changed": changed == list(EDITED_RELS),
        "new_module_matches_source": sha256(module_out) == sha256(NEW_MODULE_SOURCE),
        "new_module_compiles": _compiles(module_source_text, NEW_MODULE_REL),
        "edited_files_match_sources": all(
            r["written_sha256"] == r["source_sha256"] for r in edited_records),
        "edited_files_actually_changed": all(
            r["parent_sha256"] != r["source_sha256"] for r in edited_records),
        "edited_files_compile": all(edited_compiles.values()),
        "candidate_digest_is_parent_plus_new_module": (
            candidate_digest["files"] == parent_full_after["files"] + 1),
        "candidate_digest_excludes_manifest": candidate_digest["excludes"] == [MANIFEST_NAME],
    }

    manifest = {
        "schema": "examdata.integration.b05_candidate/1",
        "run_id": RUN_ID,
        "packet": "B05",
        "destination": DESTINATION,
        "candidate_root": str(base),
        "scope": ("serve the materials, syllabus and timetable families through the "
                  "active-owner seam; the B04 candidate plus one new seam module and "
                  "two seam-wired call sites, all at the target layout"),
        "lineage": {
            "parent_run": PARENT_RUN,
            "parent_destination": PARENT_DESTINATION,
            "parent_root": str(PARENT),
            "parent_manifest": PARENT_MANIFEST_NAME,
            "parent_manifest_sha256": sha256(parent_manifest),
            "parent_manifest_sha256_before_copy": parent_manifest_sha_before,
            "parent_tree": parent_digest,
            "parent_tree_including_manifest": parent_full_after,
            "relation": ("child of the B04 routes candidate with one added module "
                         "(the active-owner seam) and two rewritten modules "
                         "(dataset.py, app.py)"),
        },
        "new_module": {
            "staged_path": NEW_MODULE_REL,
            "source": str(NEW_MODULE_SOURCE),
            "source_sha256": sha256(NEW_MODULE_SOURCE),
            "written_sha256": sha256(module_out),
        },
        "edited_files": edited_records,
        "candidate_tree": candidate_digest,
        "carried_verbatim_tree": carried_digest,
        "parent_verbatim_tree": parent_verbatim_digest,
        "digest_rule": DIGEST_RULE,
        "counts": {
            "files_copied_from_parent": len(copied),
            "new_files_added_by_b05": len(new_files),
            "edited_files_rewritten_by_b05": len(EDITED),
            "carried_verbatim_files": carried_digest["files"],
            "digest_files": candidate_digest["files"],
            "candidate_files_on_disk_after_manifest": candidate_digest["files"] + 1,
        },
        "count_explanation": (
            f"B04's digest excluded its own manifest and covered 188 files; the "
            f"B04 candidate carried 189 files on disk (188 + manifest). B05 copies "
            f"all {len(copied)} of them, rewrites {len(EDITED)} modules "
            f"(dataset.py, app.py) and adds {len(new_files)} new module "
            f"(active_owner.py), so the B05 digest covers {candidate_digest['files']} "
            f"files = {carried_digest['files']} carried verbatim + {len(EDITED)} "
            f"rewritten + {len(new_files)} new. The on-disk count is "
            f"{candidate_digest['files'] + 1} = {candidate_digest['files']} digest "
            f"files + this B05 manifest."
        ),
        "expected_files_missing": missing,
        "checks": checks,
        "note": ("private candidate only; not merged, not deployed; the original tree "
                 "was neither read, imported nor written; frozen B02/B03/B04/R04 "
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
        "new_module_sha256": sha256(module_out),
    }


def main() -> int:
    CANDIDATES.mkdir(parents=True, exist_ok=True)
    result = build()
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0 if result["all_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
