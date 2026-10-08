"""Product-safe deployment roots and containment helpers (R04).

Product runtime modules must not import the test-only harness guard
(``..testing.guards``): that guard resolves its root from a directory-name
heuristic ("integration-staging") and therefore breaks the package once it sits
at the target layout ``examdata/src/examdata/integration/``. This module replaces
it for product code:

* :func:`resolve_root` resolves the deployment root from an *explicit*
  argument or the ``EXAMDATA_INTEGRATION_ROOT`` environment variable -- never
  from ``__file__`` parents or a directory name;
* :func:`is_within` and :func:`ensure_within` are pure containment helpers.

The isolation rule that refuses the *original* tree stays in the test harness
(``testing/guards.py``); product code only enforces that a supplied path lies
inside the deployment root it was given.
"""
from __future__ import annotations

import os
from pathlib import Path

# Explicit product configuration: the deployment root a product process runs
# against. Distinct from the test-only ``EXAMDATA_INTEGRATION_STAGING_ROOT``
# override, which exists solely so the staging harness can name its tree.
ENV_ROOT = "EXAMDATA_INTEGRATION_ROOT"


def normalize(p: os.PathLike | str) -> str:
    return os.path.normcase(os.path.realpath(str(p)))


def is_within(child: os.PathLike | str, parent: os.PathLike | str) -> bool:
    c, p = normalize(child), normalize(parent)
    return c == p or c.startswith(p + os.sep)


def resolve_root(explicit: os.PathLike | str | None = None) -> Path:
    """Resolve the deployment root explicitly (argument, then env), never by name."""
    if explicit is not None:
        return Path(os.path.realpath(str(explicit)))
    configured = os.environ.get(ENV_ROOT)
    if not configured:
        raise RuntimeError(
            "no deployment root configured for product code; pass an explicit root "
            f"or set {ENV_ROOT}")
    return Path(os.path.realpath(configured))


class PathOutsideRootError(PermissionError):
    """Raised when a path leaves the deployment root it was checked against."""


def ensure_within(path: os.PathLike | str, root: os.PathLike | str,
                  purpose: str = "path") -> Path:
    """Return the resolved path, or raise if it leaves the deployment root."""
    resolved = Path(os.path.realpath(str(path)))
    if not is_within(resolved, root):
        raise PathOutsideRootError(
            f"{purpose} escapes the deployment root: {resolved} (allowed: {root})")
    return resolved


__all__ = ["ENV_ROOT", "PathOutsideRootError", "normalize", "is_within", "resolve_root",
           "ensure_within"]
