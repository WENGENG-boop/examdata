"""The isolated v2 application factory (plan 5, A10).

`create_app()` builds a FastAPI application from a :class:`Dataset` (the fixture
catalog snapshot plus the provider registry). It imports no original application
module and reads no original data root.

Design rules enforced here:

* every JSON response is the plan 5.1 envelope, built by `envelope.py`;
* the only non-200 path is :class:`ApiError`, so a status always comes from the
  plan 5.2 map (framework routing may still answer 405 for a wrong method);
* only the routes `links.IMPLEMENTED_SPECS` lists are registered;
* the five binary rows stream verified fixture samples with RFC 9110 Range and
  If-None-Match semantics (200/206/304, HEAD supported), answer 413/416 through
  the same envelope, and can only be reached for an entity whose verified
  sample actually exists;
* query parameters are the route's filter allowlist: anything else is a 422,
  never silently ignored (plan 5.7);
* a provider failure is never an empty 200 (plan 5.2).
"""
from __future__ import annotations

import re
import secrets
from datetime import datetime, timezone
from typing import Any, Mapping

from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response, StreamingResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .. import __version__ as PACKAGE_VERSION
from ..providers.capabilities import Capability
from . import links
from .binary import (
    UNSATISFIABLE,
    BudgetExceeded,
    ByteRange,
    ContentStore,
    if_none_match_matches,
    iter_crop_copy,
    iter_range,
    iter_sample,
    parse_range_header,
)
from .dataset import (
    FIXTURE_ROOT,
    MATERIAL_FIXTURES,
    SYLLABUS_FIXTURES,
    TIMETABLE_EVENT_FIXTURES,
    TIMETABLE_SEASON_FIXTURES,
    TIMETABLE_WINDOW_FIXTURES,
    Dataset,
    default_dataset,
    deferred_fixtures,
)
from .envelope import SCHEMA_VERSION, ApiError, error_envelope, ok_envelope
from .openapi import BINARY_ROUTE_RESPONSES, ROUTE_RESPONSES
from .pagination import page_items, parse_limit
from .view import CatalogView, ProviderView

SERVICE_NAME = "examdata-v2-staged"

_DEFERRED_WARNING = (
    "staged synthetic fixture: this family is owned by the active project owner "
    "and its real integration is deferred to Phase B")

_NO_AUDIO_WARNING = (
    "the Phase A synthetic fixtures carry no audio; no association or alignment "
    "is claimed")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _request_id(request: Request | None) -> str:
    supplied = request.headers.get("x-request-id") if request is not None else None
    if supplied and 0 < len(supplied) <= 64 and all(
            c.isalnum() or c in "-_." for c in supplied):
        return supplied
    return "req_" + secrets.token_hex(8)


