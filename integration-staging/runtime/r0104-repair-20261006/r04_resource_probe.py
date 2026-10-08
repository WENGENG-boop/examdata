"""R04 resource probe: schema access, synthetic Node discovery, harness denial.

Runs with ``<candidate>/src`` as the only import root (inserted by the probe
itself, no ``PYTHONPATH``) and the candidate root supplied explicitly through
``EXAMDATA_INTEGRATION_ROOT``. It checks:

* module origin -- the imported package resolves inside the candidate;
* schema access -- every ``contracts/schema/*.json`` loads;
* synthetic Node discovery -- the candidate's own component manifest admits
  exactly the synthetic ``fake_cli`` component and its entry point resolves
  inside the candidate;
* negative control -- a manifest whose ``code_location`` escapes the root is
  refused by the loader, and the private harness guard still denies the real
  original application path;
* positive controls -- the harness admits a path inside the candidate, and
  ``check_node_file`` accepts the synthetic component entry point.

Real Node execution and real original-source validation stay ``not_run``: the
gate ``original_paths_released`` is closed.

Emits a JSON report on stdout; exits 0 only when every check passes.
"""
from __future__ import annotations

import importlib
import json
import os
import pathlib
import sys

CANDIDATE = pathlib.Path(os.environ["R04_CANDIDATE_ROOT"]).resolve()
PKG_SRC = CANDIDATE / "src"
WORKSPACE = pathlib.Path(os.environ["R04_WORKSPACE_ROOT"]).resolve()
ORIGINAL_APP_CODE = WORKSPACE / "examdata" / "src"
TMP_DIR = pathlib.Path(os.environ["R04_TMP_DIR"]).resolve()

ROOT_ENV = "EXAMDATA_INTEGRATION_ROOT"
STAGING_OVERRIDE_ENV = "EXAMDATA_INTEGRATION_STAGING_ROOT"
ORIGINAL_ENV = "EXAMDATA_INTEGRATION_ORIGINAL_APP_CODE"

sys.path.insert(0, str(PKG_SRC))

checks: list[tuple[str, bool, str]] = []


def expect(name: str, condition: bool, detail: str = "") -> None:
    checks.append((name, bool(condition), detail))


report: dict = {
    "candidate_root": str(CANDIDATE),
    "workspace_root": str(WORKSPACE),
    "original_app_code": str(ORIGINAL_APP_CODE),
    "pythonpath_env": os.environ.get("PYTHONPATH"),
    "root_env": os.environ.get(ROOT_ENV),
    "original_env": os.environ.get(ORIGINAL_ENV),
    "staging_override_present": STAGING_OVERRIDE_ENV in os.environ,
}

# --- module origin --------------------------------------------------------- #
import examdata  # noqa: E402
import examdata.integration  # noqa: E402

report["module_origin"] = {
    "examdata": getattr(examdata, "__file__", None),
    "examdata.integration": getattr(examdata.integration, "__file__", None),
}
report["paths_module"] = getattr(
    importlib.import_module("examdata.integration.runtime.paths"), "__file__", None)


def within_candidate(path, root=PKG_SRC) -> bool:
    if not path:
        return False
    p = pathlib.Path(os.path.realpath(str(path)))
    r = pathlib.Path(os.path.realpath(str(root)))
    return str(p) == str(r) or str(p).startswith(str(r) + os.sep)


expect("origin.examdata_within_candidate", within_candidate(report["module_origin"]["examdata"]),
       str(report["module_origin"]["examdata"]))
expect("origin.paths_module_within_candidate", within_candidate(report["paths_module"]),
       str(report["paths_module"]))
expect("origin.no_staging_override", not report["staging_override_present"])

# --- runtime / legacy entry points ----------------------------------------- #
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
entry_points: dict[str, str | None] = {}
entry_errors: dict[str, str] = {}
for name in ENTRY_POINTS:
    try:
        mod = importlib.import_module(name)
        file = getattr(mod, "__file__", None)
        entry_points[name] = file
        expect(f"entry.{name}", within_candidate(file), str(file))
    except Exception as exc:  # pragma: no cover - reported, never raised
        entry_errors[name] = f"{type(exc).__name__}: {exc}"
        expect(f"entry.{name}", False, entry_errors[name])
