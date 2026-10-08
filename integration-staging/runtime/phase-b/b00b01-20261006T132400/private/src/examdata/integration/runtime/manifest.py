"""Component manifest validation (plan 6.3, A06).

A component manifest records, per component: name, version, source
revision/hash, code location, runtime, entry point, supported commands, input
and output schema, environment allowlist, required data roots, read/write
policy, and a health probe.

Production component discovery must not depend on ``parents[4]``, the current
working directory, or an unrelated developer folder. This module therefore
takes an explicit manifest path and an explicit deployment root, and every
location it accepts must be a *relative* path that resolves inside that root.
An invalid component is never admitted to the whitelist the runner uses: the
problems are reported (and rendered by the doctor), but the component is not
allowed to run.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..testing.guards import STAGING_ROOT, is_within

MANIFEST_VERSION = "examdata.component-manifest/1"

ALLOWED_RUNTIMES: tuple[str, ...] = ("node", "python")
READ_WRITE_POLICIES: tuple[str, ...] = ("read_only", "write_scoped", "read_write")

REQUIRED_FIELDS: tuple[str, ...] = (
    "component_id", "name", "version", "source_revision", "code_location",
    "runtime", "entry_point", "supported_commands", "environment_allowlist",
    "data_roots", "read_write_policy",
)

_ID_RE = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
_ENV_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_COMMAND_RE = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
_ROLE_RE = re.compile(r"^[a-z][a-z0-9_]{0,31}$")


class ManifestError(ValueError):
    """The manifest document itself is unusable (unreadable/wrong version)."""


@dataclass(frozen=True)
class ManifestProblem:
    """One validation problem, with a stable code and the offending field."""

    code: str
    field: str
    detail: str
    component_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "field": self.field, "detail": self.detail,
                "component_id": self.component_id}


def _problem(code: str, field: str, detail: str, component_id: str | None = None) -> ManifestProblem:
    return ManifestProblem(code=code, field=field, detail=detail, component_id=component_id)


def _is_relative_posix(value: str) -> bool:
    if not value or value.startswith(("/", "\\")):
        return False
    if re.match(r"^[A-Za-z]:", value):
        return False
    parts = re.split(r"[\\/]+", value)
    return not any(p in ("..",) for p in parts if p)


@dataclass
class ComponentManifest:
    """One validated component declaration."""

    component_id: str
    name: str
    version: str
    source_revision: str
    code_location: str
    runtime: str
    entry_point: str
    supported_commands: tuple[str, ...]
    environment_allowlist: tuple[str, ...]
    data_roots: dict[str, str]
    read_write_policy: str
    input_schema: str | None = None
    output_schema: str | None = None
    health_probe: dict[str, Any] | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def code_path(self, deployment_root: str | os.PathLike) -> Path:
        return Path(deployment_root) / self.code_location

    def entry_path(self, deployment_root: str | os.PathLike) -> Path:
        return self.code_path(deployment_root) / self.entry_point

    def data_root_paths(self, deployment_root: str | os.PathLike) -> dict[str, str]:
        return {role: str(Path(deployment_root) / rel) for role, rel in self.data_roots.items()}

    def to_dict(self) -> dict[str, Any]:
        return {
            "component_id": self.component_id,
            "name": self.name,
            "version": self.version,
            "source_revision": self.source_revision,
            "code_location": self.code_location,
            "runtime": self.runtime,
            "entry_point": self.entry_point,
            "supported_commands": list(self.supported_commands),
            "environment_allowlist": list(self.environment_allowlist),
            "data_roots": dict(self.data_roots),
            "read_write_policy": self.read_write_policy,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "health_probe": self.health_probe,
        }


def _check_relative(problems: list[ManifestProblem], component_id: str, field: str, value: Any) -> None:
    if not isinstance(value, str) or not value:
        problems.append(_problem("wrong_type", field, "must be a non-empty string", component_id))
        return
    if not _is_relative_posix(value):
        problems.append(_problem(
            "not_relative_path", field,
            f"must be a relative path without '..' or a drive/root prefix: {value!r}", component_id))


def _check_rooted(problems: list[ManifestProblem], component_id: str, field: str,
                  value: Any, deployment_root: Path) -> None:
    if not isinstance(value, str) or not value:
        return
    if not _is_relative_posix(value):
        return  # already reported as not_relative_path
    resolved = Path(deployment_root) / value
    if not is_within(resolved, deployment_root):
        problems.append(_problem(
            "path_escapes_root", field,
            f"resolves outside the deployment root: {resolved}", component_id))


def parse_component(data: Any, *, deployment_root: str | os.PathLike,
                    index: int = 0, require_entry_point: bool = False
                    ) -> tuple[ComponentManifest | None, list[ManifestProblem]]:
    """Validate one component object; return the manifest and its problems.

    ``None`` is returned when a required field is missing or the wrong type
    (no best-effort object is invented). Semantic problems are reported on a
    returned manifest, which the loader then refuses to admit.
    """
    root = Path(os.path.abspath(str(deployment_root)))
    problems: list[ManifestProblem] = []
    if not isinstance(data, dict):
        return None, [_problem("wrong_type", "component", f"component #{index} is not an object")]

    raw_id = data.get("component_id")
    component_id = raw_id if isinstance(raw_id, str) and raw_id else None

    for name in REQUIRED_FIELDS:
        if name not in data:
            problems.append(_problem("missing_field", name, "required field is absent", component_id))
    if problems:
        return None, problems

    for name in ("component_id", "name", "version", "source_revision"):
        if not isinstance(data[name], str) or not data[name].strip():
            problems.append(_problem("wrong_type", name, "must be a non-empty string", component_id))

    if component_id is not None and not _ID_RE.match(component_id):
        problems.append(_problem("bad_identifier", "component_id",
                                 f"must match {_ID_RE.pattern}: {component_id!r}", component_id))

    _check_relative(problems, component_id, "code_location", data["code_location"])
    _check_rooted(problems, component_id, "code_location", data["code_location"], root)
    _check_relative(problems, component_id, "entry_point", data["entry_point"])

    runtime = data["runtime"]
    if runtime not in ALLOWED_RUNTIMES:
        problems.append(_problem("unknown_runtime", "runtime",
                                 f"must be one of {list(ALLOWED_RUNTIMES)}: {runtime!r}", component_id))

    commands = data["supported_commands"]
    if not isinstance(commands, list) or not commands:
        problems.append(_problem("empty", "supported_commands",
                                 "must be a non-empty list of command names", component_id))
        commands = []
    else:
        for cmd in commands:
            if not isinstance(cmd, str) or not _COMMAND_RE.match(cmd):
                problems.append(_problem("bad_command", "supported_commands",
                                         f"invalid command name: {cmd!r}", component_id))
        if len(set(commands)) != len(commands):
            problems.append(_problem("duplicate_command", "supported_commands",
                                     "command names must be unique", component_id))

    allowlist = data["environment_allowlist"]
    if not isinstance(allowlist, list):
        problems.append(_problem("wrong_type", "environment_allowlist",
                                 "must be a list of env var names", component_id))
        allowlist = []
    else:
        for name in allowlist:
            if not isinstance(name, str) or not _ENV_RE.match(name):
                problems.append(_problem("bad_env_name", "environment_allowlist",
                                         f"invalid env var name: {name!r}", component_id))

    data_roots = data["data_roots"]
    if not isinstance(data_roots, dict):
        problems.append(_problem("wrong_type", "data_roots",
                                 "must be an object of role -> relative path", component_id))
        data_roots = {}
    else:
        for role, rel in data_roots.items():
            if not isinstance(role, str) or not _ROLE_RE.match(role):
                problems.append(_problem("bad_role", "data_roots",
                                         f"invalid role name: {role!r}", component_id))
            _check_relative(problems, component_id, f"data_roots.{role}", rel)
            _check_rooted(problems, component_id, f"data_roots.{role}", rel, root)

    policy = data["read_write_policy"]
    if policy not in READ_WRITE_POLICIES:
        problems.append(_problem("unknown_policy", "read_write_policy",
                                 f"must be one of {list(READ_WRITE_POLICIES)}: {policy!r}",
                                 component_id))

    for field_name in ("input_schema", "output_schema"):
        value = data.get(field_name)
        if value is not None:
            _check_relative(problems, component_id, field_name, value)

    probe = data.get("health_probe")
    if probe is not None:
        if not isinstance(probe, dict) or "command" not in probe:
            problems.append(_problem("wrong_type", "health_probe",
                                     "must be an object with a 'command'", component_id))
        elif probe["command"] not in (commands or []):
            problems.append(_problem("health_probe_unknown_command", "health_probe.command",
                                     f"not in supported_commands: {probe['command']!r}", component_id))

    manifest = ComponentManifest(
        component_id=component_id or f"component_{index}",
        name=str(data.get("name", "")),
        version=str(data.get("version", "")),
        source_revision=str(data.get("source_revision", "")),
        code_location=str(data.get("code_location", "")),
        runtime=str(runtime),
        entry_point=str(data.get("entry_point", "")),
        supported_commands=tuple(commands or ()),
        environment_allowlist=tuple(allowlist or ()),
        data_roots={str(k): str(v) for k, v in (data_roots or {}).items()},
        read_write_policy=str(policy),
        input_schema=data.get("input_schema"),
        output_schema=data.get("output_schema"),
        health_probe=probe if isinstance(probe, dict) else None,
        raw=dict(data),
    )

    if require_entry_point and not problems:
        if not manifest.entry_path(root).is_file():
            problems.append(_problem("entry_point_missing", "entry_point",
                                     f"no such file: {manifest.entry_path(root)}", component_id))

    return manifest, problems


@dataclass
class ManifestSet:
    """The admitted components plus every problem found while loading."""

    manifest_path: str
    deployment_root: str
    components: dict[str, ComponentManifest] = field(default_factory=dict)
    problems: list[ManifestProblem] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def get(self, component_id: str) -> ComponentManifest | None:
        return self.components.get(component_id)

    def ids(self) -> list[str]:
        return sorted(self.components)

    def commands(self, component_id: str) -> tuple[str, ...]:
        manifest = self.components.get(component_id)
        return manifest.supported_commands if manifest else ()

    def allows(self, component_id: str, command: str) -> bool:
        manifest = self.components.get(component_id)
        return bool(manifest and command in manifest.supported_commands)

    def report(self) -> list[dict[str, Any]]:
        return [self.components[cid].to_dict() for cid in self.ids()]


def load_manifest_set(path: str | os.PathLike, *, deployment_root: str | os.PathLike | None = None,
                      require_entry_point: bool = False) -> ManifestSet:
    """Read and validate a manifest document; never raise on component problems."""
    root = Path(os.path.abspath(str(deployment_root))) if deployment_root is not None \
        else Path(os.path.abspath(str(STAGING_ROOT)))
    candidate = Path(path)
    if not candidate.is_file():
        raise ManifestError(f"manifest not found: {candidate}")
    try:
        payload = json.loads(candidate.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise ManifestError(f"manifest is not valid JSON: {candidate}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ManifestError(f"manifest must be a JSON object: {candidate}")
    version = payload.get("manifest_version")
    if version != MANIFEST_VERSION:
        raise ManifestError(
            f"unsupported manifest_version {version!r}; expected {MANIFEST_VERSION!r}")
    entries = payload.get("components")
    if not isinstance(entries, list) or not entries:
        raise ManifestError("manifest must list at least one component")

    result = ManifestSet(manifest_path=str(candidate), deployment_root=str(root))
    seen: dict[str, int] = {}
    for index, entry in enumerate(entries):
        manifest, problems = parse_component(
            entry, deployment_root=root, index=index, require_entry_point=require_entry_point)
        result.problems.extend(problems)
        if manifest is None:
            continue
        cid = manifest.component_id
        if cid in seen:
            result.problems.append(_problem(
                "duplicate_component_id", "component_id",
                f"already declared at index {seen[cid]}", cid))
            continue
        seen[cid] = index
        if problems:
            continue  # never admit a component with any problem
        result.components[cid] = manifest
    if result.problems:
        result.warnings.append(
            f"{len(result.problems)} manifest problem(s); only {len(result.components)} "
            f"component(s) admitted to the whitelist")
    return result


__all__ = [
    "MANIFEST_VERSION", "ALLOWED_RUNTIMES", "READ_WRITE_POLICIES", "REQUIRED_FIELDS",
    "ManifestError", "ManifestProblem", "ComponentManifest", "ManifestSet",
    "parse_component", "load_manifest_set",
]
