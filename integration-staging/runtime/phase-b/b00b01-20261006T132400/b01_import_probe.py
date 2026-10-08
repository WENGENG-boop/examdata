"""B01 import probe: run against the private candidate tree only.

Invoked as a subprocess with PYTHONPATH=<private>/src so that `examdata` and
`examdata.integration` resolve to the private candidate. Emits a JSON report on
stdout. Never imports the original tree; never writes outside the private tree.
"""
from __future__ import annotations

import importlib
import json
import os
import pathlib
import pkgutil
import sys

PRIVATE = pathlib.Path(os.environ["B01_PRIVATE_ROOT"]).resolve()
PKG_ROOT = PRIVATE / "src"


def within_private(path) -> bool:
    if not path:
        return False
    p = pathlib.Path(os.path.realpath(str(path)))
    root = pathlib.Path(os.path.realpath(str(PKG_ROOT)))
    return str(p) == str(root) or str(p).startswith(str(root) + os.sep)


report: dict = {
    "sys_path_head": sys.path[:4],
    "modules": {},
    "errors": {},
    "outside_private": [],
    "examdata_file": None,
}

try:
    import examdata  # noqa: F401
    report["examdata_file"] = getattr(examdata, "__file__", None)
    report["examdata_within_private"] = within_private(report["examdata_file"])
except Exception as exc:  # pragma: no cover - reported, not raised
    report["errors"]["examdata"] = f"{type(exc).__name__}: {exc}"

try:
    pkg = importlib.import_module("examdata.integration")
    report["modules"]["examdata.integration"] = getattr(pkg, "__file__", None)
    for info in pkgutil.walk_packages(pkg.__path__, prefix="examdata.integration."):
        name = info.name
        try:
            mod = importlib.import_module(name)
            report["modules"][name] = getattr(mod, "__file__", None)
        except Exception as exc:
            report["errors"][name] = f"{type(exc).__name__}: {exc}"
except Exception as exc:
    report["errors"]["examdata.integration"] = f"{type(exc).__name__}: {exc}"

for name, f in report["modules"].items():
    if not within_private(f):
        report["outside_private"].append({"module": name, "file": f})

report["counts"] = {
    "imported": len(report["modules"]),
    "errors": len(report["errors"]),
    "outside_private": len(report["outside_private"]),
}
print(json.dumps(report, ensure_ascii=False, indent=2))
