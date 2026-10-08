"""Private, read-only doctor output (plan 6.2, 6.3, A06).

``doctor_report`` resolves the configuration, validates the component manifest,
probes the runtime, and reports path existence — and creates nothing. That is
the point of the split in plan 6.2: a read-only doctor or a module import must
not create production directories or silently initialise an empty database.

Secrets are reported as ``set``/``unset`` only; stderr, error messages, and any
path detail pass through the same redaction as the runner.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from .manifest import ManifestSet, load_manifest_set
from .redact import redact_text
from .runner import RunnerLimits
from .settings import SETTING_SPECS, SettingKind, ResolvedConfig, resolve_config

SCHEMA = "examdata.doctor/1"
PHASE_A_NETWORK_MODE = "offline"


def doctor_report(config: ResolvedConfig, manifest_set: ManifestSet | None = None, *,
                  runtime: str | None = None,
                  limits: RunnerLimits | None = None,
                  runtime_resolver=None) -> dict[str, Any]:
    """Build the read-only doctor report. Never creates a directory."""
    limits = limits or RunnerLimits()
    runtime_spec = runtime if runtime is not None else (config.get("node_executable") or "node")
    resolver = runtime_resolver or (
        lambda spec: (spec if Path(spec).exists() else None)
        if (os.sep in spec or "/" in spec or Path(spec).is_absolute())
        else shutil.which(spec))
    resolved_runtime = resolver(runtime_spec)

    paths: list[dict[str, Any]] = []
    for spec in SETTING_SPECS:
        if spec.kind is not SettingKind.PATH:
            continue
        value = config.get(spec.key)
        if not value:
            continue
        target = Path(str(value))
        paths.append({
            "key": spec.key,
            "role": spec.role,
            "path": str(target),
            "exists": target.exists(),
            "is_dir": target.is_dir(),
            "is_file": target.is_file(),
        })

    components: list[dict[str, Any]] = []
    problems: list[dict[str, Any]] = []
    if manifest_set is not None:
        root = Path(manifest_set.deployment_root)
        for cid in manifest_set.ids():
            manifest = manifest_set.components[cid]
            entry = manifest.entry_path(root)
            code = manifest.code_path(root)
            components.append({
                "component_id": cid,
                "name": manifest.name,
                "version": manifest.version,
                "source_revision": manifest.source_revision,
                "runtime": manifest.runtime,
                "code_location": manifest.code_location,
                "code_location_exists": code.is_dir(),
                "entry_point": manifest.entry_point,
                "entry_point_exists": entry.is_file(),
                "supported_commands": list(manifest.supported_commands),
                "environment_allowlist": list(manifest.environment_allowlist),
                "data_roots": manifest.data_root_paths(root),
                "read_write_policy": manifest.read_write_policy,
                "health_probe": manifest.health_probe,
                "valid": True,
            })
        problems = [p.to_dict() for p in manifest_set.problems]

    network_mode = config.get("network_mode")
    warnings = list(config.warnings)
    if manifest_set is not None:
        warnings.extend(manifest_set.warnings)
    if network_mode != PHASE_A_NETWORK_MODE:
        warnings.append(
            f"network_mode={network_mode!r} is not {PHASE_A_NETWORK_MODE!r}; Phase A must stay offline")

    return {
        "schema": SCHEMA,
        "mode": "PHASE_A_ISOLATED_ONLY",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "deployment_root": config.deployment_root,
        "config_file": config.config_file,
        "settings": config.settings_report(),
        "paths": paths,
        "components": components,
        "component_problems": problems,
        "runtime": {
            "spec": runtime_spec,
            "resolved": resolved_runtime,
            "found": resolved_runtime is not None,
        },
        "network": {
            "mode": network_mode,
            "phase_a_expected": PHASE_A_NETWORK_MODE,
            "compliant": network_mode == PHASE_A_NETWORK_MODE,
        },
        "runner_limits": limits.to_dict(),
        "warnings": warnings,
        "creates_directories": False,
    }


def build_report(*, env: Mapping[str, str] | None = None,
                 manifest_path: str | os.PathLike | None = None,
                 config_file: str | os.PathLike | None = None,
                 runtime: str | None = None,
                 deployment_root: str | os.PathLike | None = None) -> dict[str, Any]:
    """Resolve the configuration (env + optional manifest) and build the report."""
    manifest_set = None
    defaults = None
    if manifest_path is not None:
        manifest_set = load_manifest_set(manifest_path, deployment_root=deployment_root)
    if manifest_set is not None and manifest_set.components:
        defaults = {}
    config = resolve_config(env=env, config_file=config_file,
                            manifest_defaults=defaults, deployment_root=deployment_root)
    return doctor_report(config, manifest_set, runtime=runtime)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only Phase A doctor: resolve configuration, validate the "
                    "component manifest, probe the runtime. Creates nothing.")
    parser.add_argument("--manifest", default=None, help="component manifest JSON path")
    parser.add_argument("--config-file", default=None, help="explicit JSON config file")
    parser.add_argument("--runtime", default=None, help="runtime spec (default node)")
    parser.add_argument("--deployment-root", default=None)
    args = parser.parse_args(argv)

    report = build_report(env=os.environ, manifest_path=args.manifest,
                          config_file=args.config_file, runtime=args.runtime,
                          deployment_root=args.deployment_root)
    sys.stdout.write(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return 0


__all__ = ["SCHEMA", "doctor_report", "build_report", "main", "redact_text"]


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
