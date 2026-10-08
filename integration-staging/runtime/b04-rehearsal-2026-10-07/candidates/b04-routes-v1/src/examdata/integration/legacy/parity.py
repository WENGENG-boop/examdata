"""Shape-parity harness for legacy payload proposals (plan 5.5, packet A12).

`shape()` turns a payload into a fingerprint that records *structure only*:
keys, JSON value kinds, list emptiness, and None-ness. No payload value ever
enters a fingerprint (it is not a value hash - it is a type/shape map), so a
fingerprint can be logged beside the ledger without leaking contents, and
`value_leak()` lets tests prove that property on real fixtures.

Detections the differ must make (both directions):

* a key that exists on one side and not the other;
* a JSON kind change, which includes ``none -> <value>`` and ``<value> -> none``;
* ``empty -> non-empty`` and ``non-empty -> empty`` list transitions;
* item-level shape changes inside non-empty lists (kinds are compared, still
  value-free).

This is the Phase B gate: every legacy route whose payload is reshaped by a
staged adapter must satisfy ``assert_shape_parity(legacy_payload,
staged_payload)`` before the route may switch. Nothing here imports an
original module or touches I/O.
"""
from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

#: Leaf vocabulary. `bool` deliberately precedes `int` (bool is an int subclass).
_LEAF_KINDS = ("none", "bool", "int", "float", "str")

_SKIP_LEAK_WORDS = frozenset(
    {"none", "bool", "int", "float", "str", "dict", "list", "empty", "nonempty", "kinds"}
)


def _canonical(node: Any) -> str:
    return json.dumps(node, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _leaf_kind(value: Any) -> str | None:
    if value is None:
        return "none"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    return None


def shape(payload: Any) -> Any:
    """A value-free structural fingerprint of a JSON-like payload.

    * mapping  -> ``{"dict": {key: shape(value), ...}}`` (keys sorted);
    * list/tuple -> ``{"list": "empty"}`` or
      ``{"list": "nonempty", "kinds": [distinct item shapes, sorted]}``;
    * scalar   -> ``"none" | "bool" | "int" | "float" | "str"``;
    * anything else -> ``"other:<class name>"`` (class name only, never value).
    """
    kind = _leaf_kind(payload)
    if kind is not None:
        return kind
    if isinstance(payload, Mapping):
        return {"dict": {str(key): shape(payload[key]) for key in sorted(payload, key=str)}}
    if isinstance(payload, Sequence) and not isinstance(payload, (str, bytes, bytearray)):
        items = list(payload)
        if not items:
            return {"list": "empty"}
        kinds = sorted({_canonical(shape(item)) for item in items})
        return {"list": "nonempty", "kinds": [json.loads(k) for k in kinds]}
    return f"other:{type(payload).__name__}"


def render_shape(node: Any) -> str:
    """Compact, value-free rendering of a fingerprint fragment for messages."""
    if isinstance(node, str):
        return node
    if isinstance(node, Mapping) and "dict" in node:
        inner = node["dict"]
        fields = ",".join(f"{key}:{render_shape(value)}" for key, value in inner.items())
        return f"dict{{{fields}}}"
    if isinstance(node, Mapping) and "list" in node:
        if node["list"] == "empty":
            return "list[empty]"
        kinds = ",".join(render_shape(kind) for kind in node.get("kinds", []))
        return f"list[{kinds}]"
    return _canonical(node)


def shape_diff(before: Any, after: Any, path: str = "$") -> list[str]:
    """Human-readable differences between two fingerprints (empty == parity)."""
    diffs: list[str] = []
    if isinstance(before, str) and isinstance(after, str):
        if before != after:
            diffs.append(f"{path}: kind {before} -> {after}")
        return diffs
    if isinstance(before, Mapping) and isinstance(after, Mapping):
        if "dict" in before and "dict" in after:
            before_fields, after_fields = before["dict"], after["dict"]
            for key in sorted(set(before_fields) | set(after_fields)):
                if key not in after_fields:
                    diffs.append(
                        f"{path}.{key}: key missing after (was {render_shape(before_fields[key])})")
                elif key not in before_fields:
                    diffs.append(
                        f"{path}.{key}: key added by after ({render_shape(after_fields[key])})")
                else:
                    diffs.extend(shape_diff(
                        before_fields[key], after_fields[key], f"{path}.{key}"))
            return diffs
        if "list" in before and "list" in after:
            before_state, after_state = before["list"], after["list"]
            if before_state == "empty" and after_state == "empty":
                return diffs
            if before_state == "empty":
                diffs.append(f"{path}: list empty -> non-empty")
                return diffs
            if after_state == "empty":
                diffs.append(f"{path}: list non-empty -> empty")
                return diffs
            before_kinds = {_canonical(kind) for kind in before.get("kinds", [])}
            after_kinds = {_canonical(kind) for kind in after.get("kinds", [])}
            for missing in sorted(before_kinds - after_kinds):
                diffs.append(f"{path}[]: item shape missing after: {render_shape(json.loads(missing))}")
            for added in sorted(after_kinds - before_kinds):
                diffs.append(f"{path}[]: item shape added by after: {render_shape(json.loads(added))}")
            return diffs
    if before != after:
        diffs.append(f"{path}: {render_shape(before)} -> {render_shape(after)}")
    return diffs


def assert_shape_parity(before: Any, after: Any, *, label: str = "payload") -> Any:
    """Raise with the full diff list unless shapes match exactly; return `after`."""
    diffs = shape_diff(shape(before), shape(after))
    if diffs:
        raise AssertionError(
            f"shape parity failed for {label}:\n  " + "\n  ".join(diffs))
    return after


def value_leak(payload: Any, fingerprint: Any) -> list[str]:
    """String payload values that surface in a serialized fingerprint.

    A correct shape fingerprint leaks nothing; everything returned by this
    helper is a defect. Mapping keys are not walked (they legitimately appear
    in a fingerprint as structure), and payload strings that coincide with the
    shape vocabulary (``"str"``, ``"empty"``, ...) are ignored as degenerate.
    """
    blob = _canonical(fingerprint)
    leaked: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, str):
            if node and node not in _SKIP_LEAK_WORDS and node in blob:
                leaked.append(node)
        elif isinstance(node, Mapping):
            for value in node.values():
                walk(value)
        elif isinstance(node, Sequence) and not isinstance(node, (str, bytes, bytearray)):
            for value in node:
                walk(value)

    walk(payload)
    return leaked
