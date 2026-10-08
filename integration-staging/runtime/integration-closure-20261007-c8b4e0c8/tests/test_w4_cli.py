"""W4a — the isolated Phase A CLI (``examdata.cli``).

The brief (W4 part A.2) asks for the product surface - status, configuration,
diagnostics, catalog, migration - to be reachable through a real CLI entry
point with a JSON stdout contract: exactly one envelope per run, exit codes
0/1/2, a sanitized error instead of a traceback, and no writes anywhere.

Every check here runs the CLI in-process through ``app(argv)`` and parses the
one JSON line it writes; one subprocess check proves the ``examdata.cli``
module entry point resolves from a foreign working directory (with a space
and non-ASCII in its name) while the test-only
``EXAMDATA_INTEGRATION_STAGING_ROOT`` carries a bogus sentinel - the product
CLI must never read that name.

On the frozen parent (no ``src/examdata/cli.py``) each test fails through the
lazy module accessor instead of erroring at collection.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import pytest

import b07r2_common as c  # import first: pins EXAMDATA_INTEGRATION_ROOT + candidate origin

RUN_ROOT = c.CANDIDATE_ROOT.parents[1]
ENVELOPE_KEYS = ["command", "ok", "problems", "result", "root", "schema", "warnings"]
STAGING_ENV = "EXAMDATA_INTEGRATION_ROOT"
BOGUS_TEST_ENV = "EXAMDATA_INTEGRATION_STAGING_ROOT"
BOGUS_SENTINEL = "C:/bogus/w4a-staging-sentinel-must-be-ignored"


def _cli() -> Any:
    try:
        import examdata.cli as cli
    except Exception as exc:  # pragma: no cover - RED on the frozen parent
        pytest.fail(f"examdata.cli is not implemented on this revision: "
                    f"{type(exc).__name__}: {exc}")
    return cli


def _run_json(argv: Sequence[str], *, root: Path | None = c.CANDIDATE_ROOT
              ) -> tuple[int, dict[str, Any]]:
    """Run one invocation in-process; return (exit code, envelope)."""
    module = _cli()
    args = list(argv)
    if root is not None and "--root" not in args:
        args = ["--root", str(root), *args]
    stream = io.StringIO()
    with contextlib.redirect_stdout(stream):
        code = module.app(args)
    text = stream.getvalue()
    assert text.endswith("\n"), f"stdout must end with one newline: {text!r}"
    assert text.count("\n") == 1, f"stdout must carry exactly one JSON line: {text!r}"
    payload = json.loads(text)
    assert isinstance(payload, dict)
    assert sorted(payload) == ENVELOPE_KEYS, sorted(payload)
    assert payload["schema"] == "examdata.cli/1"
    assert isinstance(payload["ok"], bool)
    return code, payload


@pytest.fixture(autouse=True)
def _restore_root_env():
    """An explicit ``--root`` is synced into the process env; restore it."""
    saved = os.environ.get(STAGING_ENV)
    yield
    if saved is None:
        os.environ.pop(STAGING_ENV, None)
    else:
        os.environ[STAGING_ENV] = saved


def _candidate_root(payload: dict[str, Any]) -> Path:
    assert payload["root"] is not None
    return Path(payload["root"])


def _check_rows(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["name"]: row for row in payload["result"]["checks"]}


# --------------------------------------------------------------------------- #
# status
# --------------------------------------------------------------------------- #
def test_status_reports_mode_root_dataset_and_baseline() -> None:
    code, payload = _run_json(["status"])
    assert code == 0 and payload["ok"] is True
    assert payload["problems"] == []
    assert _candidate_root(payload) == c.CANDIDATE_ROOT
    result = payload["result"]
    assert result["mode"] == "PHASE_A_ISOLATED_ONLY"
    assert result["root_exists"] is True
    assert result["version"] == "0.0.0-phasea"
    dataset = result["dataset"]
    assert dataset["evidence"] == "synthetic_fixture"
    assert dataset["revision"].startswith("rev-")
    assert len(dataset["revision"]) == len("rev-") + 32
    assert dataset["entries"] == dataset["counts"]["total"]
    assert dataset["entries"] > 0
    baseline = result["legacy_baseline"]
    assert baseline["rows"] == 71
    assert len(baseline["registry_sha256"]) == 64
    assert baseline["by_status"]["deferred_active_owner"] == 7


def test_status_reports_a_missing_root_as_a_problem() -> None:
    missing = c.CANDIDATE_ROOT.parent / "w4a-there-is-no-deployment-here"
    code, payload = _run_json(["status"], root=missing)
    assert code == 1 and payload["ok"] is False
    assert payload["problems"][0]["code"] == "root_missing"
    assert payload["result"]["root_exists"] is False
    assert "dataset" not in payload["result"]


# --------------------------------------------------------------------------- #
# configuration
# --------------------------------------------------------------------------- #
def test_configuration_template_is_static_and_needs_no_root() -> None:
    from examdata.integration.runtime.settings import SETTING_SPECS

    code, payload = _run_json(["configuration", "template"], root=None)
    assert code == 0 and payload["ok"] is True
    assert payload["root"] is None
    rows = payload["result"]["settings"]
    assert len(rows) == len(SETTING_SPECS) >= 20
    by_key = {row["key"]: row for row in rows}
    assert by_key["api_key"]["secret"] is True
    assert by_key["api_key"]["default"] is None
    assert by_key["api_key"]["kind"] == "secret"
    assert by_key["operations_root"]["env"] == "EXAMDATA_OPERATIONS_ROOT"
    assert by_key["component_manifest"]["new_in_phase_a"] is True
    assert payload["result"]["writes"] == []
    template = payload["result"]["template"]
    assert "EXAMDATA_API_KEY" in template and "EXAMDATA_OPERATIONS_ROOT" in template
    assert "IELTS_API_DIR -> EXAMDATA_IELTS_DIR" in template


def test_configuration_show_reports_secret_free_settings(
        monkeypatch: pytest.MonkeyPatch) -> None:
    code, payload = _run_json(["configuration", "show"])
    assert code == 0 and payload["ok"] is True
    assert _candidate_root(payload) == c.CANDIDATE_ROOT
    result = payload["result"]
    assert Path(result["deployment_root"]) == c.CANDIDATE_ROOT
    assert result["config_file"] is None
    assert result["writes"] == []
    rows = {row["key"]: row for row in result["settings"]}
    assert rows["api_key"]["value"] in {"set", "unset"}
    assert rows["network_mode"]["value"] == "offline"
    assert rows["api_key"]["source"] == "default"

    # The rows may say a setting *is* a secret; with a real secret configured
    # the rendered value must stay "set" and the secret itself must never
    # appear anywhere in the serialized report.
    secret = "REDACTED_LOCAL_CREDENTIAL"
    monkeypatch.setenv("EXAMDATA_API_KEY", secret)
    code, payload = _run_json(["configuration", "show"])
    assert code == 0 and payload["ok"] is True
    rows = {row["key"]: row for row in payload["result"]["settings"]}
    assert rows["api_key"]["value"] == "set"
    rendered = json.dumps(payload).lower()
    assert secret.lower() not in rendered
    for fragment in ("report-check-7c31ab90", "7c31ab90d2e4f5a6"):
        assert fragment not in rendered


def test_configuration_show_never_renders_a_secret_value(
        monkeypatch: pytest.MonkeyPatch) -> None:
    secret = "REDACTED_LOCAL_CREDENTIAL"
    monkeypatch.setenv("EXAMDATA_API_KEY", secret)
    code, payload = _run_json(["configuration", "show"])
    assert code == 0
    rows = {row["key"]: row for row in payload["result"]["settings"]}
    assert rows["api_key"]["value"] == "set"
    assert secret not in json.dumps(payload)


def test_configuration_check_reports_offline_and_paths() -> None:
    code, payload = _run_json(["configuration", "check"])
    assert code == 0 and payload["ok"] is True
    checks = _check_rows(payload)
    assert checks["network_mode_offline"]["ok"] is True
    assert checks["network_mode_offline"]["observed"] == "offline"
    assert isinstance(payload["result"]["paths"], list)
    assert payload["result"]["writes"] == []


def test_configuration_check_fails_closed_when_not_offline(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXAMDATA_NETWORK_MODE", "upstream")
    code, payload = _run_json(["configuration", "check"])
    assert code == 1 and payload["ok"] is False
    assert [p["code"] for p in payload["problems"]] == ["network_mode_not_offline"]
    assert _check_rows(payload)["network_mode_offline"]["ok"] is False


# --------------------------------------------------------------------------- #
# catalog
# --------------------------------------------------------------------------- #
def test_catalog_build_is_reproducible_and_writes_nothing() -> None:
    code, payload = _run_json(["catalog", "build"])
    assert code == 0 and payload["ok"] is True
    result = payload["result"]
    assert result["writes"] == []
    assert result["source_policy"] == "fixture_providers (labelled synthetic fixtures)"
    assert result["matches_current"] is True
    assert result["candidate_revision"] == result["current_revision"]
    assert result["counts"]["total"] > 0
    assert result["diff"]["counts"] == {"added": 0, "removed": 0,
                                        "changed": 0, "quality_upgrades": 0}


def test_catalog_stats_projects_kinds_systems_and_problems() -> None:
    code, payload = _run_json(["catalog", "stats"])
    assert code == 0 and payload["ok"] is True
    result = payload["result"]
    assert result["entries"] == result["counts"]["total"] > 0
    assert sum(result["by_kind"].values()) == result["entries"]
    assert set(result["by_system"]) >= {"cie", "edexcel", "ielts"}
    assert result["revision"].startswith("rev-")
    assert result["input_revisions"] == {"fixtures": "a10-synthetic-providers",
                                         "parser": "catalog-source/1"}
    # The fixture legitimately carries informational identity_unresolved rows:
    # they stay visible in the result and never fail the command.
    assert isinstance(result["snapshot_problems"], list)
    assert all(problem["code"] == "identity_unresolved"
               for problem in result["snapshot_problems"])
    assert result["writes"] == []


def test_catalog_verify_runs_every_self_check() -> None:
    code, payload = _run_json(["catalog", "verify"])
    assert code == 0 and payload["ok"] is True
    assert payload["problems"] == []
    checks = _check_rows(payload)
    assert set(checks) == {"revision_recomputes", "counts_match",
                           "public_ids_derivable",
                           "build_reproduces_current_revision",
                           "content_store_verifies"}
    assert all(check["ok"] is True for check in checks.values())
    assert checks["content_store_verifies"]["samples"] > 0
    assert checks["content_store_verifies"]["store_problems"] == []
    assert payload["result"]["revision"] == checks["revision_recomputes"]["observed"]
    assert payload["result"]["writes"] == []


# --------------------------------------------------------------------------- #
# diagnostics
# --------------------------------------------------------------------------- #
def test_diagnostics_doctor_plus_fixture_self_checks() -> None:
    code, payload = _run_json(["diagnostics"])
    assert code == 0 and payload["ok"] is True
    result = payload["result"]
    report = result["report"]
    assert report["schema"] == "examdata.doctor/1"
    assert report["mode"] == "PHASE_A_ISOLATED_ONLY"
    assert report["network"]["compliant"] is True
    assert report["creates_directories"] is False
    assert result["writes"] == []
    checks = _check_rows(payload)
    assert checks["dataset_builds"]["ok"] is True
    assert checks["dataset_revision_recomputes"]["ok"] is True
    assert checks["content_store_verifies"]["ok"] is True


def test_diagnostics_fails_closed_when_not_offline(
        monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXAMDATA_NETWORK_MODE", "upstream")
    code, payload = _run_json(["diagnostics"])
    assert code == 1 and payload["ok"] is False
    codes = [problem["code"] for problem in payload["problems"]]
    assert "network_mode_not_offline" in codes
    assert payload["result"]["report"]["network"]["compliant"] is False


# --------------------------------------------------------------------------- #
# migrate
# --------------------------------------------------------------------------- #
def test_migrate_plan_projects_the_registry_rows() -> None:
    code, payload = _run_json(["migrate", "plan"])
    assert code == 0 and payload["ok"] is True
    result = payload["result"]
    assert result["writes"] == []
    assert result["row_count"] == 71 == result["summary"]["baseline_rows"]
    row = result["rows"][0]
    assert sorted(row) == ["coverage_kind", "deferred_reason", "legacy_path",
                           "mechanism", "method", "row_id", "status", "v2_target"]
    assert all(item["row_id"] for item in result["rows"])
    assert result["summary"]["by_status"] == {"staged_pass": 64,
                                              "deferred_active_owner": 7}


def test_migrate_check_agrees_with_status_on_the_registry_sha() -> None:
    status_code, status = _run_json(["status"])
    assert status_code == 0
    code, payload = _run_json(["migrate", "check"])
    assert code == 0 and payload["ok"] is True
    result = payload["result"]
    assert result["writes"] == []
    assert result["rows"] == 71
    assert result["registry_sha256"] == result["file_sha256"]
    assert result["registry_sha256"] == status["result"]["legacy_baseline"]["registry_sha256"]
    checks = _check_rows(payload)
    assert checks["schema_matches"]["ok"] is True
    assert checks["sha256_matches_registry"]["ok"] is True


# --------------------------------------------------------------------------- #
# error handling, exit codes and argument placement
# --------------------------------------------------------------------------- #
def test_unknown_command_is_a_usage_error_with_empty_stdout() -> None:
    module = _cli()
    stream = io.StringIO()
    with contextlib.redirect_stdout(stream), pytest.raises(SystemExit) as excinfo:
        module.app(["bogus"])
    assert excinfo.value.code == 2
    assert stream.getvalue() == ""


def test_missing_subcommand_is_a_usage_error() -> None:
    module = _cli()
    with pytest.raises(SystemExit) as excinfo:
        module.app(["catalog"])
    assert excinfo.value.code == 2


def test_errors_become_one_sanitized_envelope_not_a_traceback() -> None:
    missing = c.CANDIDATE_ROOT / "w4a-no-such-config.json"
    code, payload = _run_json(["configuration", "show", "--config-file", str(missing)])
    assert code == 1 and payload["ok"] is False
    assert payload["result"] is None
    assert len(payload["problems"]) == 1
    problem = payload["problems"][0]
    assert problem["code"] == "cli_error"
    assert "ConfigError" in problem["detail"]
    assert str(c.CANDIDATE_ROOT) not in problem["detail"]
    assert "Traceback" not in problem["detail"]


def test_root_and_json_flags_work_before_and_after_the_subcommand() -> None:
    module = _cli()
    before_code, before = _run_json(["--json", "--root", str(c.CANDIDATE_ROOT), "status"])
    after_code, after = _run_json(["status", "--json"], root=None)
    assert before_code == after_code == 0
    assert before["root"] == after["root"]
    assert before["command"] == after["command"] == "status"


# --------------------------------------------------------------------------- #
# the real entry point: a subprocess from a foreign working directory
# --------------------------------------------------------------------------- #
def test_module_entry_point_from_foreign_cwd_ignores_test_env() -> None:
    _cli()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    cwd = RUN_ROOT / "tmp" / f"w4a-cli-cwd-{stamp}-{os.getpid()}" / "deploy root – ünïcode"
    cwd.mkdir(parents=True, exist_ok=True)

    env = dict(os.environ)
    env["PYTHONPATH"] = str(c.CANDIDATE_ROOT / "src")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env[STAGING_ENV] = str(c.CANDIDATE_ROOT)
    env[BOGUS_TEST_ENV] = BOGUS_SENTINEL  # the product CLI must never read this
    env.pop("EXAMDATA_OPERATIONS_ROOT", None)
    env.pop("B07R2_EXPECT_CANDIDATE_ROOT", None)

    completed = subprocess.run(
        [sys.executable, "-B", "-m", "examdata.cli", "status"],
        cwd=str(cwd), env=env, capture_output=True, timeout=240)
    assert completed.returncode == 0, completed.stderr.decode("utf-8", "replace")
    text = completed.stdout.decode("utf-8")
    lines = [line for line in text.splitlines() if line.strip()]
    assert len(lines) == 1, text
    payload = json.loads(lines[0])
    assert payload["ok"] is True
    assert Path(payload["root"]) == c.CANDIDATE_ROOT
    assert BOGUS_SENTINEL not in text
    assert payload["result"]["dataset"]["entries"] > 0
    assert b"Traceback" not in completed.stderr
