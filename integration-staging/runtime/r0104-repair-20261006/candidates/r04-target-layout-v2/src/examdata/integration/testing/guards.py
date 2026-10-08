"""Isolation guards for the Phase A staged test harness.

Installed by `tests/conftest.py` before any application module is imported:

* module guard   - refuses imports of the original `examdata` package outright
                   (the shared venv has an editable install whose `.pth` points
                   `examdata` at the original `examdata/src` tree);
* module audit   - every loaded `examdata.integration.*` module must resolve
                   under the staging tree;
* path guard     - staged code may only touch paths inside the staging tree,
                   after symlink/junction resolution;
* network guard  - sockets may only reach loopback; a deliberately failing
                   transport is provided for provider tests.

Each guard fails loudly when a forbidden original module or data path is
supplied; `tests/test_harness_isolation.py` proves that deliberately.
"""
from __future__ import annotations

import os
import socket
import sys
from pathlib import Path

_ENV_STAGING_ROOT = "EXAMDATA_INTEGRATION_STAGING_ROOT"
# R04 private candidate variant: the explicit product deployment root is the
# primary source; the original-code denial target is supplied explicitly too.
_ENV_ROOT = "EXAMDATA_INTEGRATION_ROOT"
_ENV_ORIGINAL_APP_CODE = "EXAMDATA_INTEGRATION_ORIGINAL_APP_CODE"


def _resolve_staging_root() -> Path:
    explicit = os.environ.get(_ENV_ROOT)
    if explicit:
        return Path(os.path.realpath(explicit))
    root = Path(os.path.realpath(Path(__file__).resolve().parents[3]))
    if root.name != "integration-staging":
        override = os.environ.get(_ENV_STAGING_ROOT)
        if not override:
            raise RuntimeError(
                f"staged package is not inside an 'integration-staging' tree ({root}); "
                f"set {_ENV_STAGING_ROOT} to override")
        root = Path(os.path.realpath(override))
    return root


STAGING_ROOT = _resolve_staging_root()
WORKSPACE_ROOT = STAGING_ROOT.parent
_original = os.environ.get(_ENV_ORIGINAL_APP_CODE)
ORIGINAL_APP_CODE = (Path(os.path.realpath(_original)) if _original
                     else WORKSPACE_ROOT / "examdata" / "src")


class ForbiddenImportError(ImportError):
    """Raised when staged tests try to import original application modules."""


class ForbiddenPathError(PermissionError):
    """Raised when a staged path escapes the staging tree."""


class StagingViolationError(AssertionError):
    """Raised when a loaded application module resolves outside staging."""


class NetworkDisabledError(OSError):
    """Raised when staged code attempts a non-loopback network operation."""


def _norm(p: os.PathLike | str) -> str:
    return os.path.normcase(os.path.realpath(str(p)))


def is_within(child: os.PathLike | str, parent: os.PathLike | str) -> bool:
    c, p = _norm(child), _norm(parent)
    return c == p or c.startswith(p + os.sep)


def ensure_staged_path(p: os.PathLike | str, purpose: str = "path") -> Path:
    """Return the resolved path, or raise if it leaves the staging tree."""
    resolved = Path(os.path.realpath(str(p)))
    if is_within(resolved, ORIGINAL_APP_CODE):
        raise ForbiddenPathError(
            f"{purpose} points into original application code: {resolved}")
    if not is_within(resolved, STAGING_ROOT):
        raise ForbiddenPathError(
            f"{purpose} escapes the staging tree: {resolved} (allowed: {STAGING_ROOT})")
    return resolved


class _ForbiddenModuleFinder:
    """Meta-path finder that blocks the original application package."""

    # R04 private candidate variant: the target-layout package is
    # `examdata.integration`, so the *staging* name is what this private
    # harness refuses.
    blocked = ("examdata_integration",)

    def find_spec(self, fullname, path=None, target=None):
        top = fullname.split(".")[0]
        if top in self.blocked:
            raise ForbiddenImportError(
                f"import of original application module {fullname!r} is forbidden in "
                f"staged tests; staged code must import examdata.integration.*")
        return None


def install_module_guard() -> None:
    if not any(isinstance(f, _ForbiddenModuleFinder) for f in sys.meta_path):
        sys.meta_path.insert(0, _ForbiddenModuleFinder())


def assert_app_modules_within_staging() -> None:
    """Audit sys.modules: no original modules, no application module outside staging."""
    offenders: list[tuple[str, str | None, str]] = []
    for name, mod in list(sys.modules.items()):
        top = name.split(".")[0]
        if top == "examdata_integration":
            offenders.append((name, getattr(mod, "__file__", None), "staging module name"))
            continue
        if top == "examdata.integration":
            f = getattr(mod, "__file__", None)
            if f and not is_within(f, STAGING_ROOT):
                offenders.append((name, f, "resolves outside the staging tree"))
    if offenders:
        detail = "; ".join(f"{n} ({why}: {f})" for n, f, why in offenders)
        raise StagingViolationError(f"application module isolation violated: {detail}")


_LOOPBACK_NAMES = {"", "localhost", "127.0.0.1", "::1"}


def _is_loopback(host) -> bool:
    if host is None or not isinstance(host, str):
        return True
    h = host.strip("[]").lower()
    return h in _LOOPBACK_NAMES or h.startswith("127.")


def _check_sockaddr(address, op: str) -> None:
    if isinstance(address, tuple) and address:
        host = address[0]
    elif isinstance(address, str):
        return
    else:
        return
    if not _is_loopback(host):
        raise NetworkDisabledError(
            f"network disabled in staged tests: {op} -> {address!r} is not loopback")


_real_create_connection = socket.create_connection
_real_getaddrinfo = socket.getaddrinfo


class _GuardedSocket(socket.socket):
    def connect(self, address):
        _check_sockaddr(address, "socket.connect")
        return super().connect(address)

    def connect_ex(self, address):
        _check_sockaddr(address, "socket.connect_ex")
        return super().connect_ex(address)


def _guarded_create_connection(address, *args, **kwargs):
    _check_sockaddr(address, "create_connection")
    return _real_create_connection(address, *args, **kwargs)


def _guarded_getaddrinfo(host, port, *args, **kwargs):
    if not _is_loopback(host):
        raise NetworkDisabledError(
            f"DNS disabled in staged tests: getaddrinfo({host!r}, {port!r})")
    return _real_getaddrinfo(host, port, *args, **kwargs)


def install_network_guard() -> None:
    """Route every socket through the loopback-only policy (idempotent)."""
    if getattr(socket, "_staged_network_guard_installed", False):
        return
    socket.socket = _GuardedSocket
    socket.create_connection = _guarded_create_connection
    socket.getaddrinfo = _guarded_getaddrinfo
    socket._staged_network_guard_installed = True


def offline_transport(*args, **kwargs):
    """Failing fake transport for provider tests (no real network in Phase A)."""
    raise NetworkDisabledError(
        "offline transport: real network is disabled in Phase A staged tests")
