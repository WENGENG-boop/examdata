"""Static import-resolution guard for copied Node code (plan section 11/A02).

Resolves relative and absolute-path specifiers in a JavaScript file and rejects
any that escape the staging tree. Bare specifiers (Node builtins and packages)
are not resolved here. Used by the staged test suite now and by the controlled
Node runner from A06 onward.
"""
from __future__ import annotations

import re
from pathlib import Path

from .guards import ensure_staged_path

_SPECIFIER_PATTERNS = (
    re.compile(r"""\brequire\s*\(\s*['"]([^'"]+)['"]\s*\)"""),
    re.compile(r"""\bimport\s*\(\s*['"]([^'"]+)['"]\s*\)"""),
    re.compile(r"""\bfrom\s+['"]([^'"]+)['"]"""),
    re.compile(r"""\bimport\s+['"]([^'"]+)['"]"""),
)

_NODE_SUFFIXES = (".js", ".mjs", ".cjs", ".json")


def iter_specifiers(text: str):
    """Yield each distinct import/require specifier in source order."""
    matches: list[tuple[int, str]] = []
    for pattern in _SPECIFIER_PATTERNS:
        for match in pattern.finditer(text):
            matches.append((match.start(), match.group(1)))
    matches.sort(key=lambda item: item[0])
    seen: set[str] = set()
    for _, spec in matches:
        if spec not in seen:
            seen.add(spec)
            yield spec


def _looks_absolute(spec: str) -> bool:
    return spec.startswith("/") or spec.startswith("\\\\") or bool(re.match(r"^[A-Za-z]:[\\/]", spec))


def resolve_relative_import(from_file, spec: str) -> Path:
    """Resolve a relative specifier against a file, preferring an existing file."""
    base = Path(from_file).resolve().parent
    target = base / spec
    candidates = [target]
    candidates += [Path(str(target) + suffix) for suffix in _NODE_SUFFIXES]
    candidates += [target / "index.js", target / "index.mjs"]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return target


def check_node_file(path, purpose: str = "node import guard") -> list[str]:
    """Return resolved local specifiers; raise if any resolution escapes staging."""
    resolved = ensure_staged_path(path, purpose)
    text = resolved.read_text(encoding="utf-8", errors="replace")
    checked: list[str] = []
    for spec in iter_specifiers(text):
        if spec.startswith("."):
            target = resolve_relative_import(resolved, spec)
            ensure_staged_path(target, f"relative import {spec!r} in {resolved.name}")
            checked.append(spec)
        elif _looks_absolute(spec):
            ensure_staged_path(spec, f"absolute import {spec!r} in {resolved.name}")
            checked.append(spec)
    return checked
