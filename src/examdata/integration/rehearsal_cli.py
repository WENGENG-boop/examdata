"""The isolated Phase A CLI for the staged package (packet W4a).

One entry point - ``examdata.cli:app`` - with a JSON-only stdout contract:
every invocation writes exactly one machine-readable envelope

    {"schema": "examdata.cli/1", "command", "ok", "root",
     "problems", "warnings", "result"}

and nothing else on stdout; exit code 0 means no problems, 1 means problems
or an error, and 2 is argparse's usage error (raised before any command
runs). A failing command reports its sanitized error inside the same
envelope - one JSON object, never a traceback.

What Phase A allows here:

* the deployment root resolves from ``--root`` or the canonical
  ``EXAMDATA_INTEGRATION_ROOT`` (never the test-only
  ``EXAMDATA_INTEGRATION_STAGING_ROOT``); the resolved root is written back
  into this process's own environment so the lazy imports that resolve the
  root at import time read the same root - no file and no child process is
  touched;
* every command is read-only: it reads the staged fixture dataset, the
  verified content store, the legacy registry and, when configured, the
  component manifest. Nothing writes a file, opens a network connection or
  starts a process, and ``catalog build`` reports ``writes: []`` because a
  Phase A build must not publish anything.

``configuration template`` is the one command that runs without a root: it
is pure text from the static setting specs.

Command surface::

    examdata status                  mode, root, versions, dataset, legacy baseline
    examdata configuration show      the resolved configuration (secrets as set/unset)
    examdata configuration template  the staging env template (static; no root)
    examdata configuration check     offline mode, configured paths, manifest
    examdata diagnostics             the doctor report plus fixture self-checks
    examdata catalog build           rebuild the fixture catalog and report the diff
    examdata catalog stats           the fixture snapshot's counts and revisions
    examdata catalog verify          snapshot and content-store self-checks
    examdata migrate plan            the A12 legacy compatibility projection
    examdata migrate check           legacy registry schema, sha and counts

Stdlib only; nothing here reads the original project, the network or a
database.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import sys
from pathlib import Path
from typing import Any, Sequence

SCHEMA = "examdata.cli/1"
MODE = "PHASE_A_ISOLATED_ONLY"
OFFLINE = "offline"
SOURCE_POLICY = "fixture_providers (labelled synthetic fixtures)"
MANIFEST_ENV = "EXAMDATA_COMPONENT_MANIFEST"


def _redact(text: object) -> str:
    from .runtime.redact import redact_text

    return redact_text(text)


def _resolve_cli_root(explicit: str | None) -> Path:
    """Resolve the deployment root (explicit wins) and sync the process env."""
    from .runtime.paths import ENV_ROOT, resolve_root

    root = resolve_root(explicit)
    os.environ[ENV_ROOT] = str(root)
    return root


def _manifest_path(args: argparse.Namespace) -> str | None:
    return getattr(args, "manifest", None) or os.environ.get(MANIFEST_ENV) or None


def _resolve_config_for(args: argparse.Namespace, root: Path):
    """The doctor's resolution: env + optional manifest defaults + config file."""
    from .runtime.manifest import load_manifest_set
    from .runtime.settings import resolve_config

    manifest_path = _manifest_path(args)
    manifest_set = None
    if manifest_path is not None:
        manifest_set = load_manifest_set(manifest_path, deployment_root=root)
    defaults = None
    if manifest_set is not None and manifest_set.components:
        defaults = {}
    config = resolve_config(env=os.environ, config_file=getattr(args, "config_file", None),
                            manifest_defaults=defaults, deployment_root=root)
    return config, manifest_set


def _envelope(command: str, *, root: Path | None, problems: Sequence[Any],
              warnings: Sequence[Any], result: Any) -> dict[str, Any]:
    problems = list(problems)
    return {
        "schema": SCHEMA,
        "command": command,
        "ok": not problems,
        "root": str(root) if root is not None else None,
        "problems": problems,
        "warnings": list(warnings),
        "result": result,
    }


def _failed(checks: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"code": "check_failed", "check": check["name"]}
            for check in checks if not check["ok"]]


