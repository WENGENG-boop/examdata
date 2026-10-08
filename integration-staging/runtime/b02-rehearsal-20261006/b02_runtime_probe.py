"""B02 runtime probe: shared configuration, old aliases, startup, discovery.

Runs with ``<candidate>/src`` as the only import root (inserted by the probe
itself, no ``PYTHONPATH``) and the candidate root supplied explicitly through
``EXAMDATA_INTEGRATION_ROOT``. It rehearses the parts of the B02 acceptance that
do not need the original tree:

* **startup behaviour** -- importing the runtime package creates no file, and
  resolving a configuration mutates neither ``os.environ`` nor the candidate;
* **old aliases** -- the legacy env aliases still resolve to the canonical
  setting with a deprecation warning, the canonical name wins, and two different
  values for the same setting are still a hard conflict;
* **configuration precedence** -- explicit > environment > config file >
  manifest defaults > built-in default, unchanged;
* **component packaging** -- the packaged component manifest admits exactly the
  synthetic component, and discovery is independent of the current working
  directory (re-checked after ``os.chdir``);
* **runtime / legacy entry points** -- every entry point imports from inside the
  candidate.

Real legacy Node gateway execution stays ``not_run``: the gate
``original_paths_released`` is closed, so no real gateway is started.

Emits a JSON report on stdout; exits 0 only when every check passes.
"""
from __future__ import annotations

import importlib
import json
import os
import pathlib
import sys

CANDIDATE = pathlib.Path(os.environ["B02_CANDIDATE_ROOT"]).resolve()
PKG_SRC = CANDIDATE / "src"
WORKSPACE = pathlib.Path(os.environ["B02_WORKSPACE_ROOT"]).resolve()
TMP_DIR = pathlib.Path(os.environ["B02_TMP_DIR"]).resolve()
ORIGINAL_APP_CODE = WORKSPACE / "examdata" / "src"

ROOT_ENV = "EXAMDATA_INTEGRATION_ROOT"
STAGING_OVERRIDE_ENV = "EXAMDATA_INTEGRATION_STAGING_ROOT"

sys.path.insert(0, str(PKG_SRC))

checks: list[tuple[str, bool, str]] = []


def expect(name: str, condition: bool, detail: str = "") -> None:
    checks.append((name, bool(condition), detail))


def snapshot_tree(base: pathlib.Path) -> set[str]:
    out: set[str] = set()
    for p in base.rglob("*"):
        if any(part in {"__pycache__", ".pytest_cache"} for part in p.parts):
            continue
        out.add(p.relative_to(base).as_posix())
    return out


def norm(value: object) -> str:
    return os.path.normpath(os.path.abspath(str(value)))


def within_candidate(path, root: pathlib.Path = PKG_SRC) -> bool:
    if not path:
        return False
    p = pathlib.Path(os.path.realpath(str(path)))
    r = pathlib.Path(os.path.realpath(str(root)))
    return str(p) == str(r) or str(p).startswith(str(r) + os.sep)


report: dict = {
    "candidate_root": str(CANDIDATE),
    "workspace_root": str(WORKSPACE),
    "cwd_at_start": os.getcwd(),
    "pythonpath_env": os.environ.get("PYTHONPATH"),
    "root_env": os.environ.get(ROOT_ENV),
    "staging_override_present": STAGING_OVERRIDE_ENV in os.environ,
}

# --- startup behaviour: the import itself has no filesystem side effect ------ #
tree_before = snapshot_tree(CANDIDATE)
from examdata.integration.runtime import (  # noqa: E402
    ConfigConflictError,
    ConfigError,
    env_template,
    resolve_config,
)
from examdata.integration.runtime.manifest import load_manifest_set  # noqa: E402
from examdata.integration.runtime import paths as paths_mod  # noqa: E402

