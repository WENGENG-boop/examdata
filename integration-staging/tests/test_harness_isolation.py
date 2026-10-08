"""Harness isolation proof tests (plan section 11/A02).

Each guard must work and must fail deliberately when a forbidden original module
or data path is supplied. These tests are the A02 pass condition: a fixture test
runs, every created file stays inside the allowlist, and a prohibited
source-network call fails.
"""
from __future__ import annotations

import importlib
import importlib.util
import socket
import subprocess
import sys
import types

import pytest

from examdata_integration.testing import guards
from examdata_integration.testing.guards import (
    STAGING_ROOT,
    WORKSPACE_ROOT,
    ForbiddenImportError,
    ForbiddenPathError,
    NetworkDisabledError,
    assert_app_modules_within_staging,
    ensure_staged_path,
    is_within,
    offline_transport,
)

UNROUTABLE = "192.0.2.1"  # RFC 5737 TEST-NET-1: no host, no real traffic


def test_fixture_test_runs_and_writes_stay_inside_allowlist(tmp_path):
    probe = tmp_path / "probe.txt"
    probe.write_text("ok", encoding="utf-8")
    assert is_within(probe, STAGING_ROOT)
    assert ensure_staged_path(probe, "fixture write").is_file()


def test_pytest_temp_is_private(tmp_path):
    assert is_within(tmp_path, STAGING_ROOT)
    assert not is_within(tmp_path, WORKSPACE_ROOT / "examdata")


def test_module_guard_installed_before_tests():
    assert any(type(f).__name__ == "_ForbiddenModuleFinder" for f in sys.meta_path)


def test_original_package_import_fails_deliberately():
    with pytest.raises(ForbiddenImportError):
        importlib.import_module("examdata")
    assert "examdata" not in sys.modules


def test_original_package_spec_resolution_is_intercepted():
    with pytest.raises(ForbiddenImportError):
        importlib.util.find_spec("examdata")


def test_module_audit_fails_deliberately():
    hazard = types.ModuleType("examdata_integration.hazard")
    hazard.__file__ = str(WORKSPACE_ROOT / "examdata" / "src" / "examdata" / "api" / "app.py")
    sys.modules[hazard.__name__] = hazard
    try:
        with pytest.raises(guards.StagingViolationError):
            assert_app_modules_within_staging()
    finally:
        del sys.modules[hazard.__name__]
    assert_app_modules_within_staging()


def test_path_guard_rejects_forbidden_original_paths():
    for forbidden in (
        WORKSPACE_ROOT / "examdata" / "src",
        WORKSPACE_ROOT / "examdata" / "src" / "examdata" / "api" / "app.py",
        WORKSPACE_ROOT / "ielts-data",
        WORKSPACE_ROOT,
    ):
        with pytest.raises(ForbiddenPathError):
            ensure_staged_path(forbidden, "deliberate forbidden path")
    assert ensure_staged_path(STAGING_ROOT / "runtime").is_dir()


def _try_link(link, target) -> str | None:
    try:
        link.symlink_to(target, target_is_directory=True)
        return "symlink"
    except (OSError, NotImplementedError):
        pass
    try:
        proc = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)],
                              capture_output=True, timeout=30)
        if proc.returncode == 0:
            return "junction"
    except OSError:
        pass
    return None


def test_path_guard_rejects_link_escape(tmp_path):
    link = tmp_path / "escape"
    kind = _try_link(link, WORKSPACE_ROOT / "examdata")
    if kind is None:
        pytest.skip("link creation not permitted on this host (symlink and junction both refused)")
    try:
        with pytest.raises(ForbiddenPathError):
            ensure_staged_path(link / "src", "linked path")
    finally:
        if kind == "symlink":
            link.unlink(missing_ok=True)
        else:
            link.rmdir()


def test_network_guard_blocks_real_connection():
    with pytest.raises(NetworkDisabledError):
        socket.create_connection((UNROUTABLE, 9), timeout=2)
    sock = socket.socket()
    try:
        with pytest.raises(NetworkDisabledError):
            sock.connect((UNROUTABLE, 9))
    finally:
        sock.close()
    with pytest.raises(NetworkDisabledError):
        socket.getaddrinfo("example.com", 80)


def test_loopback_policy_is_not_a_blanket_block():
    try:
        socket.create_connection(("127.0.0.1", 1), timeout=2)
    except NetworkDisabledError:
        pytest.fail("loopback must be permitted by the staged network policy")
    except OSError:
        pass


def test_offline_transport_fails_deliberately():
    with pytest.raises(NetworkDisabledError):
        offline_transport("https://example.com/api")


def test_subprocess_cwd_and_writes_stay_private():
    cwd = STAGING_ROOT / "runtime" / "tmp"
    cwd.mkdir(parents=True, exist_ok=True)
    out = cwd / "probe_from_subprocess.txt"
    try:
        proc = subprocess.run(
            [sys.executable, "-c",
             "import pathlib; pathlib.Path('probe_from_subprocess.txt').write_text('ok')"],
            cwd=cwd, capture_output=True, timeout=60)
        assert proc.returncode == 0, proc.stderr
        assert out.is_file() and is_within(out, STAGING_ROOT)
    finally:
        out.unlink(missing_ok=True)


def test_no_application_modules_leaked():
    assert_app_modules_within_staging()