# --------------------------------------------------------------------------- #
# status
# --------------------------------------------------------------------------- #
def _cmd_status(args: argparse.Namespace, root: Path) -> dict[str, Any]:
    from . import __version__

    problems: list[dict[str, Any]] = []
    root_exists = root.exists()
    result: dict[str, Any] = {
        "mode": MODE,
        "root_exists": root_exists,
        "version": __version__,
        "python": platform.python_version(),
    }
    if root_exists:
        from .api.dataset import default_dataset

        try:
            dataset = default_dataset(operations_root=None)
        except Exception as exc:
            problems.append({"code": "dataset_unavailable",
                             "detail": _redact(f"{type(exc).__name__}: {exc}")})
        else:
            snapshot = dataset.snapshot
            result["dataset"] = {
                "evidence": dataset.evidence,
                "revision": dataset.revision,
                "created_at": snapshot.created_at,
                "entries": len(snapshot.entries),
                "counts": dict(snapshot.counts),
            }
    else:
        problems.append({"code": "root_missing",
                         "detail": "the deployment root does not exist"})
    try:
        from .legacy import decisions

        result["legacy_baseline"] = {
            "rows": decisions.baseline_count(),
            "registry_sha256": decisions.registry_sha256(),
            "by_status": decisions.status_counts(),
        }
    except Exception as exc:
        problems.append({"code": "legacy_baseline_unavailable",
                         "detail": _redact(f"{type(exc).__name__}: {exc}")})
    return _envelope("status", root=root, problems=problems, warnings=[], result=result)


# --------------------------------------------------------------------------- #
# configuration
# --------------------------------------------------------------------------- #
def _cmd_configuration_show(args: argparse.Namespace, root: Path) -> dict[str, Any]:
    config, manifest_set = _resolve_config_for(args, root)
    problems: list[dict[str, Any]] = []
    warnings = list(config.warnings)
    if manifest_set is not None:
        warnings.extend(manifest_set.warnings)
        problems.extend(problem.to_dict() for problem in manifest_set.problems)
    result = {
        "settings": config.settings_report(),
        "config_file": config.config_file,
        "deployment_root": config.deployment_root,
        "writes": [],
    }
    return _envelope("configuration show", root=root, problems=problems,
                     warnings=warnings, result=result)


def _cmd_configuration_template(args: argparse.Namespace, root: Path | None) -> dict[str, Any]:
    from .runtime.settings import SETTING_SPECS, env_template

    rows = []
    for spec in SETTING_SPECS:
        rows.append({
            "key": spec.key,
            "env": spec.env,
            "kind": spec.kind.value,
            "role": spec.role,
            "secret": spec.secret,
            "default": None if spec.secret else spec.default,
            "aliases": list(spec.aliases),
            "legacy_aliases": list(spec.legacy_aliases),
            "choices": list(spec.choices),
            "new_in_phase_a": spec.new_in_phase_a,
        })
    result = {"settings": rows, "template": env_template(), "writes": []}
    return _envelope("configuration template", root=None, problems=[],
                     warnings=[], result=result)


def _cmd_configuration_check(args: argparse.Namespace, root: Path) -> dict[str, Any]:
    from .runtime.settings import SETTING_SPECS, SettingKind

    config, manifest_set = _resolve_config_for(args, root)
    problems: list[dict[str, Any]] = []
    warnings = list(config.warnings)
    checks: list[dict[str, Any]] = []
    network = config.get("network_mode")
    checks.append({"name": "network_mode_offline", "ok": network == OFFLINE,
                   "observed": network, "expected": OFFLINE})
    if network != OFFLINE:
        problems.append({"code": "network_mode_not_offline",
                         "detail": f"network_mode={network!r} is not {OFFLINE!r}"})
    if manifest_set is not None:
        warnings.extend(manifest_set.warnings)
        manifest_problems = [problem.to_dict() for problem in manifest_set.problems]
        checks.append({"name": "manifest_loads_cleanly", "ok": not manifest_problems,
                       "problem_count": len(manifest_problems)})
        problems.extend(manifest_problems)
    paths: list[dict[str, Any]] = []
    for spec in SETTING_SPECS:
        if spec.kind is not SettingKind.PATH:
            continue
        value = config.get(spec.key)
        if not value:
            continue
        target = Path(str(value))
        paths.append({"key": spec.key, "role": spec.role, "path": str(target),
                      "exists": target.exists(), "is_dir": target.is_dir(),
                      "is_file": target.is_file()})
    result = {
        "checks": checks,
        "paths": paths,
        "config_file": config.config_file,
        "deployment_root": config.deployment_root,
        "writes": [],
    }
    return _envelope("configuration check", root=root, problems=problems,
                     warnings=warnings, result=result)


