"""Build the R04 private target-layout candidate trees (F03/R04).

Produces one private candidate tree per requested destination. Each tree is the
staged package placed at the *target layout* `examdata/src/examdata/integration/`
plus the resources the product code resolves relative to the deployment root
(contracts, components, synthetic fixtures).

Two destinations are built by default:

* ``candidates/r04-target-layout-v2``          - an arbitrary directory name;
* ``candidates/R04 目标 layout ünïcode``       - a name with spaces and non-ASCII
  characters.

Nothing outside the two Phase A write roots is touched; the original `examdata`
tree is never read, copied or imported. The private trees are candidates only:
not merged, not deployed.

Disclosed in-candidate adaptations (recorded in ``R04_CANDIDATE_MANIFEST.json``):

* ``testing/guards.py`` (test-only harness, not product code) is adapted so the
  harness keeps working after relocation: the staging root comes from the
  explicit ``EXAMDATA_INTEGRATION_ROOT`` environment variable first, the
  original-code denial target from ``EXAMDATA_INTEGRATION_ORIGINAL_APP_CODE``,
  and the module-name guard is retargeted from ``examdata`` to the staging name
  ``examdata_integration`` (the target-layout package is now ``examdata.integration``).
  The denial itself (``ensure_staged_path``) is unchanged.

The product package itself is copied verbatim (only the package name is
rewritten); product code no longer imports ``..testing.guards`` at all.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import shutil

ROOT = pathlib.Path(__file__).resolve().parents[3]        # C:/Users/weo/Desktop/api
RUN_ID = "r0104-repair-20261006"
STAGING = ROOT / "integration-staging"
SRC_PKG = STAGING / "src" / "examdata_integration"
SRC_CONTRACTS = STAGING / "contracts"
SRC_COMPONENTS = STAGING / "components"
SRC_FIXTURES = STAGING / "fixtures" / "synthetic"
CANDIDATES = STAGING / "runtime" / RUN_ID / "candidates"

DESTINATIONS = (
    "r04-target-layout-v2",
    "R04 \u76ee\u6807 layout \u00fcn\u00efcode",
)

OLD = "examdata_integration"
NEW = "examdata.integration"
SKIP_DIRS = {"__pycache__", ".pytest_cache"}

SHIM = '''"""Private candidate parent package (R04 target-layout validation).