report["entry_points"] = entry_points
report["entry_errors"] = entry_errors

# --- schema access --------------------------------------------------------- #
schema_dir = CANDIDATE / "contracts" / "schema"
schema_files = sorted(schema_dir.glob("*.json")) if schema_dir.is_dir() else []
schema_bad: list[dict] = []
for schema in schema_files:
    try:
        json.loads(schema.read_text(encoding="utf-8"))
    except Exception as exc:
        schema_bad.append({"file": schema.name, "error": f"{type(exc).__name__}: {exc}"})
report["schema"] = {"files": len(schema_files), "loaded_ok": len(schema_files) - len(schema_bad),
                    "bad": schema_bad}
expect("schema.files_found", len(schema_files) == 28, f"found {len(schema_files)}")
expect("schema.all_load", not schema_bad, json.dumps(schema_bad)[:400])

# --- synthetic Node discovery ---------------------------------------------- #
from examdata.integration.runtime.manifest import load_manifest_set  # noqa: E402
from examdata.integration.testing import node_guard  # noqa: E402
from examdata.integration.testing.guards import (  # noqa: E402
    ForbiddenPathError,
    ORIGINAL_APP_CODE as GUARD_ORIGINAL_APP_CODE,
    STAGING_ROOT as GUARD_STAGING_ROOT,
    ensure_staged_path,
)

report["guard"] = {
    "staging_root": str(GUARD_STAGING_ROOT),
    "original_app_code": str(GUARD_ORIGINAL_APP_CODE),
}
expect("guard.staging_root_is_candidate",
       pathlib.Path(os.path.realpath(str(GUARD_STAGING_ROOT)))
       == pathlib.Path(os.path.realpath(str(CANDIDATE))),
       str(GUARD_STAGING_ROOT))
expect("guard.original_app_code_is_real_workspace",
       pathlib.Path(os.path.realpath(str(GUARD_ORIGINAL_APP_CODE)))
       == pathlib.Path(os.path.realpath(str(ORIGINAL_APP_CODE))),
       str(GUARD_ORIGINAL_APP_CODE))

manifest_path = CANDIDATE / "components" / "manifest.json"
manifest_set = load_manifest_set(manifest_path, deployment_root=CANDIDATE,
                                 require_entry_point=True)
report["node_discovery"] = {
    "manifest": str(manifest_path),
    "ids": manifest_set.ids(),
    "problems": [p.to_dict() if hasattr(p, "to_dict") else str(p)
                 for p in manifest_set.problems],
}
expect("node.ids_exactly_fake_cli", manifest_set.ids() == ["fake_cli"],
       str(manifest_set.ids()))
expect("node.no_problems", not manifest_set.problems,
       json.dumps(report["node_discovery"]["problems"])[:400])

component = manifest_set.get("fake_cli")
entry_path = component.entry_path(CANDIDATE) if component else None
report["node_discovery"]["entry_path"] = str(entry_path) if entry_path else None
expect("node.entry_point_inside_candidate",
       bool(entry_path) and within_candidate(entry_path, CANDIDATE), str(entry_path))

resolved_specs = node_guard.check_node_file(entry_path) if entry_path else None
report["node_discovery"]["entry_specifiers"] = resolved_specs
expect("node.check_node_file_ok", resolved_specs is not None,
       str(resolved_specs))

# --- negative controls ----------------------------------------------------- #
TMP_DIR.mkdir(parents=True, exist_ok=True)
escaping = TMP_DIR / "r04_escaping_manifest.json"
payload = json.loads(manifest_path.read_text(encoding="utf-8"))
payload["components"][0]["code_location"] = "../outside"
escaping.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
escaping_set = load_manifest_set(escaping, deployment_root=CANDIDATE,
                                 require_entry_point=True)