# --------------------------------------------------------------------------- #
# diagnostics
# --------------------------------------------------------------------------- #
def _cmd_diagnostics(args: argparse.Namespace, root: Path) -> dict[str, Any]:
    from .runtime import doctor

    report = doctor.build_report(env=os.environ, manifest_path=_manifest_path(args),
                                 config_file=getattr(args, "config_file", None),
                                 runtime=getattr(args, "runtime", None),
                                 deployment_root=root)
    problems: list[dict[str, Any]] = list(report.get("component_problems") or [])
    warnings = list(report.get("warnings") or [])
    network = report.get("network") or {}
    if not network.get("compliant", False):
        problems.append({"code": "network_mode_not_offline",
                         "detail": f"network_mode={network.get('mode')!r} is not {OFFLINE!r}"})
    checks: list[dict[str, Any]] = []
    try:
        from .api.dataset import default_dataset
        from .catalog.model import compute_revision

        snapshot = default_dataset(operations_root=None).snapshot
    except Exception as exc:
        checks.append({"name": "dataset_builds", "ok": False,
                       "detail": _redact(f"{type(exc).__name__}: {exc}")})
    else:
        recomputed = compute_revision(snapshot.entries)
        checks.append({"name": "dataset_builds", "ok": True})
        checks.append({"name": "dataset_revision_recomputes",
                       "ok": recomputed == snapshot.dataset_revision,
                       "expected": snapshot.dataset_revision, "observed": recomputed})
    try:
        from .api.app import default_content_store

        store = default_content_store()
    except Exception as exc:
        checks.append({"name": "content_store_verifies", "ok": False,
                       "detail": _redact(f"{type(exc).__name__}: {exc}")})
    else:
        samples = len(store.all_samples)
        checks.append({"name": "content_store_verifies", "ok": store.ok and samples > 0,
                       "samples": samples, "store_problems": list(store.problems)})
    problems.extend(_failed(checks))
    result = {"report": report, "checks": checks, "writes": []}
    return _envelope("diagnostics", root=root, problems=problems,
                     warnings=warnings, result=result)


# --------------------------------------------------------------------------- #
# catalog
# --------------------------------------------------------------------------- #
def _cmd_catalog_build(args: argparse.Namespace, root: Path) -> dict[str, Any]:
    from .api.dataset import (build_fixture_snapshot, default_dataset,
                                          fixture_providers)
    from .catalog.builder import diff_snapshots
    from .catalog.model import compute_revision

    current = default_dataset(operations_root=None).snapshot
    rebuilt = build_fixture_snapshot(fixture_providers())
    candidate_revision = compute_revision(rebuilt.entries)
    matches = candidate_revision == current.dataset_revision
    problems: list[dict[str, Any]] = []
    if not matches:
        problems.append({"code": "catalog_not_reproducible",
                         "detail": f"candidate {candidate_revision} != current "
                                   f"{current.dataset_revision}"})
    result = {
        "writes": [],
        "source_policy": SOURCE_POLICY,
        "current_revision": current.dataset_revision,
        "candidate_revision": candidate_revision,
        "matches_current": matches,
        "counts": dict(rebuilt.counts),
        "diff": diff_snapshots(current, rebuilt.entries),
    }
    return _envelope("catalog build", root=root, problems=problems,
                     warnings=[], result=result)


def _cmd_catalog_stats(args: argparse.Namespace, root: Path) -> dict[str, Any]:
    from .api.dataset import default_dataset

    snapshot = default_dataset(operations_root=None).snapshot
    by_kind = {kind: n for kind, n in snapshot.counts.items() if kind != "total"}
    by_system: dict[str, int] = {}
    for entry in snapshot.entries:
        by_system[entry.system] = by_system.get(entry.system, 0) + 1
    result = {
        "revision": snapshot.dataset_revision,
        "created_at": snapshot.created_at,
        "entries": len(snapshot.entries),
        "counts": dict(snapshot.counts),
        "by_kind": dict(sorted(by_kind.items())),
        "by_system": dict(sorted(by_system.items())),
        "input_revisions": dict(snapshot.input_revisions),
        "snapshot_problems": [dict(p) for p in snapshot.problems],
        "writes": [],
    }
    return _envelope("catalog stats", root=root, problems=[], warnings=[], result=result)


