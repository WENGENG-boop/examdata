"""Runtime, configuration and the controlled Node runner (plan 3.5, section 6, A06).

Staged implementation of:

* :mod:`.settings`  - the single resolved configuration and its precedence;
* :mod:`.manifest`  - component manifest validation and the command whitelist;
* :mod:`.runner`    - the bounded, classified child-process runner;
* :mod:`.doctor`    - read-only configuration/component diagnostics;
* :mod:`.redact`    - path/secret redaction for public error surfaces.

Nothing here reads the original tree, the network, or a database; the runner
only starts components whose entry point resolves inside the staging tree.
"""
from __future__ import annotations

from .classification import (
    ERROR_CODES,
    INFRASTRUCTURE_OUTCOMES,
    OUTCOME_PRECEDENCE,
    RETRYABLE_OUTCOMES,
    RunnerOutcome,
    error_code,
    error_object,
    is_business_failure,
    is_infrastructure_failure,
)
from .doctor import build_report, doctor_report
from .manifest import (
    ALLOWED_RUNTIMES,
    MANIFEST_VERSION,
    READ_WRITE_POLICIES,
    ComponentManifest,
    ManifestError,
    ManifestProblem,
    ManifestSet,
    load_manifest_set,
    parse_component,
)
from .redact import PATH_PLACEHOLDER, SECRET_PLACEHOLDER, contains_path, redact_text
from .runner import BASE_ENV_ALLOWLIST, NodeRunner, RunnerLimits, RunResult, parse_stdout
from .settings import (
    ConfigConflictError,
    ConfigError,
    ConfigLayer,
    InvalidSettingError,
    ResolvedConfig,
    SETTING_SPECS,
    SettingKind,
    SettingSpec,
    UnknownSettingError,
    env_template,
    resolve_config,
)

__all__ = [
    "RunnerOutcome", "OUTCOME_PRECEDENCE", "ERROR_CODES", "RETRYABLE_OUTCOMES",
    "INFRASTRUCTURE_OUTCOMES", "is_infrastructure_failure", "is_business_failure",
    "error_code", "error_object",
    "RunnerLimits", "RunResult", "NodeRunner", "parse_stdout", "BASE_ENV_ALLOWLIST",
    "ComponentManifest", "ManifestSet", "ManifestProblem", "ManifestError",
    "load_manifest_set", "parse_component", "MANIFEST_VERSION", "ALLOWED_RUNTIMES",
    "READ_WRITE_POLICIES",
    "ResolvedConfig", "SettingSpec", "SettingKind", "ConfigLayer", "SETTING_SPECS",
    "ConfigError", "ConfigConflictError", "UnknownSettingError", "InvalidSettingError",
    "resolve_config", "env_template",
    "doctor_report", "build_report",
    "redact_text", "contains_path", "PATH_PLACEHOLDER", "SECRET_PLACEHOLDER",
]
