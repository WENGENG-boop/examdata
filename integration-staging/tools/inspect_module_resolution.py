#!/usr/bin/env python3
"""Read-only module-resolution inspection for the Phase A staging harness.

Run BEFORE any staged import. Uses `importlib.util.find_spec` only: no
application module is imported. Records the interpreter, the editable-install
artifact that points `examdata` at the original tree, and where each candidate
package would resolve with the staging `src` on `sys.path`.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import sysconfig
from datetime import datetime, timezone
from pathlib import Path

STAGING = Path(__file__).resolve().parents[1]
WORKSPACE = STAGING.parent
SRC = STAGING / "src"
ORIGINAL_SRC = WORKSPACE / "examdata" / "src"


def _norm(p) -> str:
    return os.path.normcase(os.path.realpath(str(p)))


def _within(child, parent) -> bool:
    c, p = _norm(child), _norm(parent)
    return c == p or c.startswith(p + os.sep)


def find_spec_report(name: str) -> dict:
    try:
        spec = importlib.util.find_spec(name)
    except BaseException as exc:  # noqa: BLE001 - report, never propagate
        return {"name": name, "error": f"{type(exc).__name__}: {exc}"}
    if spec is None:
        return {"name": name, "origin": None}
    return {
        "name": name,
        "origin": spec.origin,
        "search_locations": list(spec.submodule_search_locations or []),
    }


def main() -> int:
    purelib = Path(sysconfig.get_paths()["purelib"])
    editable = sorted(p.name for p in purelib.glob("__editable__*"))
    pth_text: dict[str, str] = {}
    for name in editable:
        try:
            pth_text[name] = (purelib / name).read_text(encoding="utf-8", errors="replace").strip()
        except OSError as exc:
            pth_text[name] = f"<unreadable: {exc}>"

    sys.path.insert(0, str(SRC))
    report = {
        "generated_at_local": datetime.now().astimezone().isoformat(timespec="seconds"),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "cwd": os.getcwd(),
        "python_executable": sys.executable,
        "python_version": sys.version,
        "staging_root": str(STAGING),
        "workspace_root": str(WORKSPACE),
        "staging_src_on_path": str(SRC),
        "site_packages": str(purelib),
        "editable_install_artifacts": editable,
        "editable_install_pth_text": pth_text,
        "find_spec": {
            "examdata": find_spec_report("examdata"),
            "examdata_integration": find_spec_report("examdata_integration"),
        },
    }
    original_origin = report["find_spec"]["examdata"].get("origin")
    staged_origin = report["find_spec"]["examdata_integration"].get("origin")
    report["verdicts"] = {
        "examdata_resolves_into_original_tree":
            bool(original_origin) and _within(original_origin, ORIGINAL_SRC),
        "examdata_integration_resolves_under_staging":
            bool(staged_origin) and _within(staged_origin, STAGING),
        "conclusion": (
            "HAZARD CONFIRMED: the shared venv's editable install resolves 'examdata' to the "
            "original examdata/src tree; the staged harness blocks that import and audits every "
            "loaded application module."
            if bool(original_origin) and _within(original_origin, ORIGINAL_SRC)
            else "no editable 'examdata' resolution into the original tree was detected"),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
