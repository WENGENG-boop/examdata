"""Legacy v1 payload builders (plan 5.5, packet A12 - proposals).

Every builder reproduces a payload contract recorded by static inspection of a
legacy handler (see `evidence/A12/legacy_shape_extract.json`). The derived
functions are pure: no I/O, no original imports, no fabrication - a builder can
only re-shape data the caller already has.

Contract rules enforced here:

* a page echoes `limit`/`offset` unchanged; range validation stays with the
  legacy layer (`Query(ge=..., le=...)`);
* `count`/`total` are computed from the list actually returned, never guessed;
* quality tokens are never rewritten (`quality_fingerprint` +
  `assert_no_quality_change` let tests prove a translation did not touch them);
* a missing key stays missing (`json_copy` preserves absence; no `setdefault`).
"""
from __future__ import annotations

import json
from typing import Any, Iterable, Mapping

QUALITY_DIMENSIONS: tuple[str, ...] = (
    "content",
    "answer_presence",
    "answer_verification",
    "assets",
    "audio_integrity",
    "audio_alignment",
    "region_verification",
)

#: `POST /sample` 422 detail, verbatim from the legacy handler.
SAMPLE_COUNT_OR_TARGET_DETAIL = "count 与 marks_target 至少给一个"

#: `/paper-qa/query` 422 detail, verbatim from the legacy handler.
PAPER_QA_FORMAT_DETAIL = "format must be binary or json"


def json_copy(payload: Any) -> Any:
    """A deep copy through JSON: proves serializability, keeps absence intact."""
    return json.loads(json.dumps(payload, ensure_ascii=False))


