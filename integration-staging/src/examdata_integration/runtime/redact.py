"""Redaction for public runner surfaces (plan 6.4 rule 9, A06).

`stderr` is a log channel owned by the child process: it may contain absolute
paths, temporary directories, or a token the child was given. Before any of it
reaches a public response the runner passes it through :func:`redact_text`,
which replaces drive-rooted / UNC / POSIX paths and any supplied secret value,
collapses whitespace, and bounds the result.

This mirrors the conservative heuristic in
`examdata_integration.providers.results._sanitize` (A05) but is kept separate so
the frozen A05 module is not modified by A06.
"""
from __future__ import annotations

import re
from typing import Iterable

PATH_PLACEHOLDER = "<path>"
SECRET_PLACEHOLDER = "<secret>"

_UNC_RE = re.compile(r"\\\\[^\s'\"]+")
_PATH_RE = re.compile(r"(?:[A-Za-z]:[\\/]|/)[^\s'\"]+")

DEFAULT_LIMIT = 500


def redact_text(text: object, *, secrets: Iterable[str] = (), limit: int = DEFAULT_LIMIT) -> str:
    """Return a short, path-free, secret-free rendering of ``text``."""
    out = str(text)
    for secret in secrets:
        if secret:
            out = out.replace(str(secret), SECRET_PLACEHOLDER)
    out = _UNC_RE.sub(PATH_PLACEHOLDER, out)
    out = _PATH_RE.sub(PATH_PLACEHOLDER, out)
    out = " ".join(out.split())
    return out[:limit]


def contains_path(text: object) -> bool:
    """True when ``text`` still carries something that looks like a path."""
    value = str(text)
    return bool(_PATH_RE.search(value) or _UNC_RE.search(value))


__all__ = ["redact_text", "contains_path", "PATH_PLACEHOLDER", "SECRET_PLACEHOLDER"]
