"""Build the B03 private rehearsal candidate (plan 12 / B03).

B03 is "integrate contracts, registry, and local read catalog": add stable
mappings and provider services without rewriting raw data, and rehearse a real
catalog build from approved consistent snapshots. The actual merge waits for
the human release of the original paths; what can be done privately is a
*rehearsal* on a private target-layout candidate.

Unlike B02 (which packaged new configuration files on top of the R04
candidate), B03 validates the code, contracts and catalog machinery that are
already carried at the target layout. So this candidate is a byte-identical
copy of the B02 candidate: zero new files, and the proof that matters is that
the copy is exactly the parent file set. That also means the parent's own
candidate manifest (`B02_CANDIDATE_MANIFEST.json`), which B02 excluded from its
own tree digest, becomes an ordinary carried file here -- the reason this
candidate's digest covers 186 files where the parent's covered 185.

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
RUN_ID = "b03-rehearsal-2026-10-07"
STAGING = ROOT / "integration-staging"
RUN_DIR = STAGING / "runtime" / RUN_ID
CANDIDATES = RUN_DIR / "candidates"

PARENT_RUN = "b02-rehearsal-20261006"
PARENT_DESTINATION = "b02-shared-config-v1"
PARENT = STAGING / "runtime" / PARENT_RUN / "candidates" / PARENT_DESTINATION
PARENT_MANIFEST_NAME = "B02_CANDIDATE_MANIFEST.json"

DESTINATION = "b03-contracts-catalog-v1"
MANIFEST_NAME = "B03_CANDIDATE_MANIFEST.json"

DIGEST_RULE = (
    "sha256 over 'path\\0sha256\\n' for every file under the root, sorted by path, "
    "excluding __pycache__/.pytest_cache and excluding the named manifest itself"
)

SKIP_DIRS = {"__pycache__", ".pytest_cache"}

# Modules and contract files this packet's rehearsal will exercise; recorded so a
# later reader can see what the candidate was expected to carry.
EXPECTED_FILES = [
    "src/examdata/integration/contracts/quality.py",
    "src/examdata/integration/contracts/ids.py",
    "src/examdata/integration/contracts/enums.py",
    "src/examdata/integration/contracts/models.py",
    "src/examdata/integration/catalog/builder.py",
    "src/examdata/integration/catalog/model.py",
    "src/examdata/integration/catalog/store.py",
    "src/examdata/integration/catalog/revision.py",
    "src/examdata/integration/providers/registry.py",
    "src/examdata/integration/providers/fixtures.py",
    "src/examdata/integration/providers/results.py",
    "src/examdata/integration/providers/protocol.py",
    "src/examdata/integration/api/dataset.py",
    "src/examdata/integration/api/view.py",
    "src/examdata/integration/legacy/bridge.py",
    "src/examdata/integration/runtime/paths.py",
    "src/examdata/integration/runtime/manifest.py",
    "contracts/quality-transitions.json",
    "contracts/identity-keys.json",
    "contracts/schema/quality.schema.json",
    "components/manifest.json",
    "config/staging-config.example.json",
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
        raise SystemExit(f"parent B02 candidate is missing: {PARENT}")
    parent_manifest = PARENT / PARENT_MANIFEST_NAME
    if not parent_manifest.is_file():
        raise SystemExit(f"parent manifest is missing: {parent_manifest}")

    parent_manifest_doc = json.loads(parent_manifest.read_text(encoding="utf-8"))
    parent_recorded_tree = parent_manifest_doc.get("candidate_tree", {})

    base = CANDIDATES / DESTINATION
    if base.exists():
        shutil.rmtree(base)
    base.mkdir(parents=True)

    parent_digest_before = tree_digest(PARENT, exclude=(PARENT_MANIFEST_NAME,))
    parent_full_before = tree_digest(PARENT)
    parent_manifest_sha_before = sha256(parent_manifest)
    copied = copy_tree(PARENT, base)

    parent_digest = tree_digest(PARENT, exclude=(PARENT_MANIFEST_NAME,))
    parent_full_after = tree_digest(PARENT)
    candidate_digest = tree_digest(base, exclude=(MANIFEST_NAME,))

    missing = [rel for rel in EXPECTED_FILES if not (base / rel).is_file()]
    checks = {
        "parent_manifest_carried": (base / PARENT_MANIFEST_NAME).is_file(),
        "target_package_present": (base / "src" / "examdata" / "integration").is_dir(),
        "expected_files_present": not missing,
        "parent_tree_unchanged": parent_digest_before == parent_digest,
        "parent_manifest_unchanged": parent_manifest_sha_before == sha256(parent_manifest),
        "parent_manifest_internal_digest_matches": (
            parent_recorded_tree.get("files") == parent_digest_before["files"]
            and parent_recorded_tree.get("sha256") == parent_digest_before["sha256"]
            and parent_recorded_tree.get("excludes") == list(parent_digest_before["excludes"])
        ),
        "candidate_matches_parent_fileset": (
            candidate_digest["files"] == parent_full_after["files"]
            and candidate_digest["sha256"] == parent_full_after["sha256"]
        ),
        "candidate_digest_excludes_manifest": candidate_digest["excludes"] == [MANIFEST_NAME],
    }

    manifest = {
        "schema": "examdata.integration.b03_candidate/1",
        "run_id": RUN_ID,
        "packet": "B03",
        "destination": DESTINATION,
        "candidate_root": str(base),
        "scope": ("contracts, provider registry and local read catalog at the "
                  "target layout; byte-identical carry of the B02 candidate, no "
                  "new files"),
        "lineage": {
            "parent_run": PARENT_RUN,
            "parent_destination": PARENT_DESTINATION,
            "parent_root": str(PARENT),
            "parent_manifest": PARENT_MANIFEST_NAME,
            "parent_manifest_sha256": sha256(parent_manifest),
            "parent_manifest_sha256_before_copy": parent_manifest_sha_before,
            "parent_tree": parent_digest,
            "parent_tree_including_manifest": parent_full_after,
            "relation": "byte-identical child of the B02 shared-config candidate",
        },
        "candidate_tree": candidate_digest,
        "digest_rule": DIGEST_RULE,
        "counts": {
            "files_copied_from_parent": len(copied),
            "new_files_added_by_b03": 0,
            "digest_files": candidate_digest["files"],
            "candidate_files_on_disk_after_manifest": candidate_digest["files"] + 1,
        },
        "count_explanation": (
            "B02's digest covered 185 files because its own manifest was excluded; "
            "that manifest is an ordinary carried file in B03, so the B03 digest "
            "covers 186 files = 185 parent-digest files + the carried B02 manifest. "
            "The on-disk count is 187 = 186 digest files + this B03 manifest."
        ),
        "expected_files_missing": missing,
        "checks": checks,
        "note": ("private candidate only; not merged, not deployed; the original tree "
                 "was neither read, imported nor written; frozen B02/R04 evidence was "
                 "not overwritten"),
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
        "parent_tree_recorded": parent_digest,
        "parent_tree_including_manifest": parent_full_after,
    }


def main() -> int:
    CANDIDATES.mkdir(parents=True, exist_ok=True)
    result = build()
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0 if result["all_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
