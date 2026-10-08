"""Runtime-vs-OpenAPI agreement (plan A10 pass condition).

The staged app builds its OpenAPI document from the runtime route table, so the
two cannot drift *structurally*. What can still drift is the *contract*: a route
could be registered without the shared envelope schema, or the registry could
advertise a link the app does not serve. This module checks all of it and is the
single place the tests and the probe tool call.

The envelope schema is declared here once and attached to every non-binary v2
route, so `openapi()["paths"][p][m]["responses"]["200"]` is identical for each
of them and can be validated against a real response with the frozen A04
JSON-Schema-lite validator (no new dependency). The five binary rows (plan 5.3)
declare their raw media types on success and are checked against their own
response set instead, including the HEAD operations they alone register.
"""
from __future__ import annotations

from typing import Any, Mapping

from ..contracts.jsonschema_lite import validate as validate_schema
from . import links
from .envelope import SCHEMA_VERSION

_COMPLETENESS = ["complete", "partial", "unknown", "empty"]

#: The HTTP methods the staged app registers: pair comparisons below operate on
#: this set, so HEAD (binary rows only, checked separately) never leaks into the
#: envelope-schema or runtime/spec pair comparisons.
HTTP_METHODS: frozenset[str] = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE"})

#: The plan 5.1 envelope, as a JSON-Schema (2020-12 subset) document.
ENVELOPE_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "examdata.v2/1 envelope",
    "type": "object",
    "additionalProperties": False,
    "required": ["schema_version", "request_id", "data", "meta", "error"],
    "properties": {
        "schema_version": {"const": SCHEMA_VERSION},
        "request_id": {"type": "string", "minLength": 1, "maxLength": 128},
        "data": {"type": ["object", "array", "string", "integer", "number",
                          "boolean", "null"]},
        "meta": {
            "type": "object",
            "additionalProperties": False,
            "required": ["dataset_revision", "retrieved_at", "pagination",
                         "completeness", "warnings", "providers"],
            "properties": {
                "dataset_revision": {"type": ["string", "null"]},
                "retrieved_at": {"type": ["string", "null"]},
                "pagination": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["limit", "next_cursor"],
                    "properties": {
                        "limit": {"type": ["integer", "null"], "minimum": 1},
                        "next_cursor": {"type": ["string", "null"]},
                    },
                },
                "completeness": {"enum": _COMPLETENESS},
                "warnings": {"type": "array", "items": {"type": "string"}},
                "providers": {"type": "array"},
            },
        },
        "error": {
            "type": ["object", "null"],
            "additionalProperties": False,
            "required": ["code", "message", "retryable", "details"],
            "properties": {
                "code": {"type": "string", "minLength": 1},
                "message": {"type": "string", "minLength": 1},
                "retryable": {"type": "boolean"},
                "details": {"type": ["object", "array", "null"]},
            },
        },
    },
}

RESPONSE_DESCRIPTION = "examdata.v2/1 envelope (plan 5.1); failures carry data=null"

#: Attached to every non-binary registered route so the document always
#: describes the envelope.
ROUTE_RESPONSES: dict[int | str, dict[str, Any]] = {
    200: {"description": RESPONSE_DESCRIPTION,
          "content": {"application/json": {"schema": ENVELOPE_SCHEMA}}},
    400: {"description": "malformed request syntax (for example an invalid cursor)"},
    404: {"description": "known requested identity or resource is absent"},
    409: {"description": "identity, revision or hash conflict"},
    422: {"description": "invalid or unsupported parameter combination"},
    500: {"description": "unexpected internal error, public message sanitized"},
    502: {"description": "invalid or failing upstream response"},
    503: {"description": "required component unavailable"},
}


def binary_route_responses(media_types: tuple[str, ...]
                           ) -> dict[int | str, dict[str, Any]]:
    """The documented responses for one binary route serving ``media_types``.

    Success is raw bytes (200/206) or an empty conditional hit (304); every
    failure is the shared error envelope, exactly like the JSON routes.
    """
    media = {media_type: {} for media_type in media_types}
    envelope = {"content": {"application/json": {"schema": ENVELOPE_SCHEMA}}}
    return {
        200: {"description": "the verified sample bytes (plan 5.3)",
              "content": dict(media)},
        206: {"description": "a satisfiable byte range of the sample (RFC 9110)",
              "content": dict(media)},
        304: {"description": "If-None-Match matched the sample's entity tag; no body"},
        413: {"description": "resource or response budget exceeded (plan 5.2)",
              **envelope},
        416: {"description": "the Range is unsatisfiable for the sample size",
              **envelope},
    }


#: Per capability, the documented responses for the five binary rows.
BINARY_ROUTE_RESPONSES: dict[str, dict[int | str, dict[str, Any]]] = {
    spec.capability: binary_route_responses(spec.media_types)
    for spec in links.ROUTE_SPECS if spec.binary
}


def validate_response(payload: Any) -> list[str]:
    """Validate one runtime response body against the declared envelope schema."""
    return validate_schema(payload, ENVELOPE_SCHEMA)


def iter_routes(routes: Any):
    """Walk app routes, descending into FastAPI's included-router wrappers."""
    for route in routes:
        if getattr(route, "path", None) is not None:
            yield route
            continue
        inner = getattr(route, "routes", None)
        if not inner:
            router = getattr(route, "original_router", None)
            inner = getattr(router, "routes", None) if router is not None else None
        if inner:
            yield from iter_routes(inner)


