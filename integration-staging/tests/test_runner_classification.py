"""A06 controlled runner classification tests (plan 6.4).

The twelve named failure modes from plan 11 plus the whitelist rejections and
the JSON parser. Real ``node`` subprocesses run the synthetic
``components/fake-node-cli`` fixture; nothing here touches the original tree.
"""
from __future__ import annotations

import threading
from pathlib import Path

import pytest

from examdata_integration.runtime import (
    ERROR_CODES,
    RunnerOutcome,
    load_manifest_set,
    parse_stdout,
)
from examdata_integration.runtime.redact import (
    PATH_PLACEHOLDER,
    SECRET_PLACEHOLDER,
)
from examdata_integration.testing import runtime_support

STAGING = runtime_support.STAGING
FAKE_SECRET = runtime_support.FAKE_SECRET
NODE = runtime_support.node_executable()

requires_node = pytest.mark.skipif(NODE is None, reason="node runtime not on PATH")


@pytest.fixture()
def manifests():
    return load_manifest_set(runtime_support.MANIFEST_PATH, deployment_root=STAGING)


# -- baseline -----------------------------------------------------------------

@requires_node
def test_ok_baseline(manifests):
    result = runtime_support.runner(manifests).run("fake_cli", "ok")
    assert result.outcome is RunnerOutcome.OK
    assert result.ok and not result.infrastructure_failure
    assert result.exit_code == 0
    assert result.error is None
    assert result.error_code == "ok"
    assert result.payload["cwd"] == str(runtime_support.FAKE_COMPONENT_DIR)


@requires_node
def test_argv_is_an_array_never_shell_interpolated(manifests):
    tricky = ["a b", "; rm -rf /", "$(whoami)", "a;b"]
    result = runtime_support.runner(manifests).run("fake_cli", "echo", tricky)
    assert result.ok
    assert result.payload["echo"] == tricky
    assert result.argv[3:] == tricky


# -- the twelve named failure modes -------------------------------------------

def test_missing_executable(manifests):
    runner = runtime_support.runner(manifests, runtime="definitely-not-a-real-runtime-xyz")
    result = runner.run("fake_cli", "ok")
    assert result.outcome is RunnerOutcome.MISSING_RUNTIME
    assert result.error_code == "runtime_missing"
    assert result.argv[0] == "definitely-not-a-real-runtime-xyz"


@requires_node
def test_spaces_in_paths(tmp_path, manifests):
    spaced = runtime_support.copy_fake_component(tmp_path / "space dir a06", "fake node cli")
    code_location = runtime_support.relative_to_staging(spaced)
    manifest_path = runtime_support.write_manifest(
        tmp_path, [runtime_support.component_spec(code_location=code_location)])
    spaced_set = load_manifest_set(manifest_path, deployment_root=STAGING)
    result = runtime_support.runner(spaced_set).run("fake_cli", "ok")
    assert result.ok, result.error
    assert "space dir a06" in result.payload["cwd"]
    assert result.payload["cwd"].endswith("fake node cli")


@requires_node
def test_invalid_json(manifests):
    result = runtime_support.runner(manifests).run("fake_cli", "bad-json")
    assert result.outcome is RunnerOutcome.INVALID_JSON
    assert result.error_code == "invalid_json"


@requires_node
def test_multiple_json_values(manifests):
    result = runtime_support.runner(manifests).run("fake_cli", "two-values")
    assert result.outcome is RunnerOutcome.MULTIPLE_JSON_VALUES
    assert result.error_code == "multiple_json_values"


@requires_node
def test_nonzero_exit(manifests):
    result = runtime_support.runner(manifests).run("fake_cli", "nonzero")
    assert result.outcome is RunnerOutcome.NONZERO_EXIT
    assert result.exit_code == 3
    assert result.error_code == "nonzero_exit"


@requires_node
def test_stderr_redaction(manifests):
    result = runtime_support.runner(manifests).run("fake_cli", "nonzero")
    text = result.stderr_text
    assert FAKE_SECRET not in text
    assert SECRET_PLACEHOLDER in text
    assert PATH_PLACEHOLDER in text
    assert "private" not in text


@requires_node
def test_noisy_command_is_ok_with_redacted_stderr(manifests):
    result = runtime_support.runner(manifests).run("fake_cli", "noisy")
    assert result.ok
    assert result.payload["note"] == "logs on stderr"
    assert FAKE_SECRET not in (result.stderr_text or "")
    assert SECRET_PLACEHOLDER in result.stderr_text


@requires_node
def test_queue_full(manifests):
    semaphore = threading.BoundedSemaphore(1)
    semaphore.acquire()
    runner = runtime_support.runner(
        manifests, limits=runtime_support.limits(queue_timeout=0.2, concurrency=1),
        semaphore=semaphore)
    try:
        result = runner.run("fake_cli", "ok")
    finally:
        semaphore.release()
    assert result.outcome is RunnerOutcome.QUEUE_FULL
    assert result.error_code == "queue_full"
    assert result.error["retryable"] is True


@requires_node
def test_output_overflow(manifests):
    runner = runtime_support.runner(manifests, limits=runtime_support.limits(stdout_bytes=8192))
    result = runner.run("fake_cli", "flood")
    assert result.outcome is RunnerOutcome.OUTPUT_OVERFLOW
    assert result.error_code == "output_overflow"
    assert result.stdout_truncated is True
    assert result.stdout_bytes > 8192


