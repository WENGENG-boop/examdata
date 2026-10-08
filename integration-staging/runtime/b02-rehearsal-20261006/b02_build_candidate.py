"""Build the B02 private rehearsal candidate (plan 12 / B02).

B02 is "integrate shared configuration and component packaging": merge the
runtime configuration and runner modules, preserve old aliases and startup
behaviour, and keep the database schema and data roots unchanged.

The actual merge waits for the human release of the original paths. What can be
done privately is a *rehearsal*: take the R04 target-layout candidate as the
parent, package the shared configuration next to it, and prove the parts of the
B02 acceptance that do not need the original tree.

Lineage is explicit: the parent candidate's manifest hash and tree digest are
recorded, and this candidate gets its own fresh tree digest. Nothing outside the
two Phase A write roots is read, copied or written. The original `examdata` tree
is never touched. This candidate is private only: not merged, not deployed.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import shutil

ROOT = pathlib.Path(__file__).resolve().parents[3]        # C:/Users/weo/Desktop/api
RUN_ID = "b02-rehearsal-20261006"
STAGING = ROOT / "integration-staging"
RUN_DIR = STAGING / "runtime" / RUN_ID
CANDIDATES = RUN_DIR / "candidates"

PARENT_RUN = "r0104-repair-20261006"
PARENT_DESTINATION = "r04-target-layout-v2"
PARENT = STAGING / "runtime" / PARENT_RUN / "candidates" / PARENT_DESTINATION

DESTINATION = "b02-shared-config-v1"
MANIFEST_NAME = "B02_CANDIDATE_MANIFEST.json"

DIGEST_RULE = (
    "sha256 over 'path\\0sha256\\n' for every file under the root, sorted by path, "
    "excluding __pycache__/.pytest_cache and excluding the named manifest itself"
)

SRC_CONFIG = STAGING / "config"
SKIP_DIRS = {"__pycache__", ".pytest_cache"}


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_digest(base: pathlib.Path, exclude: tuple[str, ...] = ()) -> dict:
    """Deterministic digest over the files under ``base`` (path + content).

    ``exclude`` names top-level entries to skip. The candidate's own manifest is
    excluded because a file cannot contain a hash of itself; the digest has to be
    reproducible from the tree as it stands on disk, so the rule is stated here
    and recorded next to every digest it produces.
    """
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


def build() -> dict:
    if not PARENT.is_dir():
        raise SystemExit(f"parent R04 candidate is missing: {PARENT}")
    parent_manifest = PARENT / "R04_CANDIDATE_MANIFEST.json"
    if not parent_manifest.is_file():
        raise SystemExit(f"parent manifest is missing: {parent_manifest}")

    base = CANDIDATES / DESTINATION
    if base.exists():
        shutil.rmtree(base)
    base.mkdir(parents=True)

    parent_digest_before = tree_digest(PARENT)
    parent_manifest_sha_before = sha256(parent_manifest)
    copied = copy_tree(PARENT, base)
    config_copied = copy_tree(SRC_CONFIG, base / "config")

    parent_digest = tree_digest(PARENT)
    candidate_digest = tree_digest(base, exclude=(MANIFEST_NAME,))

    pkg = base / "src" / "examdata" / "integration"
    checks = {
        "parent_manifest_carried": (base / "R04_CANDIDATE_MANIFEST.json").is_file(),
        "target_package_present": pkg.is_dir(),
        "paths_module_present": (pkg / "runtime" / "paths.py").is_file(),
        "settings_module_present": (pkg / "runtime" / "settings.py").is_file(),
        "runner_module_present": (pkg / "runtime" / "runner.py").is_file(),
        "manifest_module_present": (pkg / "runtime" / "manifest.py").is_file(),
        "shared_config_packaged": (base / "config" / "staging-config.example.json").is_file(),
        "component_manifest_packaged": (base / "components" / "manifest.json").is_file(),
        "schema_packaged": (base / "contracts" / "schema").is_dir(),
        "parent_tree_unchanged": parent_digest_before == parent_digest,
        "parent_manifest_unchanged": parent_manifest_sha_before == sha256(parent_manifest),
        "candidate_differs_from_parent": candidate_digest["files"] > parent_digest["files"],
        "candidate_digest_excludes_manifest": candidate_digest["excludes"] == [MANIFEST_NAME],
    }

    manifest = {
        "schema": "examdata.integration.b02_candidate/1",
        "run_id": RUN_ID,
        "packet": "B02",
        "destination": DESTINATION,
        "candidate_root": str(base),
        "scope": ("shared configuration and component packaging: runtime "
                  "configuration + runner modules at the target layout"),
        "lineage": {
            "parent_run": PARENT_RUN,
            "parent_destination": PARENT_DESTINATION,
            "parent_root": str(PARENT),
            "parent_manifest_sha256": sha256(parent_manifest),
            "parent_manifest_sha256_before_copy": parent_manifest_sha_before,
            "parent_tree": parent_digest,
            "relation": "child of the R04 target-layout candidate",
        },
        "candidate_tree": candidate_digest,
        "digest_rule": DIGEST_RULE,
        "counts": {
            "files_copied_from_parent": len(copied),
            "config_files_packaged": len(config_copied),
            "candidate_files_on_disk_after_manifest": candidate_digest["files"] + 1,
        },
        "source_hashes": {
            "runtime/settings.py": sha256(pkg / "runtime" / "settings.py"),
            "runtime/runner.py": sha256(pkg / "runtime" / "runner.py"),
            "runtime/manifest.py": sha256(pkg / "runtime" / "manifest.py"),
            "runtime/paths.py": sha256(pkg / "runtime" / "paths.py"),
        },
        "checks": checks,
        "note": ("private candidate only; not merged, not deployed; the original tree "
                 "was neither read, imported nor written; frozen R04 evidence was not "
                 "overwritten"),
    }
    (base / MANIFEST_NAME).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # The recorded digest must be reproducible from the tree as it now stands on
    # disk; recomputing it here catches the "hashed before the manifest was
    # written" mistake, and b02_validate.py re-checks it independently.
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
    }


def main() -> int:
    CANDIDATES.mkdir(parents=True, exist_ok=True)
    result = build()
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0 if result["all_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