def runtime_pairs(app: Any) -> set[tuple[str, str]]:
    """(method, path) pairs the app actually serves, excluding framework defaults."""
    pairs: set[tuple[str, str]] = set()
    for route in iter_routes(app.routes):
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None) or set()
        if not path or not path.startswith(links.PREFIX):
            continue
        for method in methods:
            if method in HTTP_METHODS:
                pairs.add((method, path))
    return pairs


def runtime_head_pairs(app: Any) -> set[tuple[str, str]]:
    """(HEAD, path) pairs the app serves; only the binary rows may appear."""
    pairs: set[tuple[str, str]] = set()
    for route in iter_routes(app.routes):
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None) or set()
        if path and path.startswith(links.PREFIX) and "HEAD" in methods:
            pairs.add(("HEAD", path))
    return pairs


def spec_pairs(app: Any) -> set[tuple[str, str]]:
    """Documented (method, path) pairs, restricted to the registered methods."""
    document = app.openapi()
    pairs: set[tuple[str, str]] = set()
    for path, operations in document.get("paths", {}).items():
        for method in operations:
            if method.upper() in HTTP_METHODS:
                pairs.add((method.upper(), path))
    return pairs


def spec_head_pairs(app: Any) -> set[tuple[str, str]]:
    """Documented (HEAD, path) operations."""
    document = app.openapi()
    pairs: set[tuple[str, str]] = set()
    for path, operations in document.get("paths", {}).items():
        for method in operations:
            if method.upper() == "HEAD":
                pairs.add(("HEAD", path))
    return pairs


def spec_envelope_schemas(app: Any) -> dict[str, Any]:
    """The declared 200 schema for every documented non-binary v2 operation."""
    document = app.openapi()
    binary_paths = {s.full_path for s in links.ROUTE_SPECS if s.binary}
    out: dict[str, Any] = {}
    for path, operations in document.get("paths", {}).items():
        if path in binary_paths:
            continue
        for method, operation in operations.items():
            content = (operation.get("responses", {}).get("200", {})
                       .get("content", {}).get("application/json", {}))
            out[f"{method.upper()} {path}"] = content.get("schema")
    return out


def agreement_problems(app: Any) -> list[str]:
    """Every way the runtime, the OpenAPI document and the registry can disagree."""
    problems: list[str] = []
    runtime = runtime_pairs(app)
    spec = spec_pairs(app)
    implemented = links.advertised_pairs()
    deferred = frozenset((s.method, s.full_path) for s in links.DEFERRED_SPECS)
    binary = tuple(s for s in links.ROUTE_SPECS if s.binary)

    missing = sorted(implemented - runtime)
    if missing:
        problems.append(f"registry advertises routes the app does not serve: {missing}")
    extra = sorted(runtime - implemented)
    if extra:
        problems.append(f"the app serves routes the registry does not list: {extra}")
    if spec != runtime:
        problems.append(
            f"OpenAPI paths and runtime routes differ: "
            f"spec-only={sorted(spec - runtime)} runtime-only={sorted(runtime - spec)}")
    served_deferred = sorted(deferred & runtime)
    if served_deferred:
        problems.append(f"deferred routes are registered: {served_deferred}")

    expected_head = {("HEAD", row.full_path) for row in binary}
    runtime_head = runtime_head_pairs(app)
    if runtime_head != expected_head:
        problems.append(
            f"HEAD is served exactly for the binary rows: "
            f"unexpected={sorted(runtime_head - expected_head)} "
            f"missing={sorted(expected_head - runtime_head)}")
    spec_head = spec_head_pairs(app)
    if spec_head != runtime_head:
        problems.append(
            f"documented HEAD operations differ from the runtime: "
            f"spec-only={sorted(spec_head - runtime_head)} "
            f"runtime-only={sorted(runtime_head - spec_head)}")

    document = app.openapi()
    for row in binary:
        operation = document.get("paths", {}).get(row.full_path, {}).get("get")
        if operation is None:
            problems.append(f"{row.capability}: binary route is not documented")
            continue
        responses = operation.get("responses", {})
        content = responses.get("200", {}).get("content", {})
        if set(content) != set(row.media_types) or "application/json" in content:
            problems.append(
                f"{row.capability}: documented 200 media {sorted(content)} do not "
                f"match {list(row.media_types)}")
        required = {"200", "206", "304", "413", "416"}
        documented = {str(code) for code in responses}
        if not required <= documented:
            problems.append(
                f"{row.capability}: missing documented binary responses "
                f"{sorted(required - documented)}")

    for label, schema in sorted(spec_envelope_schemas(app).items()):
        if schema != ENVELOPE_SCHEMA:
            problems.append(f"{label}: the documented 200 schema is not the shared envelope")
    return problems


__all__ = [
    "HTTP_METHODS",
    "ENVELOPE_SCHEMA",
    "ROUTE_RESPONSES",
    "RESPONSE_DESCRIPTION",
    "binary_route_responses",
    "BINARY_ROUTE_RESPONSES",
    "validate_response",
    "runtime_pairs",
    "runtime_head_pairs",
    "spec_pairs",
    "spec_head_pairs",
    "spec_envelope_schemas",
    "agreement_problems",
]