def _cmd_catalog_verify(args: argparse.Namespace, root: Path) -> dict[str, Any]:
    from .api.app import default_content_store
    from .api.dataset import (build_fixture_snapshot, default_dataset,
                                          fixture_providers)
    from .catalog.model import compute_revision, counts_for
    from .contracts.canonical import public_id as derive_public_id
    from .contracts.enums import EntityKind

    snapshot = default_dataset(operations_root=None).snapshot
    checks: list[dict[str, Any]] = []

    recomputed = compute_revision(snapshot.entries)
    checks.append({"name": "revision_recomputes",
                   "ok": recomputed == snapshot.dataset_revision,
                   "expected": snapshot.dataset_revision, "observed": recomputed})

    observed_counts = counts_for(snapshot.entries)
    checks.append({"name": "counts_match", "ok": observed_counts == snapshot.counts,
                   "expected": dict(snapshot.counts), "observed": observed_counts})

    bad_ids: list[dict[str, Any]] = []
    for entry in snapshot.entries:
        try:
            derived = derive_public_id(EntityKind.coerce(entry.kind), entry.identity_fields)
        except (ValueError, KeyError, TypeError) as exc:
            bad_ids.append({"public_id": entry.public_id, "detail": _redact(str(exc))})
            continue
        if derived != entry.public_id:
            bad_ids.append({"public_id": entry.public_id, "derived": derived})
    checks.append({"name": "public_ids_derivable", "ok": not bad_ids,
                   "failures": bad_ids})

    rebuilt_revision = build_fixture_snapshot(fixture_providers()).dataset_revision
    checks.append({"name": "build_reproduces_current_revision",
                   "ok": rebuilt_revision == snapshot.dataset_revision,
                   "expected": snapshot.dataset_revision, "observed": rebuilt_revision})

    store = default_content_store()
    samples = len(store.all_samples)
    checks.append({"name": "content_store_verifies", "ok": store.ok and samples > 0,
                   "samples": samples, "store_problems": list(store.problems)})

    result = {
        "revision": snapshot.dataset_revision,
        "entries": len(snapshot.entries),
        "checks": checks,
        "snapshot_problems": [dict(p) for p in snapshot.problems],
        "writes": [],
    }
    return _envelope("catalog verify", root=root, problems=_failed(checks),
                     warnings=[], result=result)


# --------------------------------------------------------------------------- #
# migrate
# --------------------------------------------------------------------------- #
def _cmd_migrate_plan(args: argparse.Namespace, root: Path) -> dict[str, Any]:
    from .legacy import decisions

    rows = [{
        "row_id": row.get("row_id"),
        "method": row.get("method"),
        "legacy_path": row.get("legacy_path"),
        "mechanism": row.get("mechanism"),
        "status": row.get("status"),
        "v2_target": row.get("v2_target"),
        "deferred_reason": row.get("deferred_reason"),
        "coverage_kind": row.get("coverage_kind"),
    } for row in decisions.rows()]
    result = {
        "writes": [],
        "summary": decisions.coverage_summary(),
        "row_count": len(rows),
        "rows": rows,
    }
    return _envelope("migrate plan", root=root, problems=[], warnings=[], result=result)


def _cmd_migrate_check(args: argparse.Namespace, root: Path) -> dict[str, Any]:
    from .legacy import decisions

    document = decisions.registry()
    cached_sha = decisions.registry_sha256()
    file_sha = hashlib.sha256(decisions.REGISTRY_PATH.read_bytes()).hexdigest()
    checks = [
        {"name": "schema_matches", "ok": document.get("schema") == decisions.SCHEMA,
         "expected": decisions.SCHEMA, "observed": document.get("schema")},
        {"name": "sha256_matches_registry", "ok": file_sha == cached_sha,
         "expected": cached_sha, "observed": file_sha},
    ]
    result = {
        "writes": [],
        "registry_path": str(decisions.REGISTRY_PATH),
        "schema": decisions.SCHEMA,
        "rows": decisions.baseline_count(),
        "registry_sha256": cached_sha,
        "file_sha256": file_sha,
        "checks": checks,
        "coverage": decisions.coverage_summary(),
    }
    return _envelope("migrate check", root=root, problems=_failed(checks),
                     warnings=[], result=result)


# --------------------------------------------------------------------------- #
# entry point
# --------------------------------------------------------------------------- #
def _command_name(args: argparse.Namespace) -> str:
    sub = getattr(args, "subcommand", None)
    return f"{args.command} {sub}" if sub else args.command


def _dispatch(args: argparse.Namespace, root: Path | None, command: str) -> dict[str, Any]:
    if command == "status":
        return _cmd_status(args, root)
    if command == "configuration show":
        return _cmd_configuration_show(args, root)
    if command == "configuration template":
        return _cmd_configuration_template(args, root)
    if command == "configuration check":
        return _cmd_configuration_check(args, root)
    if command == "diagnostics":
        return _cmd_diagnostics(args, root)
    if command == "catalog build":
        return _cmd_catalog_build(args, root)
    if command == "catalog stats":
        return _cmd_catalog_stats(args, root)
    if command == "catalog verify":
        return _cmd_catalog_verify(args, root)
    if command == "migrate plan":
        return _cmd_migrate_plan(args, root)
    if command == "migrate check":
        return _cmd_migrate_check(args, root)
    raise RuntimeError(f"unknown command {command!r}")


