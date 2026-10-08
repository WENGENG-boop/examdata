"""R04 import probe: import the private target-layout candidate package.

The candidate root is supplied explicitly through ``R04_CANDIDATE_ROOT``. The
probe puts ``<candidate>/src`` on ``sys.path`` itself -- it does **not** rely on
``PYTHONPATH`` -- and it refuses to run with a staging-root override
(``EXAMDATA_INTEGRATION_STAGING_ROOT``) present, so a clean run proves the
package imports from its own root configuration alone.

Emits a JSON report on stdout and exits 0 only when every module resolved inside
the candidate, no module failed to import, and the runtime/legacy entry points
are importable. Never imports the original tree; never writes anything.
"""
from __future__ import annotations

import importlib
import json
import os
import pathlib
import pkgutil
import sys

CANDIDATE = pathlib.Path(os.environ["R04_CANDIDATE_ROOT"]).resolve()
PKG_SRC = CANDIDATE / "src"

ENTRY_POINTS = (
    "examdata.integration.api.dataset",
    "examdata.integration.api.app",
    "examdata.integration.runtime",
    "examdata.integration.runtime.doctor",
    "examdata.integration.legacy",
    "examdata.integration.legacy.bridge",
    "examdata.integration.legacy.decisions",
    "examdata.integration.legacy.parity",
    "examdata.integration.legacy.translate",
)

ROOT_ENV = "EXAMDATA_INTEGRATION_ROOT"
STAGING_OVERRIDE_ENV = "EXAMDATA_INTEGRATION_STAGING_ROOT"

sys.path.insert(0, str(PKG_SRC))


def within_candidate(path) -> bool:
    if not path:
        return False
    p = pathlib.Path(os.path.realpath(str(path)))
    root = pathlib.Path(os.path.realpath(str(PKG_SRC)))
    return str(p) == str(root) or str(p).startswith(str(root) + os.sep)


report: dict = {
    "candidate_root": str(CANDIDATE),
    "pkg_src": str(PKG_SRC),
    "pythonpath_env": os.environ.get("PYTHONPATH"),
    "root_env": os.environ.get(ROOT_ENV),
    "staging_override_present": STAGING_OVERRIDE_ENV in os.environ,
    "sys_path_head": sys.path[:4],
    "modules": {},
    "errors": {},
    "outside_candidate": [],
    "entry_points": {},
    "examdata_file": None,
    "examdata_within_candidate": False,
}

try:
    import examdata  # noqa: F401
    report["examdata_file"] = getattr(examdata, "__file__", None)
    report["examdata_within_candidate"] = within_candidate(report["examdata_file"])
except Exception as exc:  # pragma: no cover - reported, never raised
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

for name in ENTRY_POINTS:
    try:
        mod = importlib.import_module(name)
        file = getattr(mod, "__file__", None)
        report["entry_points"][name] = file
        if not within_candidate(file):
            report["outside_candidate"].append({"module": name, "file": file})
    except Exception as exc:
        report["errors"][name] = f"{type(exc).__name__}: {exc}"

for name, file in report["modules"].items():
    if not within_candidate(file):
        report["outside_candidate"].append({"module": name, "file": file})

report["counts"] = {
    "walked": len(report["modules"]),
    "entry_points": len(report["entry_points"]),
    "errors": len(report["errors"]),
    "outside_candidate": len(report["outside_candidate"]),
}
report["ok"] = bool(
    report["examdata_within_candidate"]
    and not report["errors"]
    and not report["outside_candidate"]
    and not report["staging_override_present"]
    and report["entry_points"].keys() == set(ENTRY_POINTS)
)
print(json.dumps(report, ensure_ascii=True, indent=2))
raise SystemExit(0 if report["ok"] else 1)
