"""Isolated v2 HTTP API (plan 5, A10).

This package is the staged application factory. It is built **only** from the
staged package (`contracts/`, `providers/`, `catalog/`) plus the standard
library and the already-installed web framework; it never imports the original
`app.py` or any original application module, and it never reads the original
data roots, the network or a database.

Layout:
    envelope.py    the v2 JSON envelope, the error map and public sanitisation
    pagination.py  limit parsing and revision-bound cursor paging (plan 5.7)
    dataset.py     the fixture-backed read dataset (catalog + providers)
    view.py        read-only views over the catalog snapshot and the registry
    links.py       the single route registry: one row per plan 5.4 route
    binary.py      the verified fixture content store and Range/ETag helpers
    app.py         `create_app()` - the application factory and its routes
    openapi.py     runtime-vs-OpenAPI agreement checking

Every plan 5.4 route is registered, including the five binary content/crop
rows: they stream verified synthetic fixture samples with Range and
If-None-Match semantics (200/206/304) and answer 413/416 through the same
envelope. A content or crop link is only emitted for an entity whose verified
sample actually exists, so no advertised link can claim an unavailable feature
(plan 5.4, A10/A11 pass conditions).
"""
from __future__ import annotations

from .app import create_app
from .envelope import SCHEMA_VERSION, ApiError

__all__ = ["create_app", "SCHEMA_VERSION", "ApiError"]