def _parser() -> argparse.ArgumentParser:
    """The command surface; ``--root``/``--json`` work before or after a subcommand."""
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--root", default=argparse.SUPPRESS, metavar="PATH",
                        help="deployment root (default: EXAMDATA_INTEGRATION_ROOT)")
    common.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                        help="accepted for compatibility; output is always JSON")

    parser = argparse.ArgumentParser(
        prog="examdata",
        description="Phase A read-only CLI; every run writes one JSON envelope to stdout.")
    parser.add_argument("--root", default=None, metavar="PATH",
                        help="deployment root (default: EXAMDATA_INTEGRATION_ROOT)")
    parser.add_argument("--json", action="store_true",
                        help="accepted for compatibility; output is always JSON")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", parents=[common],
                   help="mode, root, versions, fixture dataset, legacy baseline")

    config = sub.add_parser("configuration", parents=[common],
                            help="show/check the resolved configuration")
    config_sub = config.add_subparsers(dest="subcommand", required=True)
    show = config_sub.add_parser("show", parents=[common],
                                 help="the resolved configuration (secrets set/unset)")
    show.add_argument("--manifest", default=None, help="component manifest JSON path")
    show.add_argument("--config-file", default=None, help="explicit JSON config file")
    config_sub.add_parser("template", parents=[common],
                          help="the staging env template (static; no root needed)")
    check = config_sub.add_parser("check", parents=[common],
                                  help="offline mode, configured paths, manifest")
    check.add_argument("--manifest", default=None, help="component manifest JSON path")
    check.add_argument("--config-file", default=None, help="explicit JSON config file")

    diag = sub.add_parser("diagnostics", parents=[common],
                          help="the doctor report plus fixture self-checks")
    diag.add_argument("--manifest", default=None, help="component manifest JSON path")
    diag.add_argument("--config-file", default=None, help="explicit JSON config file")
    diag.add_argument("--runtime", default=None, help="runtime spec probed by the doctor")

    catalog = sub.add_parser("catalog", parents=[common],
                             help="rebuild/read the fixture catalog (writes nothing)")
    catalog_sub = catalog.add_subparsers(dest="subcommand", required=True)
    catalog_sub.add_parser("build", parents=[common],
                           help="rebuild the fixture catalog and report the diff")
    catalog_sub.add_parser("stats", parents=[common],
                           help="fixture snapshot counts and revisions")
    catalog_sub.add_parser("verify", parents=[common],
                           help="fixture snapshot and content-store self-checks")

    migrate = sub.add_parser("migrate", parents=[common],
                             help="the A12 legacy compatibility projection (read-only)")
    migrate_sub = migrate.add_subparsers(dest="subcommand", required=True)
    migrate_sub.add_parser("plan", parents=[common],
                           help="the per-route compatibility projection")
    migrate_sub.add_parser("check", parents=[common],
                           help="legacy registry schema, sha and counts")
    return parser


def _emit(payload: dict[str, Any]) -> None:
    text = json.dumps(payload, ensure_ascii=False) + "\n"
    buffer = getattr(sys.stdout, "buffer", None)
    if buffer is not None:
        buffer.write(text.encode("utf-8"))
        buffer.flush()
    else:  # pragma: no cover - a replaced text stream in tests
        sys.stdout.write(text)
        sys.stdout.flush()


def app(argv: Sequence[str] | None = None) -> int:
    """Run one CLI invocation; return 0 (ok), 1 (problems or error) or 2 (usage)."""
    parser = _parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    command = _command_name(args)
    root: Path | None = None
    try:
        if command != "configuration template":
            root = _resolve_cli_root(getattr(args, "root", None))
        payload = _dispatch(args, root, command)
    except SystemExit:
        raise
    except Exception as exc:
        payload = _envelope(command, root=root, warnings=[], result=None,
                            problems=[{"code": "cli_error",
                                       "detail": _redact(f"{type(exc).__name__}: {exc}")}])
    _emit(payload)
    return 0 if payload["ok"] else 1


__all__ = ["SCHEMA", "app", "main"]


def main(argv: Sequence[str] | None = None) -> int:  # pragma: no cover - CLI entry
    return app(argv)


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(app())
