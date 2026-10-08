"""Build the B01 private candidate copy at the proposed final layout.

Release-independent B01 work (F03): copy the staged package to the proposed final
layout `examdata/src/examdata/integration/` *inside a private tree*, rename the
package, and keep the private tree the only import root. Nothing outside the two
write roots is touched; the original `examdata` tree is never imported or copied.

Private layout produced under runtime/phase-b/<run>/private/:

    private/
      src/examdata/__init__.py                 private shim for the target parent package
      src/examdata/integration/**              renamed from examdata_integration/**
      contracts/**                             repo-level contracts (target examdata/contracts)
      harness/private_guards.py                corrected isolation guard for the private tree

The copy is intentionally minimal: no venv, no live DB, no PDF/CIE data, no caches,
no secret config.
"""
from __future__ import annotations

import json
import pathlib
import shutil

ROOT = pathlib.Path(__file__).resolve().parents[4]  # C:/Users/weo/Desktop/api
RUN_ID = "b00b01-20261006T132400"
STAGING = ROOT / "integration-staging"
SRC_PKG = STAGING / "src/examdata_integration"
SRC_CONTRACTS = STAGING / "contracts"
PRIVATE = ROOT / "integration-staging/runtime/phase-b" / RUN_ID / "private"
TARGET_PKG = PRIVATE / "src/examdata/integration"

OLD = "examdata_integration"
NEW = "examdata.integration"

SKIP_DIRS = {"__pycache__", ".pytest_cache"}


def rewrite_text(path: pathlib.Path) -> int:
    """Rewrite the package name in a text file; return the number of replacements."""
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
            copied.append(str(rel).replace("\\", "/"))
    return copied


def main() -> int:
    if PRIVATE.exists():
        shutil.rmtree(PRIVATE)
    PRIVATE.mkdir(parents=True)

    py_copied = copy_tree(SRC_PKG, TARGET_PKG)
    contracts_copied = copy_tree(SRC_CONTRACTS, PRIVATE / "contracts")

    # Private shim so `examdata` resolves to the private tree, never the editable install.
    shim = PRIVATE / "src/examdata/__init__.py"
    shim.write_text(
        '"""Private candidate parent package (B01 layout validation).\n\n'
        'This shim exists only so `examdata.integration` can be imported from the\n'
        'private tree during layout validation. It is not the original package and\n'
        'carries no original code.\n"""\n\n__all__ = ["integration"]\n',
        encoding="utf-8")

    # Rename the package references in the copied sources.
    rewritten = {}
    for p in sorted(TARGET_PKG.rglob("*")):
        if p.suffix in (".py", ".json"):
            n = rewrite_text(p)
            if n:
                rewritten[str(p.relative_to(PRIVATE)).replace("\\", "/")] = n

    manifest = {
        "run_id": RUN_ID,
        "source": "integration-staging/src/examdata_integration + integration-staging/contracts",
        "private_root": str(PRIVATE),
        "target_package": "examdata.integration",
        "target_path_in_private": "src/examdata/integration",
        "py_files_copied": len(py_copied),
        "contracts_files_copied": len(contracts_copied),
        "rename_from": OLD,
        "rename_to": NEW,
        "files_rewritten": rewritten,
        "skipped_dirs": sorted(SKIP_DIRS),
        "note": ("private candidate only; not merged, not deployed; original tree untouched"),
    }
    (PRIVATE / "B01_PRIVATE_COPY_MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    checks = {
        "target_package_dir": TARGET_PKG.is_dir(),
        "no_old_name_left_in_py": not any(
            OLD in p.read_text(encoding="utf-8")
            for p in TARGET_PKG.rglob("*.py")),
        "no_old_name_left_in_json": not any(
            OLD in p.read_text(encoding="utf-8")
            for p in TARGET_PKG.rglob("*.json")),
        "private_shim": shim.is_file(),
        "contracts_present": (PRIVATE / "contracts/schema").is_dir(),
    }
    print(json.dumps({"private_root": str(PRIVATE), "checks": checks,
                      "py_files_copied": len(py_copied),
                      "contracts_files_copied": len(contracts_copied),
                      "all_ok": all(checks.values())}, indent=2))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
