"""A06 runner bounds and result-shape tests (plan 6.4 rules 5, 10).

The runner applies a queue bound, a process bound, stdout/stderr byte budgets
and a process-local concurrency limit. One call starts exactly one process.
"""
from __future__ import annotations

import pytest

from examdata_integration.runtime import (
    RunResult,
    RunnerLimits,
    RunnerOutcome,
    load_manifest_set,
)
from examdata_integration.testing import runtime_support

STAGING = runtime_support.STAGING
NODE = runtime_support.node_executable()
requires_node = pytest.mark.skipif(NODE is None, reason="node runtime not on PATH")


@pytest.fixture()
def manifests():
    return load_manifest_set(runtime_support.MANIFEST_PATH, deployment_root=STAGING)


# -- the limits object --------------------------------------------------------

def test_limits_defaults():
    limits = RunnerLimits()
    assert limits.to_dict() == {
        "queue_timeout": 5.0,
        "process_timeout": 120.0,
        "stdout_bytes": 4 * 1024 * 1024,
        "stderr_bytes": 256 * 1024,
        "concurrency": 4,
        "terminate_grace": 5.0,
    }


@pytest.mark.parametrize("kwargs", [
    {"concurrency": 0},
    {"stdout_bytes": 0},
    {"stderr_bytes": 0},
    {"process_timeout": 0},
    {"queue_timeout": -1},
])
def test_limits_validation(kwargs):
    with pytest.raises(ValueError):
        RunnerLimits(**kwargs)


def test_limits_overrides_are_recorded():
    limits = RunnerLimits(stdout_bytes=1024, stderr_bytes=64, concurrency=2)
    assert limits.stdout_bytes == 1024
    assert limits.stderr_bytes == 64
    assert limits.concurrency == 2


# -- byte budgets -------------------------------------------------------------

@requires_node
def test_stdout_not_truncated_within_budget(manifests):
    result = runtime_support.runner(manifests).run("fake_cli", "ok")
    assert result.stdout_truncated is False
    assert result.stderr_truncated is False


@requires_node
def test_stderr_budget_truncates(manifests):
    runner = runtime_support.runner(manifests, limits=runtime_support.limits(stderr_bytes=16))
    result = runner.run("fake_cli", "noisy")
    assert result.ok
    assert result.stderr_truncated is True
    assert result.stderr_bytes > 16
    # The retained, redacted text stays bounded regardless of the raw volume.
    assert len(result.stderr_text) <= 500


@requires_node
def test_queue_wait_is_recorded(manifests):
    result = runtime_support.runner(manifests).run("fake_cli", "ok")
    assert isinstance(result.queue_wait_ms, int)
    assert result.queue_wait_ms >= 0
    assert result.duration_ms >= 0


# -- one process per call (rule 10) -------------------------------------------

@requires_node
def test_one_run_starts_one_process(manifests):
    result = runtime_support.runner(manifests).run("fake_cli", "echo", ["a", "b"])
    assert isinstance(result.pid, int) and result.pid > 0
    # argv is [runtime, entry, command, *args] - one process, no list fan-out.
    assert len(result.argv) == 3 + 2
    assert result.payload["pid"] == result.pid


# -- result shape -------------------------------------------------------------

def test_run_result_to_dict_has_documented_keys():
    result = RunResult(outcome=RunnerOutcome.OK, component_id="c", command="x")
    payload = result.to_dict()
    for key in ("outcome", "ok", "business_failure", "infrastructure_failure",
                "component_id", "command", "argv", "pid", "exit_code", "duration_ms",
                "queue_wait_ms", "stdout_bytes", "stderr_bytes", "stdout_truncated",
                "stderr_truncated", "error", "stderr_text", "cleanup"):
        assert key in payload
    assert payload["outcome"] == "ok"
