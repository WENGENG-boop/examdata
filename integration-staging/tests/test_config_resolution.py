"""A06 configuration resolution tests (plan 6.1-6.2).

Covers the fixed precedence (explicit > environment > file > manifest defaults >
built-in default), the legacy-alias handling, validation failures, path roles,
secret redaction in the settings report, and the guarantee that resolving a
configuration creates no directory while ``ensure_directories`` refuses to
create one outside the staging tree.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from examdata_integration.runtime import (
    ConfigConflictError,
    ConfigError,
    InvalidSettingError,
    UnknownSettingError,
    env_template,
    resolve_config,
)
from examdata_integration.runtime.paths import PathOutsideRootError
from examdata_integration.testing import runtime_support

STAGING = runtime_support.STAGING
WORKSPACE = STAGING.parent


def _write_config(directory: Path, payload: dict) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "config.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _norm(value: object) -> str:
    return os.path.normpath(os.path.abspath(str(value)))


# -- layers and precedence ----------------------------------------------------

def test_default_layer_values():
    cfg = resolve_config(env={})
    assert cfg.source("network_mode") == "default"
    assert cfg.get("network_mode") == "offline"
    assert cfg.get("frontend_port") == 5188
    assert cfg.get("ielts_max_concurrent") == 4
    assert os.path.isabs(cfg.get("data_dir"))


def test_environment_overrides_default():
    cfg = resolve_config(env={"EXAMDATA_NETWORK_MODE": "loopback"})
    assert cfg.get("network_mode") == "loopback"
    assert cfg.source("network_mode") == "environment"
    assert cfg.origins["network_mode"] == "env:EXAMDATA_NETWORK_MODE"


def test_explicit_overrides_environment():
    cfg = resolve_config(explicit={"frontend_port": 6000},
                         env={"FRONTEND_PORT": "7000"})
    assert cfg.get("frontend_port") == 6000
    assert cfg.source("frontend_port") == "explicit"


def test_full_precedence_order(tmp_path):
    config_file = _write_config(tmp_path, {"ielts_max_concurrent": 7})
    layers = dict(
        explicit={"ielts_max_concurrent": 9},
        env={"EXAMDATA_IELTS_MAX_CONCURRENT": "8"},
        config_file=config_file,
        manifest_defaults={"ielts_max_concurrent": 6},
    )
    assert resolve_config(**layers).get("ielts_max_concurrent") == 9

    without_explicit = dict(layers)
    without_explicit.pop("explicit")
    assert resolve_config(**without_explicit).get("ielts_max_concurrent") == 8

    without_env = dict(without_explicit)
    without_env.pop("env")
    assert resolve_config(**without_env).get("ielts_max_concurrent") == 7

    only_manifest = dict(without_env)
    only_manifest.pop("config_file")
    cfg = resolve_config(**only_manifest)
    assert cfg.get("ielts_max_concurrent") == 6
    assert cfg.source("ielts_max_concurrent") == "manifest_default"

    assert resolve_config(env={}).get("ielts_max_concurrent") == 4


def test_config_file_layer(tmp_path):
    path = _write_config(tmp_path, {"network_mode": "loopback",
                                    "component_manifest": "components/manifest.json"})
    cfg = resolve_config(env={}, config_file=path)
    assert cfg.get("network_mode") == "loopback"
    assert cfg.source("network_mode") == "config_file"
    assert cfg.get("component_manifest").endswith(os.path.join("components", "manifest.json"))


# -- validation failures ------------------------------------------------------

def test_unknown_explicit_key_rejected():
    with pytest.raises(UnknownSettingError):
        resolve_config(explicit={"no_such_setting": 1}, env={})


def test_unknown_manifest_default_key_rejected():
    with pytest.raises(UnknownSettingError):
        resolve_config(env={}, manifest_defaults={"no_such_setting": 1})


def test_unknown_config_file_key_rejected(tmp_path):
    path = _write_config(tmp_path, {"no_such_setting": 1})
    with pytest.raises(UnknownSettingError):
        resolve_config(env={}, config_file=path)


def test_config_file_not_found(tmp_path):
    with pytest.raises(ConfigError):
        resolve_config(env={}, config_file=tmp_path / "absent.json")


def test_config_file_outside_staging_refused():
    outside = WORKSPACE / "docs" / "README.md"
    assert outside.is_file(), "test premise: an existing file outside staging"
    with pytest.raises(PathOutsideRootError):
        resolve_config(env={}, config_file=outside)


def test_conflicting_alias_values_rejected():
    env = {
        "IELTS_API_DIR": str(STAGING / "runtime" / "data" / "ielts"),
        "EXAMDATA_IELTS_DIR": str(STAGING / "runtime" / "data" / "ielts2"),
    }
    with pytest.raises(ConfigConflictError):
        resolve_config(env=env)


def test_invalid_int_rejected():
    with pytest.raises(InvalidSettingError):
        resolve_config(env={"EXAMDATA_IELTS_MAX_CONCURRENT": "not-a-number"})


def test_invalid_enum_rejected():
    with pytest.raises(InvalidSettingError):
        resolve_config(env={"EXAMDATA_NETWORK_MODE": "turbo"})


def test_invalid_url_rejected():
    with pytest.raises(InvalidSettingError):
        resolve_config(env={"EXAMDATA_URL": "ftp://example.invalid"})


# -- aliases ------------------------------------------------------------------

def test_legacy_alias_still_works_with_warning():
    target = STAGING / "runtime" / "data" / "ielts"
    cfg = resolve_config(env={"IELTS_API_DIR": str(target)})
    assert cfg.get("ielts_dir") == _norm(target)
    assert cfg.origins["ielts_dir"] == "env:IELTS_API_DIR"
    assert any("deprecated alias" in w for w in cfg.warnings)


def test_duplicate_alias_same_value_only_warns():
    target = str(STAGING / "runtime" / "data" / "ielts")
    cfg = resolve_config(env={"IELTS_API_DIR": target, "EXAMDATA_IELTS_DIR": target})
    assert cfg.get("ielts_dir") == _norm(target)
    assert any("legacy alias" in w for w in cfg.warnings)


# -- roles, secrets, new settings --------------------------------------------

def test_path_setting_is_absolute_and_role_recorded(tmp_path):
    cfg = resolve_config(env={"EXAMDATA_CIE_INDEX_ROOT": str(tmp_path / "cie")})
    assert os.path.isabs(cfg.get("cie_index_root"))
    assert cfg.roles["cie_index_root"] == "data_root"
    assert cfg.roles["api_key"] == "secret"


def test_new_phase_a_settings_defaults_and_roles():
    cfg = resolve_config(env={})
    assert cfg.get("network_mode") == "offline"
    assert cfg.roles["network_mode"] == "network"
    assert cfg.get("runner_output_budget") == 4 * 1024 * 1024
    assert cfg.roles["runner_output_budget"] == "limit"
    assert cfg.roles["component_manifest"] == "manifest"
    assert cfg.get("component_manifest") is None


def test_settings_report_redacts_secret():
    secret = "s3cr3t-value-do-not-leak"
    cfg = resolve_config(explicit={"api_key": secret}, env={})
    report = cfg.settings_report()
    rows = {row["key"]: row for row in report}
    assert rows["api_key"]["value"] == "set"
    assert secret not in json.dumps(report)

    cfg_unset = resolve_config(env={})
    rows_unset = {row["key"]: row for row in cfg_unset.settings_report()}
    assert rows_unset["api_key"]["value"] == "unset"
    assert rows_unset["network_mode"]["new_in_phase_a"] is True


# -- directory creation -------------------------------------------------------

def test_resolve_creates_no_directory(tmp_path):
    sentinel = tmp_path / "not-created" / "catalog"
    resolve_config(env={"EXAMDATA_CATALOG_ROOT": str(sentinel)})
    assert not sentinel.exists()


def test_ensure_directories_creates_inside_staging(tmp_path):
    data_dir = tmp_path / "data"
    catalog = tmp_path / "catalog"
    cfg = resolve_config(explicit={"data_dir": str(data_dir), "catalog_root": str(catalog)},
                         env={})
    created = cfg.ensure_directories()
    assert str(data_dir) in created and data_dir.is_dir()
    assert str(catalog) in created and catalog.is_dir()


def test_ensure_directories_refuses_outside_staging(tmp_path):
    outside = WORKSPACE / "docs" / "a06-should-not-create"
    cfg = resolve_config(explicit={"data_dir": str(tmp_path / "data"),
                                   "catalog_root": str(outside)}, env={})
    with pytest.raises(ConfigError):
        cfg.ensure_directories()
    assert not outside.exists()


# -- template -----------------------------------------------------------------

def test_env_template_covers_every_setting():
    template = env_template()
    for token in ("EXAMDATA_NETWORK_MODE", "EXAMDATA_COMPONENT_MANIFEST",
                  "EXAMDATA_RUNNER_OUTPUT_BUDGET", "EXAMDATA_API_KEY",
                  "new in Phase A", "IELTS_API_DIR -> EXAMDATA_IELTS_DIR"):
        assert token in template
