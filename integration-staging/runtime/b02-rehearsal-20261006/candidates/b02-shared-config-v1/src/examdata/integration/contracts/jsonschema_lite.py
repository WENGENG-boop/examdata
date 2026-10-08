"""A deliberately small JSON-Schema (2020-12 subset) validator.

Why not a library: Phase A must not add dependencies to the shared virtual
environment, and the schemas in `contracts/schema/` are generated from the
dataclasses in this package, so only a known subset of keywords is ever emitted.

Supported keywords: ``$ref`` (local ``#/$defs/...``), ``type``, ``enum``,
``const``, ``required``, ``properties``, ``additionalProperties`` (bool),
``items``, ``minItems``, ``maxItems``, ``uniqueItems``, ``minLength``,
``maxLength``, ``pattern``, ``minimum``, ``maximum``, ``oneOf``, ``anyOf``,
``allOf``, ``propertyNames``.

Unsupported keywords are ignored - and :func:`unsupported_keywords` reports them,
so a caller can prove a schema stayed inside the supported subset instead of
assuming full validation.
"""
from __future__ import annotations

import re
from typing import Any, Iterable, Mapping

SUPPORTED = frozenset({
    "$schema", "$id", "$defs", "$ref", "title", "description", "type", "enum",
    "const", "required", "properties", "additionalProperties", "items",
    "minItems", "maxItems", "uniqueItems", "minLength", "maxLength", "pattern",
    "minimum", "maximum", "oneOf", "anyOf", "allOf", "propertyNames", "default",
    "examples", "x-generated-by",
})


class SchemaError(ValueError):
    """The schema itself is malformed."""


def _resolve(root: Mapping[str, Any], ref: str) -> Mapping[str, Any]:
    if not ref.startswith("#/"):
        raise SchemaError(f"only local references are supported, got {ref!r}")
    node: Any = root
    for part in ref[2:].split("/"):
        if not isinstance(node, Mapping) or part not in node:
            raise SchemaError(f"unresolvable reference {ref!r}")
        node = node[part]
    return node


def _type_ok(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, Mapping)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    return True


def validate(instance: Any, schema: Mapping[str, Any], *,
             root: Mapping[str, Any] | None = None, path: str = "$") -> list[str]:
    """Validate `instance` against `schema`; return a list of problems."""
    root = root if root is not None else schema
    problems: list[str] = []

    if "$ref" in schema:
        return validate(instance, _resolve(root, schema["$ref"]), root=root, path=path)

    if "allOf" in schema:
        for sub in schema["allOf"]:
            problems.extend(validate(instance, sub, root=root, path=path))
    if "anyOf" in schema:
        branches = [validate(instance, sub, root=root, path=path) for sub in schema["anyOf"]]
        if all(branch for branch in branches):
            problems.append(f"{path}: no anyOf branch matched")
    if "oneOf" in schema:
        matched = sum(1 for sub in schema["oneOf"]
                      if not validate(instance, sub, root=root, path=path))
        if matched != 1:
            problems.append(f"{path}: expected exactly one oneOf branch to match, matched {matched}")

    if "const" in schema and instance != schema["const"]:
        problems.append(f"{path}: expected const {schema['const']!r}, got {instance!r}")
    if "enum" in schema and instance not in schema["enum"]:
        problems.append(f"{path}: {instance!r} is not one of {schema['enum']}")

    expected = schema.get("type")
    if expected is not None:
        types = expected if isinstance(expected, list) else [expected]
        if not any(_type_ok(instance, t) for t in types):
            problems.append(f"{path}: expected type {types}, got {type(instance).__name__}")
            return problems

    if isinstance(instance, Mapping):
        for name in schema.get("required", []):
            if name not in instance:
                problems.append(f"{path}: missing required property {name!r}")
        props = schema.get("properties", {})
        for name, value in instance.items():
            if name in props:
                problems.extend(validate(value, props[name], root=root, path=f"{path}.{name}"))
            else:
                extra = schema.get("additionalProperties", True)
                if extra is False:
                    problems.append(f"{path}: unexpected property {name!r}")
                elif isinstance(extra, Mapping):
                    problems.extend(validate(value, extra, root=root, path=f"{path}.{name}"))
        if "propertyNames" in schema:
            for name in instance:
                problems.extend(validate(name, schema["propertyNames"], root=root,
                                         path=f"{path}.<key>"))
    elif isinstance(instance, list):
        if "items" in schema:
            for i, item in enumerate(instance):
                problems.extend(validate(item, schema["items"], root=root, path=f"{path}[{i}]"))
        if "minItems" in schema and len(instance) < schema["minItems"]:
            problems.append(f"{path}: fewer than {schema['minItems']} items")
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            problems.append(f"{path}: more than {schema['maxItems']} items")
        if schema.get("uniqueItems"):
            seen: list[Any] = []
            for item in instance:
                if item in seen:
                    problems.append(f"{path}: duplicate item {item!r}")
                seen.append(item)
    elif isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            problems.append(f"{path}: shorter than {schema['minLength']} characters")
        if "maxLength" in schema and len(instance) > schema["maxLength"]:
            problems.append(f"{path}: longer than {schema['maxLength']} characters")
        if "pattern" in schema and not re.search(schema["pattern"], instance):
            problems.append(f"{path}: does not match pattern {schema['pattern']!r}")
    elif isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            problems.append(f"{path}: below minimum {schema['minimum']}")
        if "maximum" in schema and instance > schema["maximum"]:
            problems.append(f"{path}: above maximum {schema['maximum']}")

    return problems


NAME_MAPS = frozenset({"$defs", "properties"})


def unsupported_keywords(schema: Mapping[str, Any], *,
                         root: Mapping[str, Any] | None = None,
                         path: str = "#") -> list[str]:
    """List schema keywords outside the supported subset (recursively).

    ``$defs`` and ``properties`` are maps of *names* to sub-schemas, so their
    keys are data, not keywords: the walk descends into their values instead of
    reporting every model field name as an unsupported keyword.
    """
    root = root if root is not None else schema
    found: list[str] = []
    if isinstance(schema, Mapping):
        for key, value in schema.items():
            if key.startswith("x-"):
                # JSON Schema extension annotation (e.g. x-generated-by).
                continue
            if key not in SUPPORTED:
                found.append(f"{path}/{key}")
            elif key == "$ref":
                continue
            elif key in NAME_MAPS and isinstance(value, Mapping):
                for name, sub in value.items():
                    found.extend(unsupported_keywords(sub, root=root,
                                                      path=f"{path}/{key}/{name}"))
            elif isinstance(value, (Mapping, list)):
                found.extend(_walk(value, root, f"{path}/{key}"))
    return found


def _walk(node: Any, root: Mapping[str, Any], path: str) -> list[str]:
    out: list[str] = []
    if isinstance(node, Mapping):
        out.extend(unsupported_keywords(node, root=root, path=path))
    elif isinstance(node, list):
        for i, item in enumerate(node):
            out.extend(_walk(item, root, f"{path}[{i}]"))
    return out


def iter_refs(schema: Mapping[str, Any]) -> Iterable[str]:
    if isinstance(schema, Mapping):
        for key, value in schema.items():
            if key == "$ref" and isinstance(value, str):
                yield value
            else:
                yield from iter_refs(value)
    elif isinstance(schema, list):
        for item in schema:
            yield from iter_refs(item)


__all__ = ["validate", "unsupported_keywords", "iter_refs", "SUPPORTED", "SchemaError"]