def _require_int(name: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an int, got {type(value).__name__}")
    return value


def legacy_page(items: Iterable[Any], *, total: int, limit: int, offset: int) -> dict[str, Any]:
    """`GET /papers` and `GET /questions`: {"total","limit","offset","items"}."""
    _require_int("total", total)
    _require_int("limit", limit)
    _require_int("offset", offset)
    return {"total": total, "limit": limit, "offset": offset,
            "items": json_copy(list(items))}


def legacy_search_page(items: Iterable[Any], *, total: int, limit: int, offset: int,
                       board: str, by_board: Any,
                       board_source: str | None = None) -> dict[str, Any]:
    """`GET /api/v1/search`: the page plus {"by_board","board","board_source"}.

    `board_source` is the recorded legacy value ("explicit" when a board was
    resolved, `None` when none was supplied) - never a token the caller did
    not pass.
    """
    _require_int("total", total)
    _require_int("limit", limit)
    _require_int("offset", offset)
    return {"total": total, "limit": limit, "offset": offset,
            "by_board": json_copy(by_board), "items": json_copy(list(items)),
            "board": board, "board_source": board_source}


def legacy_counted(items: Iterable[Any], *, extra: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """`GET /overrides`: {"count","items"} (+ caller-supplied extra keys)."""
    items_list = json_copy(list(items))
    payload: dict[str, Any] = {"count": len(items_list), "items": items_list}
    if extra:
        if "count" in extra or "items" in extra:
            raise ValueError("extra must not shadow count/items")
        payload.update(json_copy(dict(extra)))
    return payload


def legacy_status_counted(status: str, items: Iterable[Any], *,
                          total: int | None = None) -> dict[str, Any]:
    """`GET /review` and `GET /explanations/review-queue` queue payloads.

    `total` is only attached when the legacy handler computed it; absence is
    preserved rather than filled with `len(items)`.
    """
    payload: dict[str, Any] = {"status": status, "count": len(list(items)),
                               "items": json_copy(list(items))}
    if total is not None:
        payload["total"] = _require_int("total", total)
    return payload


def unified_question_view(*, question_id: Any, board: str, board_source: str,
                          source: Any, bundle: Any) -> dict[str, Any]:
    """`GET /api/v1/question/{question_id}` outer payload."""
    return {"question_id": question_id, "board": board, "board_source": board_source,
            "source": json_copy(source), "bundle": json_copy(bundle)}


def taxonomy_payload(roots: Iterable[Any]) -> dict[str, Any]:
    """`GET /taxonomy`: {"roots","topic_count"} with topic_count == len(roots)."""
    roots_list = json_copy(list(roots))
    return {"roots": roots_list, "topic_count": len(roots_list)}


def classifications_payload(items: Iterable[Any]) -> dict[str, Any]:
    """`GET /classifications`: conflicts counted, never resolved."""
    items_list = json_copy(list(items))
    conflicts = sum(1 for item in items_list if item.get("method") == "conflict")
    return {"count": len(items_list), "conflicts": conflicts, "items": items_list}


def provenance_payload(target_kind: str, target_id: Any,
                       sources: Iterable[Any]) -> dict[str, Any]:
    """`GET /questions/{id}/provenance` and `/assets/{id}/provenance`."""
    if target_kind not in {"question", "asset"}:
        raise ValueError(f"unknown provenance target kind {target_kind!r}")
    return {f"{target_kind}_id": target_id, "sources": json_copy(list(sources))}


def provenance_coverage_payload(coverage: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """`GET /provenance/coverage`: `complete` is exactly the legacy expression."""
    rows = json_copy(dict(coverage))
    complete = all(row["ratio"] >= 1.0 for row in rows.values())
    return {"coverage": rows, "complete": complete}


def sample_request_valid(count: int | None, marks_target: int | None) -> bool:
    return count is not None or marks_target is not None


def sample_payload(comp: Mapping[str, Any]) -> dict[str, Any]:
    """`POST /sample`: {"marks_total","requested_marks","question_count","questions"}."""
    questions = json_copy(list(comp["questions"]))
    return {"marks_total": comp["marks_total"], "requested_marks": comp["requested_marks"],
            "question_count": len(questions), "questions": questions}


def boards_payload(*, schema_version: Any, auto_detect: Any,
                   boards: Iterable[Any]) -> dict[str, Any]:
    """`GET /api/v1/boards`: {"schema_version","auto_detect","boards"}."""
    return {"schema_version": schema_version, "auto_detect": json_copy(auto_detect),
            "boards": json_copy(list(boards))}


def paper_payload(manifest: Mapping[str, Any], *, board: str,
                  board_source: str) -> dict[str, Any]:
    """`GET /api/v1/paper` JSON branch: `{**payload, "board", "board_source"}`."""
    payload = json_copy(dict(manifest))
    payload.update({"board": board, "board_source": board_source})
    return payload


def legacy_error(status: int, detail: str) -> dict[str, Any]:
    """The FastAPI error body the legacy gateway emits: `{"detail": ...}`.

    `status` is preserved as recorded; A12 never rewrites a legacy
    `200 + ok:false` into another status.
    """
    _require_int("status", status)
    return {"status_code": status, "detail": detail}


def quality_fingerprint(payload: Any) -> dict[str, str]:
    """Every quality-dimension token that appears in a payload, by path.

    Only the seven dimension names defined by the frozen A04 `Quality` model
    are collected, so the fingerprint can be compared without interpreting
    payload semantics.
    """
    found: dict[str, str] = {}

    def walk(node: Any, path: str) -> None:
        if isinstance(node, Mapping):
            for key, value in node.items():
                child = f"{path}/{key}" if path else str(key)
                if key in QUALITY_DIMENSIONS and isinstance(value, str):
                    found[child] = value
                walk(value, child)
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, f"{path}[{index}]")

    walk(payload, "")
    return found


def assert_no_quality_change(before: Any, after: Any) -> Any:
    """Prove a translation left every quality token untouched; return `after`."""
    old = quality_fingerprint(before)
    new = quality_fingerprint(after)
    if old != new:
        raise AssertionError(
            f"translation changed quality tokens: before={old!r} after={new!r}")
    return after
