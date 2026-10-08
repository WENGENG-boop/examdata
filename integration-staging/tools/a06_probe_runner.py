#!/usr/bin/env python3
"""A06 runtime probe: exercise configuration, manifest and the controlled runner.

Offline, stdlib-only, private fixtures. Starts real ``node`` subprocesses that
run the synthetic ``components/fake-node-cli`` stub and prints a stable
transcript to stdout; the closing-checks tool captures it to
`docs/integration/execution/evidence/A06/runner_stdout.txt`. Exits non-zero if
any scenario fails.
"""
from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

sys.dont_write_bytecode = True

WS = Path(__file__).resolve().parents[2]
STAGING = WS / "integration-staging"
SRC = STAGING / "src"

sys.path.insert(0, str(SRC))
# R04: product code resolves its deployment root explicitly (never by directory name).
os.environ.setdefault("EXAMDATA_INTEGRATION_ROOT", str(STAGING))

from examdata_integration.runtime import (  # noqa: E402
    ERROR_CODES,
    RunnerOutcome,
    load_manifest_set,
    resolve_config,
)
from examdata_integration.runtime.doctor import build_report  # noqa: E402
from examdata_integration.runtime.redact import (  # noqa: E402
    PATH_PLACEHOLDER,
    SECRET_PLACEHOLDER,
)
from examdata_integration.testing import runtime_support  # noqa: E402

FAKE_SECRET = runtime_support.FAKE_SECRET
SCRATCH = runtime_support.SCRATCH
NODE = runtime_support.node_executable()

failures: list[str] = []


def expect(name: str, condition: bool, detail: str = "") -> None:
    print(f"[{'ok' if condition else 'FAIL'}] {name}{(' :: ' + detail) if detail else ''}")
    if not condition:
        failures.append(name)


