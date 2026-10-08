"""Limit parsing and revision-bound cursor paging (plan 5.7).

Two rules from the plan drive this module:

* the default new v2 list limit is 50 and the initial maximum is 200, unless a
  route documents a justified different bound;
* a cursor binds query, sort, revision and last key; its integrity and length
  are validated, and a cursor whose revision is no longer published is a
  conflict (409), never a silent restart.

The cursor codec itself is the frozen A09 one (:mod:`catalog.revision`); this
module only maps its two failure modes onto the plan's HTTP statuses so there is
exactly one cursor implementation in the staged tree.
"""
from __future__ import annotations

from typing import Any, Callable, Iterable, Sequence

from ..catalog.revision import (
    InvalidCursorError,
    StaleCursorError,
    make_cursor,
    resolve_cursor,
)
from .envelope import ApiError

DEFAULT_LIMIT = 50
MAX_LIMIT = 200


def parse_limit(raw: Any, *, default: int = DEFAULT_LIMIT,
                maximum: int = MAX_LIMIT) -> int:
    """Parse a `limit` query value; 400 for non-numeric, 422 for out of range."""
    if raw is None or raw == "":
        return default
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        raise ApiError(400, "invalid_limit",
                       f"limit must be an integer between 1 and {maximum}")
    if value < 1:
        raise ApiError(422, "invalid_limit", "limit must be at least 1")
    if value > maximum:
        raise ApiError(422, "limit_exceeded",
                       f"limit {value} exceeds the maximum of {maximum}")
    return value


def parse_int(raw: Any, *, name: str, minimum: int | None = None,
              maximum: int | None = None) -> int | None:
    """Parse an optional integer query value with the same 400/422 split."""
    if raw is None or raw == "":
        return None
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        raise ApiError(400, f"invalid_{name}", f"{name} must be an integer")
    if minimum is not None and value < minimum:
        raise ApiError(422, f"invalid_{name}", f"{name} must be at least {minimum}")
    if maximum is not None and value > maximum:
        raise ApiError(422, f"invalid_{name}", f"{name} must be at most {maximum}")
    return value


def page_items(items: Sequence[Any], *, limit: int, cursor: str | None,
               query: dict[str, Any], sort: str, revision: str,
               available_revisions: Iterable[str],
               key: Callable[[Any], str]) -> tuple[list[Any], str | None]:
    """Return one page of `items` plus the next cursor (or ``None``).

    ``items`` must already be sorted by the same deterministic order the cursor
    binds to. A cursor for another query/sort/limit is a 400 (it does not belong
    to this listing); a cursor whose revision is unpublished is a 409; a cursor
    whose last key is no longer present at the same revision is a 409 conflict,
    because the page boundary cannot be honoured.
    """
    start = 0
    if cursor:
        try:
            payload = resolve_cursor(cursor, available_revisions)
        except InvalidCursorError as exc:
            raise ApiError(400, "invalid_cursor", str(exc)) from exc
        except StaleCursorError as exc:
            raise ApiError(409, "stale_cursor", str(exc),
                           retryable=True,
                           details={"restart": "request the first page again"}) from exc

        if payload.get("query") != dict(query):
            raise ApiError(400, "cursor_query_mismatch",
                           "the cursor was issued for a different query")
        if payload.get("sort") != sort:
            raise ApiError(400, "cursor_sort_mismatch",
                           "the cursor was issued for a different sort order")
        if payload.get("limit") not in (None, limit):
            raise ApiError(400, "cursor_limit_mismatch",
                           "the cursor was issued for a different limit")

        keys = [key(item) for item in items]
        last_key = payload.get("last_key")
        if last_key not in keys:
            raise ApiError(409, "cursor_key_conflict",
                           "the cursor's last key is no longer present at this revision",
                           retryable=True,
                           details={"restart": "request the first page again"})
        start = keys.index(last_key) + 1

    window = list(items[start:start + limit])
    next_cursor = None
    if window and start + limit < len(items):
        next_cursor = make_cursor(dataset_revision=revision, query=query, sort=sort,
                                  last_key=key(window[-1]), limit=limit)
    return window, next_cursor


__all__ = ["DEFAULT_LIMIT", "MAX_LIMIT", "parse_limit", "parse_int", "page_items"]