report["negative_escaping_manifest"] = {
    "admitted": escaping_set.ids(),
    "problem_codes": [p.code if hasattr(p, "code") else str(p)
                      for p in escaping_set.problems],
}
expect("negative.escaping_code_location_refused", escaping_set.ids() == [],
       str(escaping_set.ids()))
expect("negative.escaping_code_location_has_problem", bool(escaping_set.problems),
       json.dumps(report["negative_escaping_manifest"]["problem_codes"]))

original_sample = ORIGINAL_APP_CODE / "examdata" / "api" / "app.py"
try:
    ensure_staged_path(original_sample, "R04 negative control")
    original_denied, original_detail = False, "no error raised"
except ForbiddenPathError as exc:
    original_denied, original_detail = True, str(exc)
except Exception as exc:  # pragma: no cover - reported, never raised
    original_denied, original_detail = False, f"{type(exc).__name__}: {exc}"
report["negative_original_path"] = {"path": str(original_sample), "denied": original_denied,
                                   "detail": original_detail[:300]}
expect("negative.original_app_code_denied", original_denied, original_detail[:200])

outside_sample = WORKSPACE / "SESSION_CONTINUATION_PLAN.md"
try:
    ensure_staged_path(outside_sample, "R04 negative control")
    outside_denied, outside_detail = False, "no error raised"
except ForbiddenPathError as exc:
    outside_denied, outside_detail = True, str(exc)
except Exception as exc:  # pragma: no cover - reported, never raised
    outside_denied, outside_detail = False, f"{type(exc).__name__}: {exc}"
report["negative_outside_path"] = {"path": str(outside_sample), "denied": outside_denied,
                                   "detail": outside_detail[:300]}
expect("negative.outside_root_denied", outside_denied, outside_detail[:200])

try:
    node_guard.check_node_file(original_sample.with_suffix(".mjs"))
    node_denied, node_detail = False, "no error raised"
except ForbiddenPathError as exc:
    node_denied, node_detail = True, str(exc)
except Exception as exc:  # pragma: no cover - reported, never raised
    node_denied, node_detail = False, f"{type(exc).__name__}: {exc}"
report["negative_node_guard"] = {"denied": node_denied, "detail": node_detail[:300]}
expect("negative.node_guard_denies_original", node_denied, node_detail[:200])

# --- positive controls ----------------------------------------------------- #
try:
    admitted = ensure_staged_path(entry_path, "R04 positive control")
    positive_ok, positive_detail = True, str(admitted)
except Exception as exc:  # pragma: no cover - reported, never raised
    positive_ok, positive_detail = False, f"{type(exc).__name__}: {exc}"
report["positive_staged_path"] = {"path": str(entry_path), "admitted": positive_ok,
                                  "detail": positive_detail[:300]}
expect("positive.staged_path_admitted", positive_ok, positive_detail[:200])

# --- not_run --------------------------------------------------------------- #
report["not_run"] = [
    {"check": "real Node component execution",
     "reason": "gate original_paths_released is closed; synthetic fixture only"},
    {"check": "real original source / database validation",
     "reason": "gate original_paths_released is closed; no original path is read"},
]

report["notes"] = [
    ("the loader containment rule `path_escapes_root` is only reachable through a "
     "symlink/junction; an escaping code_location is refused earlier by "
     "`not_relative_path`, and containment itself is exercised by the harness path "
     "guard checks below"),
]

report["counts"] = {
    "entry_points_ok": sum(1 for n, ok, _ in checks if n.startswith("entry.") and ok),
    "schema_files": len(schema_files),
    "schema_loaded_ok": len(schema_files) - len(schema_bad),
    "node_components_admitted": len(manifest_set.ids()),
    "checks": len(checks),
    "checks_failed": sum(1 for _, ok, _ in checks if not ok),
}

report["checks"] = [{"name": n, "ok": ok, "detail": d} for n, ok, d in checks]
report["failed"] = [n for n, ok, _ in checks if not ok]
report["ok"] = not report["failed"]
print(json.dumps(report, ensure_ascii=True, indent=2))
raise SystemExit(0 if report["ok"] else 1)