tree_after = snapshot_tree(CANDIDATE)
report["startup"] = {
    "files_before_import": len(tree_before),
    "files_after_import": len(tree_after),
    "added": sorted(tree_after - tree_before)[:20],
}
expect("startup.import_creates_nothing", tree_before == tree_after,
       f"added={sorted(tree_after - tree_before)[:10]}")
expect("startup.no_staging_override", not report["staging_override_present"])
expect("startup.root_env_is_candidate",
       pathlib.Path(os.path.realpath(report["root_env"] or ""))
       == pathlib.Path(os.path.realpath(str(CANDIDATE))),
       str(report["root_env"]))

report["module_origin"] = getattr(sys.modules["examdata.integration.runtime"], "__file__", None)
report["paths_module"] = getattr(paths_mod, "__file__", None)
expect("origin.runtime_within_candidate", within_candidate(report["module_origin"]),
       str(report["module_origin"]))
expect("origin.paths_within_candidate", within_candidate(report["paths_module"]),
       str(report["paths_module"]))

# --- configuration resolution: precedence, environment untouched ------------- #
env_before = dict(os.environ)
TMP_DIR.mkdir(parents=True, exist_ok=True)
cfg_file = TMP_DIR / "b02-config.json"
cfg_file.write_text(json.dumps({"ielts_max_concurrent": 7}), encoding="utf-8")

layers = dict(
    deployment_root=TMP_DIR,
    explicit={"ielts_max_concurrent": 9},
    env={"EXAMDATA_IELTS_MAX_CONCURRENT": "8"},
    config_file=cfg_file,
    manifest_defaults={"ielts_max_concurrent": 6},
)
from_explicit = resolve_config(**layers)
without_explicit = {k: v for k, v in layers.items() if k != "explicit"}
from_env = resolve_config(**without_explicit)
without_env = {k: v for k, v in without_explicit.items() if k != "env"}
from_file = resolve_config(**without_env)
without_file = {k: v for k, v in without_env.items() if k != "config_file"}
from_manifest = resolve_config(**without_file)
from_default = resolve_config(deployment_root=TMP_DIR, env={})

precedence = {
    "explicit": from_explicit.get("ielts_max_concurrent"),
    "environment": from_env.get("ielts_max_concurrent"),
    "config_file": from_file.get("ielts_max_concurrent"),
    "manifest_default": from_manifest.get("ielts_max_concurrent"),
    "default": from_default.get("ielts_max_concurrent"),
}
report["precedence"] = precedence
expect("precedence.order_unchanged",
       list(precedence.values()) == [9, 8, 7, 6, 4], json.dumps(precedence))

report["env_mutation"] = {"mutated": env_before != dict(os.environ),
                          "names_added": sorted(set(os.environ) - set(env_before))[:10]}
expect("startup.resolve_config_does_not_mutate_environ",
       env_before == dict(os.environ), json.dumps(report["env_mutation"]))

# --- old aliases ------------------------------------------------------------- #
ielts_target = TMP_DIR / "data" / "ielts"
toefl_target = TMP_DIR / "data" / "toefl"

alias_cfg = resolve_config(deployment_root=TMP_DIR,
                           env={"IELTS_API_DIR": str(ielts_target),
                                "TOEFL_API_DIR": str(toefl_target)})
report["legacy_aliases"] = {
    "ielts_dir": alias_cfg.get("ielts_dir"),
    "ielts_origin": alias_cfg.origins.get("ielts_dir"),
    "toefl_dir": alias_cfg.get("toefl_dir"),
    "toefl_origin": alias_cfg.origins.get("toefl_dir"),
    "warnings": list(alias_cfg.warnings),
}
expect("alias.ielts_legacy_resolves",
       alias_cfg.get("ielts_dir") == norm(ielts_target), str(alias_cfg.get("ielts_dir")))
expect("alias.ielts_origin_is_legacy_name",
       alias_cfg.origins.get("ielts_dir") == "env:IELTS_API_DIR",
       str(alias_cfg.origins.get("ielts_dir")))
