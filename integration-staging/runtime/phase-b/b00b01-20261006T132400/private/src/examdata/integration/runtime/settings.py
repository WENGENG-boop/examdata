"""Resolved configuration (plan 6.1, 6.2, A06).

One resolved configuration object, built once, from four layers in a fixed
precedence::

    explicit allowed command argument
      > process environment
      > explicitly selected configuration file
      > deployment component manifest defaults
      > built-in default

Rules this module enforces:

* every path setting is resolved once to an absolute path and carries its role;
* the process environment is never mutated (child processes get a copy);
* a value that two env names carry with *different* values is a clear
  :class:`ConfigConflictError`, never a silent directory choice;
* a legacy alias still works but produces a deprecation warning;
* parsing is separated from directory creation: resolving a configuration, or
  importing this module, creates nothing (see :meth:`ResolvedConfig.ensure_directories`);
* secrets are never rendered by :meth:`ResolvedConfig.settings_report`.

New settings are read here *and* covered by precedence tests before they are
documented as usable (plan 6.2).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

from ..testing.guards import STAGING_ROOT, is_within


class ConfigError(ValueError):
    """Base class for configuration problems."""


class ConfigConflictError(ConfigError):
    """Two env names carry different values for the same setting."""


class UnknownSettingError(ConfigError):
    """An explicit/config-file/manifest key is not a known setting."""


class InvalidSettingError(ConfigError):
    """A value cannot be coerced to its declared kind."""


class _StrEnum(str, Enum):
    def __str__(self) -> str:  # pragma: no cover - convenience only
        return self.value


class SettingKind(_StrEnum):
    STRING = "string"
    INT = "int"
    FLOAT = "float"
    BOOL = "bool"
    PATH = "path"
    URL = "url"
    SECRET = "secret"
    ENUM = "enum"


class ConfigLayer(_StrEnum):
    DEFAULT = "default"
    MANIFEST = "manifest_default"
    FILE = "config_file"
    ENVIRONMENT = "environment"
    EXPLICIT = "explicit"


LAYER_RANK: dict[ConfigLayer, int] = {
    ConfigLayer.DEFAULT: 0,
    ConfigLayer.MANIFEST: 1,
    ConfigLayer.FILE: 2,
    ConfigLayer.ENVIRONMENT: 3,
    ConfigLayer.EXPLICIT: 4,
}

#: Layers whose values may be coerced from strings (env and files are text).
_TEXT_LAYERS = (ConfigLayer.ENVIRONMENT, ConfigLayer.FILE, ConfigLayer.MANIFEST)


@dataclass(frozen=True)
class SettingSpec:
    """One canonical setting: env name, kind, role and defaults."""

    key: str
    env: str
    kind: SettingKind
    role: str
    default: Any = None
    aliases: tuple[str, ...] = ()
    legacy_aliases: tuple[str, ...] = ()
    choices: tuple[str, ...] = ()
    new_in_phase_a: bool = False

    @property
    def secret(self) -> bool:
        return self.kind is SettingKind.SECRET

    def env_names(self) -> tuple[str, ...]:
        return (self.env,) + self.aliases + self.legacy_aliases


#: Canonical settings, in report order (plan 6.2: preserve the existing settings,
#: add the proposed ones as read-only until proven).
SETTING_SPECS: tuple[SettingSpec, ...] = (
    SettingSpec("data_dir", "EXAMDATA_DATA_DIR", SettingKind.PATH, "data_root", ".data"),
    SettingSpec("database_url", "EXAMDATA_DATABASE_URL", SettingKind.STRING, "database",
                "sqlite:///.data/examdata.db"),
    SettingSpec("node_executable", "EXAMDATA_NODE", SettingKind.PATH, "runtime", None),
    SettingSpec("ielts_dir", "EXAMDATA_IELTS_DIR", SettingKind.PATH, "component_data", None,
                legacy_aliases=("IELTS_API_DIR",)),
    SettingSpec("ielts_max_concurrent", "EXAMDATA_IELTS_MAX_CONCURRENT", SettingKind.INT, "limit", 4),
    SettingSpec("ielts_queue_timeout", "EXAMDATA_IELTS_QUEUE_TIMEOUT", SettingKind.FLOAT, "limit", 5.0),
    SettingSpec("ielts_timeout", "EXAMDATA_IELTS_TIMEOUT", SettingKind.FLOAT, "limit", 120.0),
    SettingSpec("toefl_dir", "EXAMDATA_TOEFL_DIR", SettingKind.PATH, "component_data", None,
                legacy_aliases=("TOEFL_API_DIR",)),
    SettingSpec("toefl_max_concurrent", "EXAMDATA_TOEFL_MAX_CONCURRENT", SettingKind.INT, "limit", 4),
    SettingSpec("toefl_queue_timeout", "EXAMDATA_TOEFL_QUEUE_TIMEOUT", SettingKind.FLOAT, "limit", 5.0),
    SettingSpec("toefl_timeout", "EXAMDATA_TOEFL_TIMEOUT", SettingKind.FLOAT, "limit", 120.0),
    SettingSpec("api_key", "EXAMDATA_API_KEY", SettingKind.SECRET, "secret", None),
    SettingSpec("cors_origins", "EXAMDATA_CORS_ORIGINS", SettingKind.STRING, "security", None),
    SettingSpec("frontend_upstream", "EXAMDATA_URL", SettingKind.URL, "frontend",
                "http://127.0.0.1:8000"),
    SettingSpec("frontend_port", "FRONTEND_PORT", SettingKind.INT, "frontend", 5188),
    SettingSpec("component_manifest", "EXAMDATA_COMPONENT_MANIFEST", SettingKind.PATH, "manifest",
                None, new_in_phase_a=True),
    SettingSpec("cie_index_root", "EXAMDATA_CIE_INDEX_ROOT", SettingKind.PATH, "data_root",
                None, new_in_phase_a=True),
    SettingSpec("toefl_data_root", "EXAMDATA_TOEFL_DATA_ROOT", SettingKind.PATH, "data_root",
                None, new_in_phase_a=True),
    SettingSpec("catalog_root", "EXAMDATA_CATALOG_ROOT", SettingKind.PATH, "data_root",
                None, new_in_phase_a=True),
    SettingSpec("operations_root", "EXAMDATA_OPERATIONS_ROOT", SettingKind.PATH, "operations",
                None, new_in_phase_a=True),
    SettingSpec("network_mode", "EXAMDATA_NETWORK_MODE", SettingKind.ENUM, "network", "offline",
                choices=("offline", "loopback", "upstream"), new_in_phase_a=True),
    SettingSpec("runner_output_budget", "EXAMDATA_RUNNER_OUTPUT_BUDGET", SettingKind.INT, "limit",
                4 * 1024 * 1024, new_in_phase_a=True),
    SettingSpec("crop_budget", "EXAMDATA_CROP_BUDGET", SettingKind.INT, "limit", None,
                new_in_phase_a=True),
    SettingSpec("total_response_budget", "EXAMDATA_TOTAL_RESPONSE_BUDGET", SettingKind.INT, "limit",
                32 * 1024 * 1024, new_in_phase_a=True),
)

SPEC_BY_KEY: dict[str, SettingSpec] = {s.key: s for s in SETTING_SPECS}
#: env name -> canonical key, for every name including aliases.
KEY_BY_ENV: dict[str, str] = {name: s.key for s in SETTING_SPECS for name in s.env_names()}

#: Roles whose directories ``ensure_directories`` may create.
DIRECTORY_ROLES: frozenset[str] = frozenset({"data_root", "component_data", "catalog", "operations"})

_TRUTHY = {"1", "true", "yes", "on"}
_FALSY = {"0", "false", "no", "off"}


def _coerce(spec: SettingSpec, value: Any, origin: str) -> Any:
    if isinstance(value, str):
        value = value.strip()
    try:
        if spec.kind is SettingKind.STRING or spec.kind is SettingKind.SECRET:
            return str(value)
        if spec.kind is SettingKind.INT:
            return int(value)
        if spec.kind is SettingKind.FLOAT:
            return float(value)
        if spec.kind is SettingKind.BOOL:
            if isinstance(value, bool):
                return value
            low = str(value).lower()
            if low in _TRUTHY:
                return True
            if low in _FALSY:
                return False
            raise ValueError(f"not a boolean: {value!r}")
        if spec.kind is SettingKind.PATH:
            return os.path.normpath(os.path.abspath(os.path.expanduser(str(value))))
        if spec.kind is SettingKind.URL:
            text = str(value)
            if not (text.startswith("http://") or text.startswith("https://")):
                raise ValueError(f"not an http(s) URL: {text!r}")
            return text
        if spec.kind is SettingKind.ENUM:
            text = str(value)
            if spec.choices and text not in spec.choices:
                raise ValueError(f"not one of {list(spec.choices)}: {text!r}")
            return text
    except (TypeError, ValueError) as exc:
        raise InvalidSettingError(
            f"{spec.key} ({origin}) is not a valid {spec.kind.value}: {exc}") from exc
    raise InvalidSettingError(f"{spec.key} ({origin}) has no coercion for {spec.kind}")


@dataclass
class ResolvedConfig:
    """A single resolved configuration: values, provenance and roles."""

    values: dict[str, Any] = field(default_factory=dict)
    sources: dict[str, str] = field(default_factory=dict)
    origins: dict[str, str] = field(default_factory=dict)
    roles: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    deployment_root: str = ""
    config_file: str | None = None

    def get(self, key: str, default: Any = None) -> Any:
        return self.values.get(key, default)

    def __getitem__(self, key: str) -> Any:
        return self.values[key]

    def source(self, key: str) -> str | None:
        return self.sources.get(key)

    def origin(self, key: str) -> str | None:
        return self.origins.get(key)

    def role(self, key: str) -> str | None:
        return self.roles.get(key)

    def path(self, key: str) -> str | None:
        value = self.values.get(key)
        return value if isinstance(value, str) else None

    def is_secret(self, key: str) -> bool:
        spec = SPEC_BY_KEY.get(key)
        return bool(spec and spec.secret)

    def settings_report(self) -> list[dict[str, Any]]:
        """Ordered, secret-free rendering of every canonical setting."""
        rows: list[dict[str, Any]] = []
        for spec in SETTING_SPECS:
            value = self.values.get(spec.key)
            if spec.secret:
                shown: Any = "set" if value else "unset"
            else:
                shown = value
            rows.append({
                "key": spec.key,
                "env": spec.env,
                "kind": spec.kind.value,
                "role": spec.role,
                "value": shown,
                "source": self.sources.get(spec.key),
                "origin": self.origins.get(spec.key),
                "new_in_phase_a": spec.new_in_phase_a,
            })
        return rows

    def ensure_directories(self, *, allow_outside_staging: bool = False) -> list[str]:
        """Create the configured directories. Explicit only — never called on import.

        Phase A refuses to create a directory outside the staging tree unless the
        caller explicitly opts in, so a default configuration cannot silently
        create ``.data`` in the process working directory.
        """
        created: list[str] = []
        for spec in SETTING_SPECS:
            if spec.kind is not SettingKind.PATH or spec.role not in DIRECTORY_ROLES:
                continue
            value = self.values.get(spec.key)
            if not value:
                continue
            target = Path(str(value))
            if not allow_outside_staging and not is_within(target, STAGING_ROOT):
                raise ConfigError(
                    f"refusing to create {spec.key} outside the staging tree: {target}")
            if not target.exists():
                target.mkdir(parents=True, exist_ok=True)
                created.append(str(target))
        return created


def _layer_value(spec: SettingSpec, layer: ConfigLayer, mapping: Mapping[str, Any] | None) -> Any:
    if not mapping or spec.key not in mapping:
        return None
    value = mapping[spec.key]
    if isinstance(value, str) and not value.strip():
        return None
    return value


def _env_candidates(spec: SettingSpec, env: Mapping[str, str]) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for name in spec.env_names():
        raw = env.get(name)
        if raw is None or str(raw).strip() == "":
            continue
        found.append((name, str(raw)))
    return found


def resolve_config(*, explicit: Mapping[str, Any] | None = None,
                   env: Mapping[str, str] | None = None,
                   config_file: str | os.PathLike | None = None,
                   manifest_defaults: Mapping[str, Any] | None = None,
                   deployment_root: str | os.PathLike | None = None,
                   allow_outside_staging: bool = False) -> ResolvedConfig:
    """Resolve the configuration once, by the plan's fixed precedence."""
    root = Path(os.path.abspath(str(deployment_root))) if deployment_root is not None \
        else Path(os.path.abspath(str(STAGING_ROOT)))
    environment: Mapping[str, str] = os.environ if env is None else env
    warnings: list[str] = []

    for name, mapping in (("explicit", explicit), ("manifest_defaults", manifest_defaults)):
        if mapping:
            unknown = sorted(k for k in mapping if k not in SPEC_BY_KEY)
            if unknown:
                raise UnknownSettingError(f"{name} names unknown settings: {unknown}")

    file_values: dict[str, Any] = {}
    file_path: str | None = None
    if config_file is not None:
        candidate = Path(config_file).expanduser()
        if not candidate.is_file():
            raise ConfigError(f"config file not found: {candidate}")
        if not allow_outside_staging:
            from ..testing.guards import ensure_staged_path
            candidate = ensure_staged_path(candidate, "config file")
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except ValueError as exc:
            raise ConfigError(f"config file is not valid JSON: {candidate}: {exc}") from exc
        if not isinstance(payload, dict):
            raise ConfigError(f"config file must contain a JSON object: {candidate}")
        unknown = sorted(k for k in payload if k not in SPEC_BY_KEY)
        if unknown:
            raise UnknownSettingError(f"config file names unknown settings: {unknown}")
        file_values = payload
        file_path = str(candidate)

    config = ResolvedConfig(deployment_root=str(root), config_file=file_path)

    for spec in SETTING_SPECS:
        value: Any = None
        layer = ConfigLayer.DEFAULT
        origin = "default"

        explicit_value = _layer_value(spec, ConfigLayer.EXPLICIT, explicit)
        file_value = _layer_value(spec, ConfigLayer.FILE, file_values)
        manifest_value = _layer_value(spec, ConfigLayer.MANIFEST, manifest_defaults)
        candidates = _env_candidates(spec, environment)

        if len(candidates) > 1:
            distinct = {v for _, v in candidates}
            if len(distinct) > 1:
                names = ", ".join(f"{n}={v!r}" for n, v in candidates)
                raise ConfigConflictError(
                    f"conflicting values for {spec.key}: {names}; "
                    f"set only one of {list(spec.env_names())}")
            warnings.append(
                f"{spec.key}: legacy alias(es) {[n for n, _ in candidates[1:]]} duplicate "
                f"{candidates[0][0]}; prefer {spec.env}")

        if explicit_value is not None:
            value, layer, origin = explicit_value, ConfigLayer.EXPLICIT, "explicit"
        elif candidates:
            name, raw = candidates[0]
            value = raw
            layer = ConfigLayer.ENVIRONMENT
            origin = f"env:{name}"
            if name in spec.legacy_aliases:
                warnings.append(
                    f"{spec.key}: {name} is a deprecated alias for {spec.env}; "
                    f"the alias still works but will be removed")
        elif file_value is not None:
            value, layer, origin = file_value, ConfigLayer.FILE, f"file:{file_path}"
        elif manifest_value is not None:
            value, layer, origin = manifest_value, ConfigLayer.MANIFEST, "manifest_default"
        else:
            value, layer, origin = spec.default, ConfigLayer.DEFAULT, "default"

        if value is None:
            config.values[spec.key] = None
            config.sources[spec.key] = layer.value
            config.origins[spec.key] = origin
            config.roles[spec.key] = spec.role
            continue

        text_layer = layer in _TEXT_LAYERS
        coerced = _coerce(spec, value, origin) if (text_layer or spec.kind is not SettingKind.STRING) \
            else value
        config.values[spec.key] = coerced
        config.sources[spec.key] = layer.value
        config.origins[spec.key] = origin
        config.roles[spec.key] = spec.role

    config.warnings = warnings
    return config