def main() -> int:
    print("=== A06 runtime probe ===")
    print("node:", NODE)
    if NODE is None:
        print("A06_PROBE: FAIL (node runtime not on PATH)")
        return 1

    # 1. configuration precedence
    cfg = resolve_config(explicit={"ielts_max_concurrent": 9},
                         env={"EXAMDATA_IELTS_MAX_CONCURRENT": "8"})
    expect("config.explicit_over_env", cfg.get("ielts_max_concurrent") == 9
           and cfg.source("ielts_max_concurrent") == "explicit")
    expect("config.offline_default", cfg.get("network_mode") == "offline")

    # 2. manifest admits the fake component, whitelists its commands
    manifests = load_manifest_set(runtime_support.MANIFEST_PATH, deployment_root=STAGING)
    expect("manifest.no_problems", manifests.problems == [])
    expect("manifest.admits_fake_cli", manifests.ids() == ["fake_cli"])
    expect("manifest.command_whitelist",
           manifests.allows("fake_cli", "ok") and not manifests.allows("fake_cli", "rm"))

    # 3. happy path
    runner = runtime_support.runner(manifests)
    ok = runner.run("fake_cli", "ok")
    expect("runner.ok", ok.ok and ok.exit_code == 0 and ok.error is None)
    expect("runner.cwd_is_component_dir", ok.payload["cwd"] == str(runtime_support.FAKE_COMPONENT_DIR))

    # 4. environment precedence: staged over inherited, non-allowlisted absent
    env_runner = runtime_support.runner(
        manifests, base_env={"FAKE_CLI_TOKEN": "inherited", "SECRET_LEAK": "leak"},
        extra_env={"FAKE_CLI_TOKEN": "staged"})
    env_res = env_runner.run("fake_cli", "env",
                             ["FAKE_CLI_TOKEN", "SECRET_LEAK", "EXAMDATA_DATA_FAKE_DATA"])
    expect("env.staged_overrides_inherited",
           env_res.payload["env"]["FAKE_CLI_TOKEN"] == "staged")
    expect("env.non_allowlisted_absent", env_res.payload["env"]["SECRET_LEAK"] is None)
    expect("env.data_root_injected",
           Path(env_res.payload["env"]["EXAMDATA_DATA_FAKE_DATA"])
           == STAGING / "runtime" / "data" / "fake-cli")

    # 5. argv never shell-interpolated
    tricky = ["a b", "; rm -rf /", "$(whoami)"]
    echoed = runner.run("fake_cli", "echo", tricky)
    expect("argv.no_shell_interpolation", echoed.payload["echo"] == tricky)

    # 6. classification of the failure modes
    expect("classify.business_failure",
           runner.run("fake_cli", "business-fail").outcome is RunnerOutcome.BUSINESS_FAILURE)
    expect("classify.invalid_json",
           runner.run("fake_cli", "bad-json").outcome is RunnerOutcome.INVALID_JSON)
    expect("classify.multiple_json_values",
           runner.run("fake_cli", "two-values").outcome is RunnerOutcome.MULTIPLE_JSON_VALUES)
    nz = runner.run("fake_cli", "nonzero")
    expect("classify.nonzero_exit",
           nz.outcome is RunnerOutcome.NONZERO_EXIT and nz.exit_code == 3)

    # 7. stderr redaction
    expect("redact.stderr", SECRET_PLACEHOLDER in nz.stderr_text
           and PATH_PLACEHOLDER in nz.stderr_text
           and FAKE_SECRET not in nz.stderr_text)

    # 8. whitelist rejections and missing pieces
    expect("reject.component_not_allowed",
           runner.run("no_such", "ok").outcome is RunnerOutcome.COMPONENT_NOT_ALLOWED)
    expect("reject.command_not_allowed",
           runner.run("fake_cli", "rm-rf").outcome is RunnerOutcome.COMMAND_NOT_ALLOWED)
    expect("reject.missing_runtime",
           runtime_support.runner(manifests, runtime="no-such-runtime-xyz").run(
               "fake_cli", "ok").outcome is RunnerOutcome.MISSING_RUNTIME)

    # 9. missing component (declared but the file is absent)
    tmp_manifest = runtime_support.write_manifest(
        SCRATCH / "probe-missing", [runtime_support.component_spec(entry_point="nope.mjs")])
    missing_set = load_manifest_set(tmp_manifest, deployment_root=STAGING)
    expect("reject.missing_component",
           runtime_support.runner(missing_set).run(
               "fake_cli", "ok").outcome is RunnerOutcome.MISSING_COMPONENT)

    # 10. spaces in paths
    spaced = runtime_support.copy_fake_component(SCRATCH / "probe space dir", "fake node cli")
    spaced_manifest = runtime_support.write_manifest(
        SCRATCH / "probe-space-manifest",
        [runtime_support.component_spec(code_location=runtime_support.relative_to_staging(spaced))])
    spaced_set = load_manifest_set(spaced_manifest, deployment_root=STAGING)
    spaced_res = runtime_support.runner(spaced_set).run("fake_cli", "ok")
    expect("paths.spaces_ok", spaced_res.ok and "probe space dir" in spaced_res.payload["cwd"])

    # 11. timeout and cleanup evidence
    slow_runner = runtime_support.runner(
        manifests, limits=runtime_support.limits(process_timeout=0.6))
    timed = slow_runner.run("fake_cli", "slow")
    expect("bound.timeout", timed.outcome is RunnerOutcome.TIMEOUT)
    expect("cleanup.timeout_evidence",
           timed.cleanup["terminated"] is True
           and timed.cleanup["method"] in ("taskkill_tree", "kill")
           and timed.cleanup["orphan_check"] == "returncode_set"
           and timed.cleanup["pid_alive_after"] is not True)

    # 12. output overflow
    overflow_runner = runtime_support.runner(
        manifests, limits=runtime_support.limits(stdout_bytes=8192))
    over = overflow_runner.run("fake_cli", "flood")
    expect("bound.output_overflow",
           over.outcome is RunnerOutcome.OUTPUT_OVERFLOW and over.stdout_truncated)
    expect("cleanup.overflow_evidence",
           over.cleanup["terminated"] is True
           and over.cleanup["orphan_check"] == "returncode_set"
           and over.cleanup["pid_alive_after"] is not True)

    # 13. cancellation
    cancel = threading.Event()
    cancel.set()
    cancelled = runtime_support.runner(
        manifests, limits=runtime_support.limits(process_timeout=30.0)).run(
            "fake_cli", "slow", cancel_event=cancel)
    expect("bound.cancelled",
           cancelled.outcome is RunnerOutcome.CANCELLED
           and cancelled.cleanup["terminated"] is True
           and cancelled.cleanup["pid_alive_after"] is not True)

    # 14. queue full
    semaphore = threading.BoundedSemaphore(1)
    semaphore.acquire()
    try:
        queued = runtime_support.runner(
            manifests, limits=runtime_support.limits(queue_timeout=0.2, concurrency=1),
            semaphore=semaphore).run("fake_cli", "ok")
    finally:
        semaphore.release()
    expect("bound.queue_full", queued.outcome is RunnerOutcome.QUEUE_FULL
           and queued.error["retryable"] is True)

    # 15. every failure has a distinct, stable error code
    codes = [ERROR_CODES[o] for o in RunnerOutcome if o is not RunnerOutcome.OK]
    expect("classify.distinct_error_codes", len(codes) == len(set(codes)) and all(codes))

    # 16. doctor is read-only and Phase A compliant
    sentinel = SCRATCH / "probe-doctor-catalog"
    report = build_report(env={"EXAMDATA_CATALOG_ROOT": str(sentinel)},
                          manifest_path=runtime_support.MANIFEST_PATH, deployment_root=STAGING)
    expect("doctor.creates_nothing",
           report["creates_directories"] is False and not sentinel.exists())
    expect("doctor.offline_compliant", report["network"]["compliant"] is True)
    expect("doctor.runtime_found", report["runtime"]["found"] is True)

    print(f"\nA06_PROBE: {'PASS' if not failures else 'FAIL'} ({len(failures)} failing)")
    if failures:
        for name in failures:
            print(f"  failing: {name}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