@requires_node
def test_timeout(manifests):
    runner = runtime_support.runner(manifests, limits=runtime_support.limits(process_timeout=0.6))
    result = runner.run("fake_cli", "slow")
    assert result.outcome is RunnerOutcome.TIMEOUT
    assert result.error_code == "timeout"
    assert result.error["retryable"] is True
    assert result.cleanup["terminated"] is True


@requires_node
def test_cancellation(manifests):
    cancel = threading.Event()
    cancel.set()
    runner = runtime_support.runner(manifests, limits=runtime_support.limits(process_timeout=30.0))
    result = runner.run("fake_cli", "slow", cancel_event=cancel)
    assert result.outcome is RunnerOutcome.CANCELLED
    assert result.error_code == "cancelled"
    assert result.cleanup["terminated"] is True


@requires_node
def test_process_cleanup_evidence(manifests):
    runner = runtime_support.runner(manifests, limits=runtime_support.limits(process_timeout=0.6))
    result = runner.run("fake_cli", "slow")
    cleanup = result.cleanup
    for key in ("terminated", "method", "waited", "returncode", "readers_alive",
                "orphan_check", "pid_alive_after"):
        assert key in cleanup
    assert cleanup["terminated"] is True
    assert cleanup["method"] in ("taskkill_tree", "kill")
    assert cleanup["waited"] is True
    assert cleanup["orphan_check"] == "returncode_set"
    assert cleanup["readers_alive"] is False
    assert cleanup["pid_alive_after"] is not True


@requires_node
def test_environment_precedence(manifests):
    runner = runtime_support.runner(
        manifests,
        base_env={"FAKE_CLI_TOKEN": "inherited", "SECRET_LEAK": "must-not-reach-child"},
        extra_env={"FAKE_CLI_TOKEN": "staged-token"})
    result = runner.run("fake_cli", "env",
                        ["FAKE_CLI_TOKEN", "SECRET_LEAK",
                         "EXAMDATA_DATA_FAKE_DATA", "EXAMDATA_DATA_ROOT"])
    assert result.ok, result.error
    child = result.payload["env"]
    assert child["FAKE_CLI_TOKEN"] == "staged-token"
    assert child["SECRET_LEAK"] is None
    assert Path(child["EXAMDATA_DATA_FAKE_DATA"]) == STAGING / "runtime" / "data" / "fake-cli"
    assert Path(child["EXAMDATA_DATA_ROOT"]) == STAGING


# -- whitelist rejections and business failure --------------------------------

def test_component_not_allowed(manifests):
    result = runtime_support.runner(manifests).run("no_such_component", "ok")
    assert result.outcome is RunnerOutcome.COMPONENT_NOT_ALLOWED
    assert result.error_code == "component_not_allowed"


def test_command_not_allowed(manifests):
    result = runtime_support.runner(manifests).run("fake_cli", "rm-rf")
    assert result.outcome is RunnerOutcome.COMMAND_NOT_ALLOWED
    assert result.error_code == "command_not_allowed"


def test_missing_component(tmp_path):
    manifest_path = runtime_support.write_manifest(
        tmp_path, [runtime_support.component_spec(entry_point="nope.mjs")])
    manifests = load_manifest_set(manifest_path, deployment_root=STAGING)
    result = runtime_support.runner(manifests).run("fake_cli", "ok")
    assert result.outcome is RunnerOutcome.MISSING_COMPONENT
    assert result.error_code == "component_missing"


@requires_node
def test_business_failure(manifests):
    result = runtime_support.runner(manifests).run("fake_cli", "business-fail")
    assert result.outcome is RunnerOutcome.BUSINESS_FAILURE
    assert result.business_failure is True
    assert result.infrastructure_failure is False
    assert result.error_code == "business_failure"


# -- the classification table itself ------------------------------------------

def test_every_failure_has_a_stable_distinct_error_code():
    failure_codes = [ERROR_CODES[o] for o in RunnerOutcome if o is not RunnerOutcome.OK]
    assert len(failure_codes) == len(set(failure_codes))
    assert all(failure_codes)
    assert set(ERROR_CODES) == set(RunnerOutcome)
    assert ERROR_CODES[RunnerOutcome.OK] == "ok"
    assert ERROR_CODES[RunnerOutcome.MISSING_COMPONENT] == "component_missing"
    assert ERROR_CODES[RunnerOutcome.MISSING_RUNTIME] == "runtime_missing"


# -- stdout parser ------------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("", RunnerOutcome.INVALID_JSON),
    ("   \n", RunnerOutcome.INVALID_JSON),
    ("not json", RunnerOutcome.INVALID_JSON),
    ("123", RunnerOutcome.INVALID_JSON),
    ("[1, 2]", RunnerOutcome.INVALID_JSON),
    ('{"ok": true}', RunnerOutcome.OK),
    ('{"ok": false, "error": "gone"}', RunnerOutcome.BUSINESS_FAILURE),
    ('{"a": 1}{"b": 2}', RunnerOutcome.MULTIPLE_JSON_VALUES),
    ('{"a": 1} trailing', RunnerOutcome.MULTIPLE_JSON_VALUES),
])
def test_parse_stdout(text, expected):
    outcome, payload, message = parse_stdout(text)
    assert outcome is expected
    if expected is RunnerOutcome.OK:
        assert payload == {"ok": True} and message is None
    if expected is RunnerOutcome.BUSINESS_FAILURE:
        assert payload["ok"] is False and message == "gone"