def env_template() -> str:
    """The staging env template shipped for the isolated harness (plan 6.2)."""
    lines = [
        "# Phase A staging environment template (integration-staging/config/).",
        "# Private roots only; nothing here points at the original tree, the live",
        "# database, or an upstream host. Copy to your own file and source it in a",
        "# private child process - never mutate the user environment.",
        "",
    ]
    for spec in SETTING_SPECS:
        if spec.secret:
            lines.append(f"# {spec.env}=            # secret; report only set/unset")
            continue
        default = "" if spec.default is None else str(spec.default)
        suffix = "  # new in Phase A" if spec.new_in_phase_a else ""
        lines.append(f"# {spec.env}={default}{suffix}")
    lines.append("")
    lines.append("# Aliases still honoured, with a deprecation warning:")
    for spec in SETTING_SPECS:
        for alias in spec.legacy_aliases:
            lines.append(f"#   {alias} -> {spec.env}")
    return "\n".join(lines) + "\n"


__all__ = [
    "ConfigError", "ConfigConflictError", "UnknownSettingError", "InvalidSettingError",
    "SettingKind", "ConfigLayer", "LAYER_RANK", "SettingSpec", "SETTING_SPECS",
    "SPEC_BY_KEY", "KEY_BY_ENV", "DIRECTORY_ROLES", "ResolvedConfig",
    "resolve_config", "env_template",
]