expect("alias.toefl_legacy_resolves",
       alias_cfg.get("toefl_dir") == norm(toefl_target), str(alias_cfg.get("toefl_dir")))
expect("alias.deprecation_warned",
       sum("deprecated alias" in w for w in alias_cfg.warnings) == 2,
       json.dumps(alias_cfg.warnings))

canonical_cfg = resolve_config(deployment_root=TMP_DIR,
                               env={"EXAMDATA_IELTS_DIR": str(ielts_target)})
report["canonical_name"] = {"warnings": list(canonical_cfg.warnings),
                            "origin": canonical_cfg.origins.get("ielts_dir")}
expect("alias.canonical_name_needs_no_warning",
       not any("deprecated" in w for w in canonical_cfg.warnings),
       json.dumps(canonical_cfg.warnings))

try:
    resolve_config(deployment_root=TMP_DIR,
                   env={"IELTS_API_DIR": str(ielts_target),
                        "EXAMDATA_IELTS_DIR": str(TMP_DIR / "data" / "ielts2")})
    conflict_raised, conflict_detail = False, "no error raised"
except ConfigConflictError as exc:
    conflict_raised, conflict_detail = True, str(exc)
except Exception as exc:  # pragma: no cover - reported, never raised
    conflict_raised, conflict_detail = False, f"{type(exc).__name__}: {exc}"
report["alias_conflict"] = {"raised": conflict_raised, "detail": conflict_detail[:200]}
expect("alias.conflicting_values_still_rejected", conflict_raised, conflict_detail[:160])

same_value_cfg = resolve_config(
    deployment_root=TMP_DIR,
    env={"IELTS_API_DIR": str(ielts_target), "EXAMDATA_IELTS_DIR": str(ielts_target)})
expect("alias.same_value_only_warns",
       any("legacy alias" in w for w in same_value_cfg.warnings)
       and same_value_cfg.get("ielts_dir") == norm(ielts_target),
       json.dumps(same_value_cfg.warnings))

template = env_template()
report["env_template_tokens"] = {
    "IELTS_API_DIR": "IELTS_API_DIR -> EXAMDATA_IELTS_DIR" in template,
    "TOEFL_API_DIR": "TOEFL_API_DIR -> EXAMDATA_TOEFL_DIR" in template,
}
expect("alias.env_template_still_documents_aliases",
       all(report["env_template_tokens"].values()), json.dumps(report["env_template_tokens"]))

# --- parsing still creates nothing ------------------------------------------- #
sentinel = TMP_DIR / "b02-not-created" / "catalog"
resolve_config(deployment_root=TMP_DIR, env={"EXAMDATA_CATALOG_ROOT": str(sentinel)})
expect("startup.resolve_creates_no_directory", not sentinel.exists(), str(sentinel))

outside = WORKSPACE / "docs" / "b02-should-not-create"
try:
    bad = resolve_config(deployment_root=TMP_DIR,
                         explicit={"data_dir": str(TMP_DIR / "data"),
                                   "catalog_root": str(outside)})
    bad.ensure_directories()
    refused, refuse_detail = False, "no error raised"
except ConfigError as exc:
    refused, refuse_detail = True, str(exc)
except Exception as exc:  # pragma: no cover - reported, never raised
    refused, refuse_detail = False, f"{type(exc).__name__}: {exc}"
report["ensure_directories_refusal"] = {"refused": refused, "detail": refuse_detail[:200],
                                        "created": outside.exists()}
expect("startup.ensure_directories_refuses_outside_root",
       refused and not outside.exists(), refuse_detail[:160])

secret_cfg = resolve_config(deployment_root=TMP_DIR,
                            explicit={"api_key": "b02-synthetic-secret"}, env={})
rendered = json.dumps(secret_cfg.settings_report())
expect("startup.secret_not_rendered",
       "b02-synthetic-secret" not in rendered
       and {r["key"]: r["value"] for r in secret_cfg.settings_report()}["api_key"] == "set")

