"""Controlled Node runner (plan 6.4, A06).

One place that starts a child process, and ten rules it follows:

1. validate component and command against the manifest whitelist;
2. invoke an argument array with no shell interpolation;
3. set cwd to the component's own directory (inside the deployment root);
4. pass only approved environment variables plus the component's explicit data
   roots, with the staged values overriding inherited ones;
5. bound queue time, process time, stdout bytes, stderr bytes and concurrency;
6. require one valid JSON object on stdout, logs on stderr;
7. classify missing component, missing runtime, startup failure, timeout,
   cancellation, non-zero exit, invalid JSON and business failure separately;
8. on timeout/cancellation terminate the process tree and wait for it, then
   record cleanup evidence (returncode observed, no orphan);
9. redact stderr before it can reach a public response;
10. never run one subprocess per list item (callers use batch commands or a
    published local snapshot).

The concurrency limit is process-local. It is *not* a global limit across
Uvicorn workers; initial deployment stays at one worker until shared source
limiting exists (plan 6.4).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

from ..testing.guards import STAGING_ROOT
from .classification import (
    RunnerOutcome,
    error_object,
    is_business_failure,
    is_infrastructure_failure,
)
from .manifest import ManifestSet
from .redact import redact_text

#: Environment variables a child may inherit for the process to function at all.
BASE_ENV_ALLOWLIST: tuple[str, ...] = (
    "PATH", "PATHEXT", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "COMSPEC",
    "TEMP", "TMP", "HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA",
    "PROGRAMDATA", "PROGRAMFILES", "NUMBER_OF_PROCESSORS", "OS",
    "PROCESSOR_ARCHITECTURE", "LANG", "LC_ALL",
)

READ_CHUNK = 65536


@dataclass(frozen=True)
class RunnerLimits:
    """Every bound the runner applies (plan 6.4 rule 5)."""

    queue_timeout: float = 5.0
    process_timeout: float = 120.0
    stdout_bytes: int = 4 * 1024 * 1024
    stderr_bytes: int = 256 * 1024
    concurrency: int = 4
    terminate_grace: float = 5.0

    def __post_init__(self) -> None:  # pragma: no cover - validation only
        if self.concurrency < 1:
            raise ValueError("concurrency must be >= 1")
        if self.stdout_bytes < 1 or self.stderr_bytes < 1:
            raise ValueError("byte budgets must be >= 1")
        if self.queue_timeout < 0 or self.process_timeout <= 0:
            raise ValueError("timeouts must be positive")

    def to_dict(self) -> dict[str, Any]:
        return {
            "queue_timeout": self.queue_timeout,
            "process_timeout": self.process_timeout,
            "stdout_bytes": self.stdout_bytes,
            "stderr_bytes": self.stderr_bytes,
            "concurrency": self.concurrency,
            "terminate_grace": self.terminate_grace,
        }


@dataclass
class RunResult:
    """The classified outcome of one controlled invocation."""

    outcome: RunnerOutcome
    component_id: str
    command: str
    argv: list[str] = field(default_factory=list)
    pid: int | None = None
    exit_code: int | None = None
    duration_ms: int = 0
    queue_wait_ms: int = 0
    stdout_bytes: int = 0
    stderr_bytes: int = 0
    stdout_truncated: bool = False
    stderr_truncated: bool = False
    payload: Any = None
    error: dict[str, Any] | None = None
    stderr_text: str | None = None
    cleanup: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.outcome is RunnerOutcome.OK

    @property
    def business_failure(self) -> bool:
        return is_business_failure(self.outcome)

    @property
    def infrastructure_failure(self) -> bool:
        return is_infrastructure_failure(self.outcome)

    @property
    def error_code(self) -> str:
        return self.error["code"] if self.error else "ok"

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome.value,
            "ok": self.ok,
            "business_failure": self.business_failure,
            "infrastructure_failure": self.infrastructure_failure,
            "component_id": self.component_id,
            "command": self.command,
            "argv": list(self.argv),
            "pid": self.pid,
            "exit_code": self.exit_code,
            "duration_ms": self.duration_ms,
            "queue_wait_ms": self.queue_wait_ms,
            "stdout_bytes": self.stdout_bytes,
            "stderr_bytes": self.stderr_bytes,
            "stdout_truncated": self.stdout_truncated,
            "stderr_truncated": self.stderr_truncated,
            "error": self.error,
            "stderr_text": self.stderr_text,
            "cleanup": dict(self.cleanup),
        }


def parse_stdout(text: str) -> tuple[RunnerOutcome, Any, str | None]:
    """Parse exactly one JSON object from stdout (plan 6.4 rule 6)."""
    stripped = text.strip()
    if not stripped:
        return RunnerOutcome.INVALID_JSON, None, "stdout is empty; expected one JSON object"
    decoder = json.JSONDecoder()
    try:
        value, end = decoder.raw_decode(stripped)
    except ValueError as exc:
        return RunnerOutcome.INVALID_JSON, None, f"stdout is not valid JSON: {exc}"
    if stripped[end:].strip():
        return (RunnerOutcome.MULTIPLE_JSON_VALUES, None,
                "stdout contains more than one JSON value")
    if not isinstance(value, dict):
        return (RunnerOutcome.INVALID_JSON, None,
                "top-level JSON value is not an object")
    if value.get("ok") is False:
        message = value.get("error")
        return (RunnerOutcome.BUSINESS_FAILURE, value,
                message if isinstance(message, str) else "component reported ok=false")
    return RunnerOutcome.OK, value, None


def _pid_alive(pid: int) -> bool | None:
    """Best-effort liveness probe for cleanup evidence (None = unknown)."""
    if os.name == "nt":
        try:
            proc = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                                  capture_output=True, text=True, timeout=10)
        except Exception:  # noqa: BLE001 - evidence only
            return None
        return re.search(rf"\b{pid}\b", proc.stdout or "") is not None
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except (PermissionError, OSError):
        return None
    return True


class NodeRunner:
    """Spawns whitelisted component commands under a bounded contract."""

    def __init__(self, manifest_set: ManifestSet, *, runtime: str | None = None,
                 limits: RunnerLimits | None = None,
                 base_env: Mapping[str, str] | None = None,
                 extra_env: Mapping[str, str] | None = None,
                 secrets: Iterable[str] = (),
                 deployment_root: str | os.PathLike | None = None,
                 semaphore: threading.BoundedSemaphore | None = None,
                 runtime_resolver: Callable[[str], str | None] | None = None,
                 popen: Callable[..., subprocess.Popen] | None = None,
                 sleep: Callable[[float], None] | None = None,
                 clock: Callable[[], float] | None = None) -> None:
        self._manifests = manifest_set
        self._runtime = runtime if runtime is not None else "node"
        self._limits = limits or RunnerLimits()
        self._deployment_root = Path(os.path.abspath(str(
            deployment_root if deployment_root is not None
            else (manifest_set.deployment_root or STAGING_ROOT))))
        self._secrets = tuple(s for s in secrets if s)
        self._semaphore = semaphore or threading.BoundedSemaphore(self._limits.concurrency)
        self._resolve_runtime = runtime_resolver or self._default_runtime_resolver
        self._popen = popen or subprocess.Popen
        self._sleep = sleep or time.sleep
        self._clock = clock or time.monotonic

        parent = dict(os.environ)
        for mapping in (base_env, extra_env):
            if not mapping:
                continue
            for key, value in mapping.items():
                self._set_env(parent, str(key), str(value))
        self._source_env = parent

    @staticmethod
    def _set_env(target: dict[str, str], key: str, value: str) -> None:
        """Set ``key`` in ``target``; on Windows replace any case-variant key."""
        if os.name == "nt":
            lowered = key.lower()
            for existing in [k for k in target if k.lower() == lowered]:
                if existing != key:
                    del target[existing]
        target[key] = value

    # -- environment ---------------------------------------------------------
    @staticmethod
    def _default_runtime_resolver(spec: str) -> str | None:
        if not spec:
            return None
        if os.sep in spec or "/" in spec or Path(spec).is_absolute():
            return spec if Path(spec).exists() else None
        return shutil.which(spec)

    def child_environment(self, component) -> dict[str, str]:
        """Only approved variables plus the component's explicit data roots."""
        approved = set(BASE_ENV_ALLOWLIST) | set(component.environment_allowlist)
        # Windows environment names are case-insensitive; resolve them that way
        # so an allowlisted "PATH" matches the inherited "Path".
        by_lower = {name.lower(): name for name in self._source_env}
        env: dict[str, str] = {}
        for name in approved:
            source_key = by_lower.get(name.lower())
            if source_key is not None:
                self._set_env(env, source_key, self._source_env[source_key])
        env["EXAMDATA_DATA_ROOT"] = str(self._deployment_root)
        for role, path in component.data_root_paths(self._deployment_root).items():
            env[f"EXAMDATA_DATA_{role.upper()}"] = str(path)
        return env

    # -- running -------------------------------------------------------------
    def _rejected(self, outcome: RunnerOutcome, component_id: str, command: str,
                  *, argv: Sequence[str] | None = None, detail: str,
                  queue_wait_ms: int = 0) -> RunResult:
        return RunResult(
            outcome=outcome, component_id=component_id, command=command,
            argv=[str(a) for a in (argv or ())],
            error=error_object(outcome, redact_text(detail, secrets=self._secrets)),
            queue_wait_ms=queue_wait_ms,
            cleanup={"terminated": False, "method": None, "waited": True,
                     "returncode": None, "orphan_check": "not_started"},
        )

    def run(self, component_id: str, command: str, args: Sequence[Any] = (), *,
            timeout: float | None = None, queue_timeout: float | None = None,
            cancel_event: threading.Event | None = None,
            stdin: bytes | None = None) -> RunResult:
        limits = self._limits
        process_timeout = limits.process_timeout if timeout is None else float(timeout)
        queue_time = limits.queue_timeout if queue_timeout is None else float(queue_timeout)

        manifest = self._manifests.get(component_id)
        if manifest is None:
            return self._rejected(RunnerOutcome.COMPONENT_NOT_ALLOWED, component_id, command,
                                  detail=f"component {component_id!r} is not in the whitelist")
        if command not in manifest.supported_commands:
            return self._rejected(RunnerOutcome.COMMAND_NOT_ALLOWED, component_id, command,
                                  detail=f"command {command!r} is not declared for {component_id!r}")

        entry = manifest.entry_path(self._deployment_root)
        runtime_path = self._resolve_runtime(self._runtime)
        argv = [str(runtime_path or self._runtime), str(entry), str(command),
                *(str(a) for a in args)]

        if not entry.is_file():
            return self._rejected(RunnerOutcome.MISSING_COMPONENT, component_id, command,
                                  argv=argv, detail=f"entry point not found: {entry}")
        if runtime_path is None:
            return self._rejected(RunnerOutcome.MISSING_RUNTIME, component_id, command,
                                  argv=argv,
                                  detail=f"runtime {self._runtime!r} is not executable or on PATH")

        start = self._clock()
        acquired = self._semaphore.acquire(timeout=max(0.0, queue_time))
        queue_wait_ms = int((self._clock() - start) * 1000)
        if not acquired:
            return self._rejected(RunnerOutcome.QUEUE_FULL, component_id, command, argv=argv,
                                  detail=f"queue full after {queue_time:g}s", queue_wait_ms=queue_wait_ms)
        try:
            return self._spawn(manifest, component_id, command, argv, process_timeout,
                               cancel_event, stdin, queue_wait_ms)
        finally:
            self._semaphore.release()

    def _spawn(self, manifest, component_id: str, command: str, argv: list[str],
               process_timeout: float, cancel_event: threading.Event | None,
               stdin: bytes | None, queue_wait_ms: int) -> RunResult:
        env = self.child_environment(manifest)
        cwd = manifest.code_path(self._deployment_root)
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
        started = self._clock()
        try:
            proc = self._popen(
                argv, cwd=str(cwd), env=env, shell=False,
                stdin=subprocess.PIPE if stdin is not None else subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                creationflags=creationflags,
            )
        except OSError as exc:
            return RunResult(
                outcome=RunnerOutcome.STARTUP_FAILURE, component_id=component_id,
                command=command, argv=argv,
                error=error_object(RunnerOutcome.STARTUP_FAILURE,
                                   redact_text(f"could not start {self._runtime!r}: {exc}",
                                               secrets=self._secrets)),
                queue_wait_ms=queue_wait_ms,
                cleanup={"terminated": False, "method": None, "waited": True,
                         "returncode": None, "orphan_check": "not_started"},
            )

        if stdin is not None:
            try:
                proc.stdin.write(stdin)
            except (BrokenPipeError, OSError):
                pass
            finally:
                try:
                    proc.stdin.close()
                except (BrokenPipeError, OSError):
                    pass

        overflow = threading.Event()
        totals: dict[str, int] = {"stdout": 0, "stderr": 0}
        buffers: dict[str, bytearray] = {"stdout": bytearray(), "stderr": bytearray()}

        def reader(name: str, stream, cap: int, kill_on_overflow: bool) -> None:
            while True:
                chunk = stream.read(READ_CHUNK)
                if not chunk:
                    break
                totals[name] += len(chunk)
                if len(buffers[name]) < cap:
                    buffers[name].extend(chunk[: cap - len(buffers[name])])
                if kill_on_overflow and totals[name] > cap:
                    overflow.set()

        out_thread = threading.Thread(target=reader,
                                      args=("stdout", proc.stdout, self._limits.stdout_bytes, True),
                                      name=f"runner-stdout-{proc.pid}", daemon=True)
        err_thread = threading.Thread(target=reader,
                                      args=("stderr", proc.stderr, self._limits.stderr_bytes, False),
                                      name=f"runner-stderr-{proc.pid}", daemon=True)
        out_thread.start()
        err_thread.start()

        cancelled = False
        timed_out = False
        deadline = started + process_timeout
        while proc.poll() is None:
            if cancel_event is not None and cancel_event.is_set():
                cancelled = True
                break
            if overflow.is_set():
                break
            if self._clock() >= deadline:
                timed_out = True
                break
            self._sleep(0.01)

        method: str | None = None
        returncode: int | None = proc.poll()
        if cancelled or timed_out or overflow.is_set():
            if proc.poll() is None:
                method, returncode = self._terminate(proc)
        else:
            try:
                returncode = proc.wait(timeout=self._limits.terminate_grace)
            except subprocess.TimeoutExpired:  # pragma: no cover - defensive
                method, returncode = self._terminate(proc)

        # Join before classifying: a reader may still be setting the overflow
        # flag while the process is exiting on its own.
        out_thread.join(timeout=self._limits.terminate_grace)
        err_thread.join(timeout=self._limits.terminate_grace)
        readers_alive = out_thread.is_alive() or err_thread.is_alive()
        if proc.returncode is not None:
            returncode = proc.returncode

        duration_ms = int((self._clock() - started) * 1000)
        stdout_text = buffers["stdout"].decode("utf-8", errors="replace")
        stderr_raw = buffers["stderr"].decode("utf-8", errors="replace")
        stdout_truncated = totals["stdout"] > self._limits.stdout_bytes
        stderr_truncated = totals["stderr"] > self._limits.stderr_bytes
        overflowed = overflow.is_set()

        outcome, payload, message = self._classify(
            cancelled=cancelled, timed_out=timed_out, overflowed=overflowed,
            returncode=returncode, stdout_text=stdout_text)

        alive = _pid_alive(proc.pid) if (method is not None and proc.pid) else None
        cleanup = {
            "terminated": method is not None,
            "method": method,
            "waited": returncode is not None,
            "returncode": returncode,
            "readers_alive": readers_alive,
            "orphan_check": "not_started" if proc.pid is None else (
                "returncode_set" if returncode is not None else "still_running"),
            "pid_alive_after": alive,
        }

        result = RunResult(
            outcome=outcome, component_id=component_id, command=command, argv=argv,
            pid=proc.pid, exit_code=returncode, duration_ms=duration_ms,
            queue_wait_ms=queue_wait_ms,
            stdout_bytes=totals["stdout"], stderr_bytes=totals["stderr"],
            stdout_truncated=stdout_truncated, stderr_truncated=stderr_truncated,
            payload=payload,
            error=error_object(outcome, redact_text(message, secrets=self._secrets)
                               if message else None),
            stderr_text=redact_text(stderr_raw, secrets=self._secrets),
            cleanup=cleanup,
        )
        return result

    @staticmethod
    def _classify(*, cancelled: bool, timed_out: bool, overflowed: bool,
                  returncode: int | None, stdout_text: str
                  ) -> tuple[RunnerOutcome, Any, str | None]:
        if cancelled:
            return RunnerOutcome.CANCELLED, None, "run was cancelled"
        if overflowed:
            return RunnerOutcome.OUTPUT_OVERFLOW, None, "stdout exceeded the output budget"
        if timed_out:
            return RunnerOutcome.TIMEOUT, None, "process exceeded the process timeout"
        if returncode != 0:
            return (RunnerOutcome.NONZERO_EXIT, None,
                    f"process exited with code {returncode}")
        return parse_stdout(stdout_text)

    def _terminate(self, proc) -> tuple[str, int | None]:
        method: str | None = None
        if os.name == "nt":
            try:
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                               capture_output=True, timeout=self._limits.terminate_grace)
                method = "taskkill_tree"
            except Exception:  # noqa: BLE001 - fall back to kill
                method = None
        if method is None:
            try:
                proc.kill()
                method = "kill"
            except OSError:
                method = "kill_failed"
        try:
            returncode = proc.wait(timeout=self._limits.terminate_grace)
        except subprocess.TimeoutExpired:  # pragma: no cover - defensive
            returncode = None
        return method, returncode


__all__ = [
    "RunnerLimits", "RunResult", "NodeRunner", "parse_stdout", "BASE_ENV_ALLOWLIST",
]