def _unique_gaps(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        key = "|".join(str(row.get(k, "")) for k in ("code", "scope", "ref", "detail"))
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def _gap_key(row: Mapping[str, Any]) -> str:
    return "|".join(str(row.get(k, "")) for k in ("code", "scope", "ref", "detail"))


def _deterministic_unique_id(route: Any) -> str:
    """Stable operation ids for routes registered with more than one method.

    FastAPI's default generator picks ``next(iter(route.methods))`` from a set,
    so a route registered for GET and HEAD gets a different operation id in
    every interpreter process. Sorting the methods makes the OpenAPI document
    reproducible, which the staged contract (and the A14 regeneration check)
    depends on.
    """
    name = re.sub(r"\W", "_", f"{route.name}{route.path_format}")
    methods = sorted(route.methods or [])
    return f"{name}_{methods[0].lower()}" if methods else name


def create_app(*, dataset: Dataset | None = None,
               content_store: ContentStore | None = None) -> FastAPI:
    """Build the staged v2 application. No global state; safe to build many."""
    ds = dataset if dataset is not None else default_dataset()
    store = content_store if content_store is not None else default_content_store()
    view = CatalogView(ds)
    providers = ProviderView(ds)

    app = FastAPI(
        title="ExamData staged v2 API (Phase A)",
        version=PACKAGE_VERSION,
        description=(
            "Isolated Phase A application factory. JSON responses are the "
            "examdata.v2/1 envelope. Every plan 5.4 route is registered; the "
            "five binary content/crop rows stream verified synthetic fixture "
            "samples (200/206/304) and use the same error envelope for 413/416."),
        openapi_url=None,
        docs_url=None,
        redoc_url=None,
        generate_unique_id_function=_deterministic_unique_id,
    )
    app.state.dataset = ds
    app.state.catalog_view = view
    app.state.content_store = store
    router = APIRouter(prefix=links.PREFIX)

    # -- envelope plumbing ---------------------------------------------------- #
    def _revision() -> str:
        return ds.revision

    def ok(request: Request, data: Any, *, limit: int | None = None,
           next_cursor: str | None = None, completeness: str = "complete",
           warnings: Any = (), providers_meta: Any = ()) -> JSONResponse:
        payload = ok_envelope(
            request_id=_request_id(request), data=data,
            dataset_revision=_revision(), retrieved_at=_now(),
            limit=limit, next_cursor=next_cursor, completeness=completeness,
            warnings=warnings, providers=providers_meta)
        return JSONResponse(payload)

    def fail(request: Request | None, error: ApiError) -> JSONResponse:
        payload = error_envelope(request_id=_request_id(request), error=error,
                                 dataset_revision=_revision(), retrieved_at=_now())
        return JSONResponse(payload, status_code=error.status, headers=error.headers)

    def _read_route(path: str, *, responses: Mapping[str, Any]) -> Any:
        """Register GET and HEAD as two routes sharing one endpoint.

        FastAPI derives a single operation id per route and uses it for every
        method the route accepts, so one route registered for GET and HEAD
        would publish the same operation id twice. Two routes keep both
        documented operations and give each a unique, deterministic id.
        """
        def decorate(endpoint: Any) -> Any:
            for method in ("GET", "HEAD"):
                router.api_route(path, methods=[method], responses=responses)(endpoint)
            return endpoint
        return decorate

    @app.exception_handler(ApiError)
    async def _api_error(request: Request, exc: ApiError) -> JSONResponse:
        return fail(request, exc)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return fail(request, ApiError(400, "invalid_request",
                                      "the request could not be parsed"))

    @app.exception_handler(StarletteHTTPException)
    async def _routing_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        status = exc.status_code if exc.status_code in (404, 405) else 500
        code = "route_not_found" if status == 404 else "method_not_allowed"
        message = ("no v2 route matches this path" if status == 404
                   else "this v2 route does not accept that HTTP method")
        payload = error_envelope(request_id=_request_id(request),
                                 error=ApiError(status, code, message),
                                 dataset_revision=_revision(), retrieved_at=_now())
        return JSONResponse(payload, status_code=status)

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, exc: Exception) -> JSONResponse:
        return fail(request, ApiError(500, "internal_error",
                                      "unexpected internal error"))

    # -- request helpers ------------------------------------------------------ #
    def _split(request: Request) -> tuple[int, str | None, dict[str, Any]]:
        raw = {k: v for k, v in request.query_params.items()}
        limit = parse_limit(raw.pop("limit", None))
        cursor = raw.pop("cursor", None)
        return limit, cursor, raw

    def _list_response(request: Request, items: list[Any], *,
                       allowed: frozenset[str], sort: str,
                       key=lambda item: str(item), item_of=lambda item: item,
                       warnings: Any = (), providers_meta: Any = (),
                       completeness: str | None = None) -> JSONResponse:
        limit, cursor, raw = _split(request)
        selected = view.filter(items, raw, allowed=allowed) if allowed or raw else items
        query = {k: v for k, v in raw.items()}
        window, next_cursor = page_items(
            selected, limit=limit, cursor=cursor, query=query, sort=sort,
            revision=_revision(), available_revisions=ds.available_revisions, key=key)
        if completeness is None:
            completeness = "empty" if not window else "complete"
        return ok(request, {"items": [item_of(item) for item in window]},
                  limit=limit, next_cursor=next_cursor, completeness=completeness,
                  warnings=warnings, providers_meta=providers_meta)

    # -- binary transport (plan 5.3) ------------------------------------------ #
    def _no_query(request: Request) -> None:
        if request.query_params:
            raise ApiError(422, "unsupported_filter",
                           f"filter(s) {sorted(request.query_params)} are not "
                           "supported here")

    def _binary_headers(request: Request, sample, *, filename: str,
                        length: int | None = None,
                        extra: Mapping[str, str] | None = None) -> dict[str, str]:
        """The staged binary headers; ``length=None`` omits content-length."""
        headers: dict[str, str] = {
            "content-type": sample.media_type,
            "accept-ranges": "bytes",
            "etag": sample.etag,
            "x-content-sha256": sample.sha256,
            "content-disposition": f'inline; filename="{filename}"',
            "x-request-id": _request_id(request),
            "x-dataset-revision": _revision(),
            "x-evidence": "synthetic_fixture",
        }
        if length is not None:
            headers["content-length"] = str(length)
        if extra:
            headers.update(extra)
        return headers

    def _sample_response(request: Request, sample, *, filename: str,
                         crop: bool = False,
                         extra: Mapping[str, str] | None = None) -> Response:
        """Serve one verified sample: 200/206/304, or 413/416 via ApiError."""
        try:
            store.enforce_budget(sample, crop=crop)
        except BudgetExceeded as exc:
            raise ApiError(413, exc.code,
                           f"the sample is {exc.actual} bytes and exceeds the "
                           f"staged budget of {exc.limit} bytes",
                           details={"limit": exc.limit,
                                    "byte_size": exc.actual}) from exc
        if if_none_match_matches(request.headers.get("if-none-match"), sample.etag):
            return Response(status_code=304,
                            headers=_binary_headers(request, sample,
                                                    filename=filename, extra=extra))
        if request.method == "HEAD":
            return Response(status_code=200,
                            headers=_binary_headers(request, sample,
                                                    filename=filename,
                                                    length=sample.byte_size,
                                                    extra=extra))
        parsed = parse_range_header(request.headers.get("range"), sample.byte_size)
        if parsed is UNSATISFIABLE:
            raise ApiError(416, "range_not_satisfiable",
                           f"the byte range is unsatisfiable for a "
                           f"{sample.byte_size}-byte entity",
                           headers={"content-range": f"bytes */{sample.byte_size}",
                                    "accept-ranges": "bytes", "etag": sample.etag})
        if isinstance(parsed, ByteRange):
            headers = _binary_headers(request, sample, filename=filename,
                                      length=parsed.length, extra=extra)
            headers["content-range"] = (f"bytes {parsed.start}-{parsed.end}"
                                        f"/{sample.byte_size}")
            if crop:
                stream = iter_crop_copy(sample, temp_root=store.temp_root,
                                        byte_range=parsed)
            else:
                stream = iter_range(sample, parsed.start, parsed.end)
            return StreamingResponse(stream, status_code=206, headers=headers)
        if crop:
            stream = iter_crop_copy(sample, temp_root=store.temp_root)
        else:
            stream = iter_sample(sample)
        return StreamingResponse(
            stream, status_code=200,
            headers=_binary_headers(request, sample, filename=filename,
                                    length=sample.byte_size, extra=extra))

    # -- info / discovery ----------------------------------------------------- #
    @router.get(links.spec_for("info").path, responses=ROUTE_RESPONSES)
    def info(request: Request) -> JSONResponse:
        data = {
            "service": {"name": SERVICE_NAME, "version": PACKAGE_VERSION},
            "schema_version": SCHEMA_VERSION,
            "dataset_revision": ds.revision,
            "counts": dict(ds.snapshot.counts),
            "systems": [row["system"] for row in ds.systems()],
            "capabilities": {
                "available": links.advertised(),
                "deferred": links.deferred(),
            },
            "evidence": ds.evidence,
            "error_map": {str(k): v for k, v in sorted(_error_map().items())},
        }
        return ok(request, data,
                  providers_meta=[d.provider_id for d in ds.registry.descriptors()])

    @router.get(links.spec_for("exam-systems").path, responses=ROUTE_RESPONSES)
    def exam_systems(request: Request) -> JSONResponse:
        return ok(request, {"items": ds.systems()})

    @router.get(links.spec_for("providers").path, responses=ROUTE_RESPONSES)
    def provider_list(request: Request) -> JSONResponse:
        items = []
        for descriptor in ds.registry.descriptors():
            row = dict(descriptor.to_dict())
            row["aliases"] = ds.registry.aliases_for(descriptor.provider_id)
            row["capabilities"] = sorted(c.value for c in descriptor.capabilities)
            row["evidence"] = ds.evidence
            items.append(row)
        return ok(request, {"items": items},
                  providers_meta=[d.provider_id for d in ds.registry.descriptors()])

    # -- courses -------------------------------------------------------------- #
    _COURSE_FILTERS = frozenset({"system", "qualification", "query", "specification_version"})

    @router.get(links.spec_for("courses.list").path, responses=ROUTE_RESPONSES)
    def courses(request: Request) -> JSONResponse:
        entries = view.entries("course")
        return _list_response(request, entries, allowed=_COURSE_FILTERS,
                              sort="public_id",
                              key=lambda e: e.public_id,
                              item_of=_course_payload)

    @router.get(links.spec_for("courses.get").path, responses=ROUTE_RESPONSES)
    def course_detail(request: Request, id: str) -> JSONResponse:
        entry = view.require(id, "course")
        return ok(request, {"item": _course_payload(entry),
                            "links": links.entry_links("course", entry.public_id)})

    def _course_payload(entry) -> dict[str, Any]:
        return {
            "public_id": entry.public_id,
            "system": entry.system,
            "qualification": entry.identity_fields.get("qualification"),
            "native_code": entry.identity_fields.get("native_code"),
            "specification_version": entry.identity_fields.get("specification_version"),
            "names": entry.searchable.get("names", []),
            "aliases": list(entry.aliases),
            "availability": "available",
            "evidence": entry.evidence_labels,
            "links": links.entry_links("course", entry.public_id),
        }

    # -- syllabuses (deferred, labelled fixture) ------------------------------- #
    _SYLLABUS_FILTERS = frozenset({"system", "course_native_code", "version", "query"})

    @router.get(links.spec_for("syllabuses.list").path, responses=ROUTE_RESPONSES)
    def syllabuses(request: Request) -> JSONResponse:
        rows = list(SYLLABUS_FIXTURES)
        return _list_response(request, rows, allowed=_SYLLABUS_FILTERS,
                              sort="public_id", key=lambda r: r["public_id"],
                              warnings=[_DEFERRED_WARNING], completeness="unknown")

    @router.get(links.spec_for("syllabuses.get").path, responses=ROUTE_RESPONSES)
    def syllabus_detail(request: Request, id: str) -> JSONResponse:
        row = next((r for r in SYLLABUS_FIXTURES if r["public_id"] == id), None)
        if row is None:
            raise ApiError(404, "not_found", f"no syllabus matches {id!r}")
        return ok(request, {"item": row}, warnings=[_DEFERRED_WARNING],
                  completeness="unknown")

    @_read_route(links.spec_for("syllabuses.content").path,
                 responses=BINARY_ROUTE_RESPONSES["syllabuses.content"])
    def syllabus_content(request: Request, id: str) -> Response:
        _no_query(request)
        if not any(r["public_id"] == id for r in SYLLABUS_FIXTURES):
            raise ApiError(404, "not_found", f"no syllabus matches {id!r}")
        sample = store.for_syllabus(id)
        if sample is None:
            raise ApiError(404, "content_not_available",
                           f"syllabus {id!r} has no staged content sample")
        return _sample_response(request, sample,
                                filename=f"{id}.{sample.extension}")

    # -- containers ----------------------------------------------------------- #
    _CONTAINER_FILTERS = frozenset({"system", "kind", "query", "revision"})

    @router.get(links.spec_for("containers.list").path, responses=ROUTE_RESPONSES)
    def containers(request: Request) -> JSONResponse:
        entries = view.entries("container")
        return _list_response(request, entries, allowed=_CONTAINER_FILTERS,
                              sort="public_id", key=lambda e: e.public_id,
                              item_of=_container_payload)

    @router.get(links.spec_for("containers.get").path, responses=ROUTE_RESPONSES)
    def container_detail(request: Request, id: str) -> JSONResponse:
        entry = view.require(id, "container")
        return ok(request, {"item": _container_payload(entry)})

    def _container_payload(entry) -> dict[str, Any]:
        return {
            "public_id": entry.public_id,
            "system": entry.system,
            "kind": entry.kind,
            "native_identity": entry.identity_fields.get("native_identity"),
            "sections": entry.searchable.get("sections", []),
            "resources": entry.searchable.get("resources", []),
            "question_refs": list(entry.searchable.get("question_refs", [])),
            "revision": entry.source_revision,
            "coverage": entry.searchable.get("coverage"),
            "quality": dict(entry.quality_summary),
            "content_class": entry.content_class,
            "evidence": entry.evidence_labels,
            "links": links.entry_links("container", entry.public_id),
        }

    @router.get(links.spec_for("containers.resources").path, responses=ROUTE_RESPONSES)
    def container_resources(request: Request, id: str) -> JSONResponse:
        entry = view.require(id, "container")
        by_sha = ds.asset_by_sha()
        items, gaps = [], []
        for ref in entry.searchable.get("resources", []):
            sha = ref.get("sha256") if isinstance(ref, Mapping) else None
            asset = by_sha.get(sha)
            if asset is None:
                gaps.append({"code": "missing_required_image", "scope": "asset",
                             "detail": f"resource role={ref.get('role')!r} is referenced "
                                       f"by hash but no catalog asset carries that hash",
                             "ref": sha})
                continue
            row = _asset_payload(asset)
            row["role"] = ref.get("role")
            items.append(row)
        return ok(request, {"items": items, "gaps": gaps})

    @router.get(links.spec_for("containers.questions").path, responses=ROUTE_RESPONSES)
    def container_questions(request: Request, id: str) -> JSONResponse:
        view.require(id, "container")
        entries = view.questions_for_container(id)
        entries.sort(key=lambda e: (list(e.identity_fields.get("number_path") or []),
                                    e.public_id))
        return _list_response(request, entries, allowed=frozenset(),
                              sort="number_path", key=lambda e: e.public_id,
                              item_of=_question_payload)

    # -- resources / assets ---------------------------------------------------- #
    _RESOURCE_FILTERS = frozenset({"system", "media_type", "query"})

    @router.get(links.spec_for("resources.list").path, responses=ROUTE_RESPONSES)
    def resources(request: Request) -> JSONResponse:
        entries = view.entries("asset")
        return _list_response(request, entries, allowed=_RESOURCE_FILTERS,
                              sort="public_id", key=lambda e: e.public_id,
                              item_of=_asset_payload)

    @router.get(links.spec_for("resources.get").path, responses=ROUTE_RESPONSES)
    def resource_detail(request: Request, id: str) -> JSONResponse:
        entry = view.require(id, "asset")
        return ok(request, {"item": _asset_payload(entry)})

    @router.get(links.spec_for("assets.get").path, responses=ROUTE_RESPONSES)
    def asset_detail(request: Request, id: str) -> JSONResponse:
        entry = view.require(id, "asset")
        return ok(request, {"item": _asset_payload(entry)})

    @_read_route(links.spec_for("resources.content").path,
                 responses=BINARY_ROUTE_RESPONSES["resources.content"])
    def resource_content(request: Request, id: str) -> Response:
        return _asset_content(request, id)

    @_read_route(links.spec_for("assets.content").path,
                 responses=BINARY_ROUTE_RESPONSES["assets.content"])
    def asset_content(request: Request, id: str) -> Response:
        return _asset_content(request, id)

    def _asset_content(request: Request, id: str) -> Response:
        _no_query(request)
        entry = view.require(id, "asset")
        sample = store.for_asset(entry.system, entry.identity_fields.get("sha256"))
        if sample is None:
            raise ApiError(404, "content_not_available",
                           f"asset {id!r} has no staged content sample")
        return _sample_response(request, sample,
                                filename=f"{id}.{sample.extension}")

    def _asset_payload(entry) -> dict[str, Any]:
        sample = store.for_asset(entry.system, entry.identity_fields.get("sha256"))
        row: dict[str, Any] = {
            "public_id": entry.public_id,
            "system": entry.system,
            "media_type": entry.identity_fields.get("media_type"),
            "sha256": entry.identity_fields.get("sha256"),
            "storage_mode": entry.identity_fields.get("storage_mode"),
            "byte_size": entry.searchable.get("byte_size"),
            "availability": "unknown",
            "range_capable": None,
            "content_link": None,
            "content_available": False,
            "evidence": entry.evidence_labels,
            "links": links.entry_links("asset", entry.public_id),
        }
        if sample is not None:
            row["availability"] = "fixture"
            row["range_capable"] = True
            row["content_available"] = True
            row["content_link"] = f"{links.PREFIX}/assets/{entry.public_id}/content"
            row["content"] = {
                "media_type": sample.media_type,
                "byte_size": sample.byte_size,
                "sha256": sample.sha256,
                "declared_sha256": sample.declared_sha256,
                "etag": sample.etag,
                "evidence": "synthetic_fixture",
            }
            row["links"] = links.entry_links("asset", entry.public_id,
                                             content_available=True)
        return row

    # -- questions ------------------------------------------------------------- #
    _QUESTION_FILTERS = frozenset({"system", "question_type", "query", "container_ref"})

    @router.get(links.spec_for("questions.list").path, responses=ROUTE_RESPONSES)
    def questions(request: Request) -> JSONResponse:
        entries = view.entries("question")
        return _list_response(request, entries, allowed=_QUESTION_FILTERS,
                              sort="public_id", key=lambda e: e.public_id,
                              item_of=_question_payload)

    @router.get(links.spec_for("questions.get").path, responses=ROUTE_RESPONSES)
    def question_detail(request: Request, id: str) -> JSONResponse:
        entry = view.require(id, "question")
        return ok(request, {"item": _question_payload(entry),
                            "gaps": _question_gaps(entry)})

    def _question_payload(entry) -> dict[str, Any]:
        return {
            "public_id": entry.public_id,
            "system": entry.system,
            "native_id": entry.identity_fields.get("native_id"),
            "number_path": list(entry.identity_fields.get("number_path") or []),
            "parent_native_id": entry.identity_fields.get("parent_native_id"),
            "container_native_identity": entry.identity_fields.get("container_native_identity"),
            "container_ref": entry.container_ref,
            "question_type": entry.searchable.get("question_type"),
            "stem": entry.searchable.get("stem"),
            "quality": dict(entry.quality_summary),
            "content_class": entry.content_class,
            "evidence": entry.evidence_labels,
            "links": links.entry_links(
                "question", entry.public_id,
                crop_available=store.crop_for(
                    entry.system, view.native_id(entry)) is not None),
        }

    def _question_gaps(entry) -> list[dict[str, Any]]:
        gaps: list[dict[str, Any]] = []
        quality = entry.quality_summary
        if quality.get("answer_presence") == "missing":
            gaps.append({"code": "missing_answer_slot", "scope": "question",
                         "detail": "the answer slot is absent and is preserved as a gap",
                         "ref": entry.public_id})
        if quality.get("answer_verification") == "conflicting":
            gaps.append({"code": "answer_conflict", "scope": "answer",
                         "detail": "candidate answers disagree with no manual decision",
                         "ref": entry.public_id})
        elif quality.get("answer_verification") in ("unverified", "unknown"):
            gaps.append({"code": "unverified_content", "scope": "question",
                         "detail": f"answer verification is "
                                   f"{quality.get('answer_verification')!r}",
                         "ref": entry.public_id})
        return gaps

    @router.get(links.spec_for("questions.answers").path, responses=ROUTE_RESPONSES)
    def question_answers(request: Request, id: str) -> JSONResponse:
        entry = view.require(id, "question")
        limit, cursor, raw = _split(request)
        if raw:
            raise ApiError(422, "unsupported_filter",
                           f"filter(s) {sorted(raw)} are not supported here")
        result = providers.dispatch(Capability.ANSWERS, system=entry.system,
                                    target=view.native_id(entry))
        return ok(request, {"items": result["items"], "gaps": result["gaps"]},
                  completeness=result["completeness"], warnings=result["warnings"],
                  providers_meta=result["providers"])

    @router.get(links.spec_for("questions.regions").path, responses=ROUTE_RESPONSES)
    def question_regions(request: Request, id: str) -> JSONResponse:
        entry = view.require(id, "question")
        limit, cursor, raw = _split(request)
        if raw:
            raise ApiError(422, "unsupported_filter",
                           f"filter(s) {sorted(raw)} are not supported here")
        result = providers.dispatch(Capability.REGIONS, system=entry.system,
                                    target=view.native_id(entry))
        return ok(request, {"items": result["items"], "gaps": result["gaps"]},
                  completeness=result["completeness"], warnings=result["warnings"],
                  providers_meta=result["providers"])

    @_read_route(links.spec_for("questions.crop").path,
                 responses=BINARY_ROUTE_RESPONSES["questions.crop"])
    def question_crop(request: Request, id: str) -> Response:
        _no_query(request)
        entry = view.require(id, "question")
        result = providers.dispatch(Capability.REGIONS, system=entry.system,
                                    target=view.native_id(entry))
        regions = result["items"]
        if not regions:
            raise ApiError(404, "region_not_found",
                           "the registry reports no region for this question")
        region = regions[0]
        sample = store.crop_for(entry.system, view.native_id(entry))
        if sample is None:
            raise ApiError(404, "crop_not_available",
                           f"question {id!r} has no staged crop sample")
        if getattr(region, "document_sha256", None) != sample.declared_sha256:
            raise ApiError(409, "hash_conflict",
                           "the region's document hash disagrees with the staged crop")
        if getattr(region, "page", None) != sample.page:
            raise ApiError(409, "region_conflict",
                           "the region's page disagrees with the staged crop")
        return _sample_response(
            request, sample, crop=True, filename=f"{id}.png",
            extra={"x-document-sha256": str(sample.declared_sha256),
                   "x-page": str(sample.page)})

    @router.get(links.spec_for("questions.audio").path, responses=ROUTE_RESPONSES)
    def question_audio(request: Request, id: str) -> JSONResponse:
        view.require(id, "question")
        limit, cursor, raw = _split(request)
        if raw:
            raise ApiError(422, "unsupported_filter",
                           f"filter(s) {sorted(raw)} are not supported here")
        return ok(request, {"items": [], "association": None, "alignment": None},
                  completeness="unknown", warnings=[_NO_AUDIO_WARNING])

    # -- tags (deferred) ------------------------------------------------------- #
    @router.get(links.spec_for("tags.list").path, responses=ROUTE_RESPONSES)
    def tags(request: Request) -> JSONResponse:
        limit, cursor, raw = _split(request)
        if raw:
            raise ApiError(422, "unsupported_filter",
                           f"filter(s) {sorted(raw)} are not supported here")
        return ok(request, {"items": [], "gaps": [{
            "code": "deferred_source", "scope": "system",
            "detail": "tag schemes are not staged in Phase A"}]},
            completeness="unknown", warnings=[_DEFERRED_WARNING])

    @router.get(links.spec_for("tags.questions").path, responses=ROUTE_RESPONSES)
    def tag_questions(request: Request, id: str) -> JSONResponse:
        limit, cursor, raw = _split(request)
        if raw:
            raise ApiError(422, "unsupported_filter",
                           f"filter(s) {sorted(raw)} are not supported here")
        return ok(request, {"items": [], "gaps": [{
            "code": "deferred_source", "scope": "tag_scheme",
            "detail": f"tag scheme {id!r} is not staged in Phase A; "
                      "no question or answer link is claimed"}]},
            completeness="unknown", warnings=[_DEFERRED_WARNING])

    # -- materials / timetables (deferred, labelled fixture) -------------------- #
    _MATERIAL_FILTERS = frozenset({"system", "kind", "query"})

    @router.get(links.spec_for("materials.list").path, responses=ROUTE_RESPONSES)
    def materials(request: Request) -> JSONResponse:
        rows = list(MATERIAL_FIXTURES)
        return _list_response(request, rows, allowed=_MATERIAL_FILTERS,
                              sort="public_id", key=lambda r: r["public_id"],
                              warnings=[_DEFERRED_WARNING], completeness="unknown")

    @router.get(links.spec_for("materials.get").path, responses=ROUTE_RESPONSES)
    def material_detail(request: Request, id: str) -> JSONResponse:
        row = next((r for r in MATERIAL_FIXTURES if r["public_id"] == id), None)
        if row is None:
            raise ApiError(404, "not_found", f"no material matches {id!r}")
        return ok(request, {"item": row}, warnings=[_DEFERRED_WARNING],
                  completeness="unknown")

    @_read_route(links.spec_for("materials.content").path,
                 responses=BINARY_ROUTE_RESPONSES["materials.content"])
    def material_content(request: Request, id: str) -> Response:
        _no_query(request)
        if not any(r["public_id"] == id for r in MATERIAL_FIXTURES):
            raise ApiError(404, "not_found", f"no material matches {id!r}")
        sample = store.for_material(id)
        if sample is None:
            raise ApiError(404, "content_not_available",
                           f"material {id!r} has no staged content sample")
        return _sample_response(request, sample,
                                filename=f"{id}.{sample.extension}")

    @router.get(links.spec_for("timetables.list").path, responses=ROUTE_RESPONSES)
    def timetables(request: Request) -> JSONResponse:
        limit, cursor, raw = _split(request)
        if raw:
            raise ApiError(422, "unsupported_filter",
                           f"filter(s) {sorted(raw)} are not supported here")
        return ok(request, {"seasons": list(TIMETABLE_SEASON_FIXTURES),
                            "availability": "unavailable"},
                  completeness="unknown", warnings=[_DEFERRED_WARNING])

    _EVENT_FILTERS = frozenset({"system", "qualification", "zone", "date", "component",
                                "session", "course_native_code"})

    @router.get(links.spec_for("timetables.events").path, responses=ROUTE_RESPONSES)
    def timetable_events(request: Request) -> JSONResponse:
        rows = list(TIMETABLE_EVENT_FIXTURES)
        return _list_response(
            request, rows, allowed=_EVENT_FILTERS, sort="public_id",
            key=lambda r: "|".join(str(r.get(k, "")) for k in
                                   ("system", "zone", "course_native_code", "component", "date")),
            warnings=[_DEFERRED_WARNING], completeness="unknown")

    _WINDOW_FILTERS = frozenset({"system", "qualification", "zone"})

    @router.get(links.spec_for("timetables.windows").path, responses=ROUTE_RESPONSES)
    def timetable_windows(request: Request) -> JSONResponse:
        rows = list(TIMETABLE_WINDOW_FIXTURES)
        return _list_response(
            request, rows, allowed=_WINDOW_FILTERS, sort="public_id",
            key=lambda r: "|".join(str(r.get(k, "")) for k in
                                   ("system", "zone", "original_text")),
            warnings=[_DEFERRED_WARNING], completeness="unknown")

    # -- coverage / gaps ------------------------------------------------------- #
    @router.get(links.spec_for("coverage.get").path, responses=ROUTE_RESPONSES)
    def coverage(request: Request) -> JSONResponse:
        limit, cursor, raw = _split(request)
        if raw:
            raise ApiError(422, "unsupported_filter",
                           f"filter(s) {sorted(raw)} are not supported here")
        result = providers.dispatch(Capability.COVERAGE, system=None,
                                    require_system=False)
        return ok(request, {"items": result["items"], "gaps": result["gaps"]},
                  completeness=result["completeness"], warnings=result["warnings"],
                  providers_meta=result["providers"])

    _GAP_FILTERS = frozenset({"code", "scope", "system"})

    @router.get(links.spec_for("gaps.list").path, responses=ROUTE_RESPONSES)
    def gaps(request: Request) -> JSONResponse:
        rows: list[dict[str, Any]] = []
        for record in ds.snapshot.problems:
            row = dict(record)
            row.setdefault("system", None)
            row["source"] = "catalog"
            rows.append(row)
        rows.append({"code": "deferred_source", "scope": "system",
                     "detail": "tag schemes are not staged in Phase A",
                     "source": "api"})
        for capability in (Capability.QUESTIONS, Capability.COVERAGE):
            for result in ds.registry.dispatch(capability).results:
                for gap in result.gaps:
                    row = dict(gap.to_dict())
                    row.pop("schema", None)
                    row["system"] = None
                    row["source"] = result.provider_id
                    rows.append(row)
        unique = _unique_gaps(rows)
        unique.sort(key=_gap_key)
        return _list_response(request, unique, allowed=_GAP_FILTERS,
                              sort="gap_key", key=_gap_key)

    # -- jobs ------------------------------------------------------------------ #
    @router.get(links.spec_for("jobs.get").path, responses=ROUTE_RESPONSES)
    def job_detail(request: Request, id: str) -> JSONResponse:
        row = deferred_fixtures()["jobs"].get(id)
        if row is None:
            raise ApiError(404, "not_found", f"no job {id!r} is recorded")
        return ok(request, {"item": row}, warnings=[_DEFERRED_WARNING],
                  completeness="unknown")

    _framework_openapi = app.openapi

    def _staged_openapi() -> dict[str, Any]:
        """The framework document, with the binary rows' real media only.

        FastAPI merges a default ``application/json`` entry into every
        operation's 200 response; the binary rows never serve a JSON body, so
        the staged document drops it and documents the fixture media alone.
        """
        document = _framework_openapi()
        for row in links.ROUTE_SPECS:
            if not row.binary:
                continue
            for method in ("get", "head"):
                operation = document.get("paths", {}).get(row.full_path, {}).get(method)
                if not operation:
                    continue
                for code in ("200", "206"):
                    content = operation.get("responses", {}).get(code, {}).get("content")
                    if content:
                        content.pop("application/json", None)
        return document

    app.openapi = _staged_openapi
    app.include_router(router)
    return app


def default_content_store() -> ContentStore:
    """The staged binary fixture store, rooted in fixtures/synthetic/binary."""
    root = FIXTURE_ROOT / "binary"
    return ContentStore(root, root / "manifest.json")


def _error_map() -> dict[int, str]:
    from .envelope import ERROR_MAP
    return ERROR_MAP


__all__ = ["create_app", "default_content_store", "SERVICE_NAME"]