# --- component packaging + cwd-independent discovery ------------------------- #
manifest_path = CANDIDATE / "components" / "manifest.json"


def discover() -> dict:
    manifest_set = load_manifest_set(manifest_path, deployment_root=CANDIDATE,
                                     require_entry_point=True)
    component = manifest_set.get("fake_cli")
    entry = component.entry_path(CANDIDATE) if component else None
    return {
        "cwd": os.getcwd(),
        "ids": manifest_set.ids(),
        "problems": [p.to_dict() if hasattr(p, "to_dict") else str(p)
                     for p in manifest_set.problems],
        "entry_path": str(entry) if entry else None,
    }


here = discover()
expect("packaging.component_manifest_packaged", manifest_path.is_file(), str(manifest_path))
expect("packaging.exactly_fake_cli", here["ids"] == ["fake_cli"], str(here["ids"]))
expect("packaging.no_problems", not here["problems"], json.dumps(here["problems"])[:300])
expect("packaging.entry_point_inside_candidate",
       bool(here["entry_path"]) and within_candidate(here["entry_path"], CANDIDATE),
       str(here["entry_path"]))

# The alternate working directory must differ from wherever this probe started,
# so the two discovery runs genuinely come from two directories.
start_cwd = os.getcwd()
alt_cwd = TMP_DIR / "probe-alt-cwd"
alt_cwd.mkdir(parents=True, exist_ok=True)
target_cwd = CANDIDATE if (
    pathlib.Path(os.path.realpath(start_cwd)) == pathlib.Path(os.path.realpath(str(alt_cwd)))
) else alt_cwd
os.chdir(target_cwd)
try:
    elsewhere = discover()
finally:
    os.chdir(start_cwd)


def comparable(entry: dict) -> dict:
    return {k: entry[k] for k in ("ids", "problems", "entry_path")}


report["discovery"] = {"from_candidate_cwd": here, "from_alt_cwd": elsewhere}
expect("packaging.discovery_independent_of_cwd",
       comparable(here) == comparable(elsewhere),
       f"{comparable(here)} != {comparable(elsewhere)}")
expect("packaging.discovery_recorded_two_cwds",
       here["cwd"] != elsewhere["cwd"], f"{here['cwd']} vs {elsewhere['cwd']}")

# --- runtime / legacy entry points ------------------------------------------- #
ENTRY_POINTS = (
    "examdata.integration.runtime",
    "examdata.integration.runtime.settings",
    "examdata.integration.runtime.runner",
    "examdata.integration.runtime.manifest",
    "examdata.integration.runtime.paths",
    "examdata.integration.runtime.doctor",
    "examdata.integration.legacy",
    "examdata.integration.legacy.bridge",
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

# --- not_run ---------------------------------------------------------------- #
report["not_run"] = [
    {"check": "real legacy Node gateway execution (ielts-api / toefl-api)",
     "reason": "gate original_paths_released is closed; no original service is started"},
    {"check": "real Node component execution",
     "reason": "gate original_paths_released is closed; synthetic fixture only"},
    {"check": "real database schema / data-root migration",
     "reason": "gate real_data_write_authorized is closed; schema and data roots unchanged"},
]

report["counts"] = {
    "checks": len(checks),
    "checks_failed": sum(1 for _, ok, _ in checks if not ok),
    "entry_points_ok": sum(1 for n, ok, _ in checks if n.startswith("entry.") and ok),
    "legacy_aliases_preserved": 2 if (
        alias_cfg.origins.get("ielts_dir") == "env:IELTS_API_DIR"
        and alias_cfg.origins.get("toefl_dir") == "env:TOEFL_API_DIR") else 0,
    "discovery_cwds": 2,
}
report["checks"] = [{"name": n, "ok": ok, "detail": d} for n, ok, d in checks]
report["failed"] = [n for n, ok, _ in checks if not ok]
report["ok"] = not report["failed"]
print(json.dumps(report, ensure_ascii=True, indent=2))
raise SystemExit(0 if report["ok"] else 1)