This shim exists only so ``examdata.integration`` can be imported from the
private candidate tree. It is not the original package and carries no original
code.
"""

__all__ = ["integration"]
'''

GUARDS_PATCHES = (
    (
        '_ENV_STAGING_ROOT = "EXAMDATA_INTEGRATION_STAGING_ROOT"',
        '_ENV_STAGING_ROOT = "EXAMDATA_INTEGRATION_STAGING_ROOT"\n'
        '# R04 private candidate variant: the explicit product deployment root is the\n'
        '# primary source; the original-code denial target is supplied explicitly too.\n'
        '_ENV_ROOT = "EXAMDATA_INTEGRATION_ROOT"\n'
        '_ENV_ORIGINAL_APP_CODE = "EXAMDATA_INTEGRATION_ORIGINAL_APP_CODE"',
    ),
    (
        "def _resolve_staging_root() -> Path:\n"
        "    root = Path(os.path.realpath(Path(__file__).resolve().parents[3]))\n"
        '    if root.name != "integration-staging":',
        "def _resolve_staging_root() -> Path:\n"
        "    explicit = os.environ.get(_ENV_ROOT)\n"
        "    if explicit:\n"
        "        return Path(os.path.realpath(explicit))\n"
        "    root = Path(os.path.realpath(Path(__file__).resolve().parents[3]))\n"
        '    if root.name != "integration-staging":',
    ),
    (
        "STAGING_ROOT = _resolve_staging_root()\n"
        "WORKSPACE_ROOT = STAGING_ROOT.parent\n"
        'ORIGINAL_APP_CODE = WORKSPACE_ROOT / "examdata" / "src"',
        "STAGING_ROOT = _resolve_staging_root()\n"
        "WORKSPACE_ROOT = STAGING_ROOT.parent\n"
        "_original = os.environ.get(_ENV_ORIGINAL_APP_CODE)\n"
        "ORIGINAL_APP_CODE = (Path(os.path.realpath(_original)) if _original\n"
        '                     else WORKSPACE_ROOT / "examdata" / "src")',
    ),
    (
        '    blocked = ("examdata",)',
        "    # R04 private candidate variant: the target-layout package is\n"
        "    # `examdata.integration`, so the *staging* name is what this private\n"
        "    # harness refuses.\n"
        '    blocked = ("examdata_integration",)',
    ),
    (
        '        if top == "examdata":\n'
        '            offenders.append((name, getattr(mod, "__file__", None), "original module name"))',
        '        if top == "examdata_integration":\n'
        '            offenders.append((name, getattr(mod, "__file__", None), "staging module name"))',
    ),
)


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rewrite_text(path: pathlib.Path) -> int:
    text = path.read_text(encoding="utf-8")
    n = text.count(OLD)
    if n:
        path.write_text(text.replace(OLD, NEW), encoding="utf-8")
    return n


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


def patch_guards(path: pathlib.Path) -> dict:
    """Apply the disclosed private-tree adaptations to the copied guards module."""
    text = path.read_text(encoding="utf-8")
    applied = []
    for index, (old, new) in enumerate(GUARDS_PATCHES, start=1):
        count = text.count(old)
        if count != 1:
            raise SystemExit(
                f"guards patch {index} matched {count} times (expected 1): {old[:60]!r}")
        text = text.replace(old, new)
        applied.append(index)
    path.write_text(text, encoding="utf-8")
    return {"patches_applied": applied, "sha256_after": sha256(path)}


def build(destination: str) -> dict:
    base = CANDIDATES / destination
    if base.exists():
        shutil.rmtree(base)
    (base / "src").mkdir(parents=True)

    pkg_dst = base / "src" / "examdata" / "integration"
    py_copied = copy_tree(SRC_PKG, pkg_dst)
    contracts_copied = copy_tree(SRC_CONTRACTS, base / "contracts")
    components_copied = copy_tree(SRC_COMPONENTS, base / "components")
    fixtures_copied = copy_tree(SRC_FIXTURES, base / "fixtures" / "synthetic")

    shim = base / "src" / "examdata" / "__init__.py"
    shim.write_text(SHIM, encoding="utf-8")

    guards_src_sha = sha256(SRC_PKG / "testing" / "guards.py")
    rewritten: dict[str, int] = {}
    for p in sorted(pkg_dst.rglob("*")):
        if p.suffix in (".py", ".json"):
            n = rewrite_text(p)
            if n:
                rewritten[p.relative_to(base).as_posix()] = n

    guards_info = patch_guards(pkg_dst / "testing" / "guards.py")

    guards_path = pkg_dst / "testing" / "guards.py"
    leftover = sorted(
        p.relative_to(base).as_posix()
        for p in list(pkg_dst.rglob("*.py")) + list(pkg_dst.rglob("*.json"))
        if p != guards_path and OLD in p.read_text(encoding="utf-8"))
    guards_refs = sorted(
        line.strip() for line in guards_path.read_text(encoding="utf-8").splitlines()
        if OLD in line)

    checks = {
        "target_package_dir": pkg_dst.is_dir(),
        "private_shim": shim.is_file(),
        "no_old_name_left": not leftover,
        "guards_old_name_refs_disclosed": len(guards_refs) == 2,
        "contracts_schema_present": (base / "contracts" / "schema").is_dir(),
        "components_manifest_present": (base / "components" / "manifest.json").is_file(),
        "fixtures_synthetic_present": (base / "fixtures" / "synthetic").is_dir(),
        "paths_module_present": (pkg_dst / "runtime" / "paths.py").is_file(),
    }

    manifest = {
        "schema": "examdata.integration.r04_candidate/1",
        "run_id": RUN_ID,
        "finding": "R04",
        "destination": destination,
        "candidate_root": str(base),
        "target_package": NEW,
        "target_path_in_candidate": "src/examdata/integration",
        "source": {
            "package": "integration-staging/src/examdata_integration",
            "contracts": "integration-staging/contracts",
            "components": "integration-staging/components",
            "fixtures": "integration-staging/fixtures/synthetic",
        },
        "source_hashes": {
            "runtime/paths.py": sha256(SRC_PKG / "runtime" / "paths.py"),
            "testing/guards.py": guards_src_sha,
            "api/dataset.py": sha256(SRC_PKG / "api" / "dataset.py"),
            "adapters/source_reader.py": sha256(SRC_PKG / "adapters" / "source_reader.py"),
        },
        "candidate_hashes": {
            "testing/guards.py": guards_info["sha256_after"],
        },
        "counts": {
            "py_files_copied": len(py_copied),
            "contracts_files_copied": len(contracts_copied),
            "components_files_copied": len(components_copied),
            "fixtures_files_copied": len(fixtures_copied),
        },
        "rename": {"from": OLD, "to": NEW, "files_rewritten": rewritten},
        "in_candidate_adaptations": {
            "testing/guards.py": {
                "why": ("test-only harness module; after relocation the directory-name "
                        "heuristic no longer applies, so the private harness resolves its "
                        "root and its denial target from explicit environment variables"),
                **guards_info,
            },
            "product_code": ("no product module imports ..testing.guards; product code "
                             "resolves its deployment root through runtime/paths.py"),
        },
        "leftover_old_name": leftover,
        "guards_disclosed_old_name_refs": guards_refs,
        "checks": checks,
        "note": ("private candidate only; not merged, not deployed; the original tree "
                 "was neither imported nor written"),
    }
    (base / "R04_CANDIDATE_MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"destination": destination, "candidate_root": str(base),
            "all_ok": all(checks.values()), "checks": checks,
            "counts": manifest["counts"]}


def main() -> int:
    CANDIDATES.mkdir(parents=True, exist_ok=True)
    results = [build(destination) for destination in DESTINATIONS]
    print(json.dumps({"candidates": results,
                      "all_ok": all(r["all_ok"] for r in results)},
                     ensure_ascii=True, indent=2))
    return 0 if all(r["all_ok"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
