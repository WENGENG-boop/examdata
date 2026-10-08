# A10 — Isolated v2 API (staged)

Packet A10 of `docs/integration/MASTER_EXECUTION_PLAN_EN.md` §11. Status:
**staged_pass** (staged in `integration-staging/`, not merged, not deployed).
All Phase B gates remain closed.

## 1. Scope

Build the isolated, read-only v2 HTTP surface on top of the frozen staged
contracts (A04), provider registry (A05), read adapters (A07/A08) and catalog
(A09), without importing or running the original application:

- an application factory under the staged package that never imports the
  original `app.py`;
- the plan §5.1 response envelope and §5.2 error map;
- the plan §5.7 limit/cursor pagination, reusing the single frozen A09 cursor
  codec rather than a second implementation;
- the plan §5.4 route inventory — **29 implemented routes**, **5 deferred**
  binary routes (content/crop, staged in A11);
- an OpenAPI document that agrees with the running staged app;
- deferred families (materials, syllabuses, timetables, tags, jobs) served only
  from clearly labelled synthetic fixtures, never fabricated.

Writable roots used: `integration-staging/` and
`docs/integration/execution/`. No original path was read or written.

## 2. Deliverables

Source — `integration-staging/src/examdata_integration/api/`:

| file | role |
| --- | --- |
| `__init__.py` | package docstring; no imports (avoids import cycles) |
| `envelope.py` | §5.1 envelope builders, `ApiError`, `ERROR_MAP`, `EMITTABLE_STATUSES`, `FRAMEWORK_STATUSES`, sanitizers |
| `pagination.py` | `parse_limit`/`parse_int` and `page_items` over the frozen A09 cursor codec |
| `dataset.py` | frozen-fixture dataset, `default_dataset()`, `Dataset`, deferred fixture families |
| `view.py` | `CatalogView` (lookups/filters over catalog entries **and** deferred dict rows) and `ProviderView` (multi-provider dispatch → statuses) |
| `links.py` | `RouteSpec` registry, `PREFIX`, `IMPLEMENTED_SPECS`/`DEFERRED_SPECS`, `advertised()`, `entry_links()` — single source of truth |
| `openapi.py` | recursive route walk (`iter_routes`), `runtime_pairs`, `spec_pairs`, `validate_response`, `agreement_problems` |
| `app.py` | `create_app()` factory, all 29 handlers, request helpers |

Tests — `integration-staging/tests/` (146 new tests):

| file | tests |
| --- | --- |
| `test_api_envelope.py` | 30 |
| `test_api_routes.py` | 53 |
| `test_api_pagination.py` | 21 |
| `test_api_links_openapi.py` | 19 |
| `test_api_dataset.py` | 23 |

Tools — `integration-staging/tools/`: `a10_probe_api.py` (82 offline
scenarios), `a10_final_checks.py`, `a10_close_patch.py`.

Docs/evidence — `docs/integration/execution/`: `A10_REPORT.md`,
`evidence/A10/{api_stdout.txt,pytest_run_stdout.txt,final_checks.txt}`,
ledger patch `integration-staging/runtime/ledger-patches/A10_close.json`.

## 3. API contract

**Envelope** (§5.1). Every response carries `schema_version`
(`examdata.v2/1`), `request_id`, `data`, `meta`
(`dataset_revision`, `retrieved_at`, `pagination`, `completeness`,
`warnings`, `providers`) and `error`. Success sets `error` to `null`; a
non-200 sets `data` to `null`. A caller-supplied `X-Request-ID` is echoed only
when it is safe, otherwise replaced with a generated `req_…` id.

**Error map** (§5.2). `ERROR_MAP` names 200/400/401/403/404/409/410/413/422/429/500/502/503/504;
`EMITTABLE_STATUSES` records the subset Phase A may emit
(`200, 400, 404, 409, 422, 500, 502, 503`). `ApiError` refuses any status
outside the map. A wrong HTTP method is rejected by the framework's own routing
(405) before any handler runs; it is documented as `FRAMEWORK_STATUSES = {405}`
— framework-level, outside the §5.2 map — and still surfaced through the same
envelope.

**Pagination** (§5.7). Default limit 50, maximum 200; a non-numeric limit is
400, an out-of-range limit is 422. A cursor binds query, sort, revision and
last key. A tampered cursor is 400 (`InvalidCursorError`); a cursor whose
revision is no longer published is 409 (`StaleCursorError`). Both are the
frozen A09 codec — there is exactly one cursor implementation in the tree.

**Multi-provider dispatch** (`ProviderView`). Any provider success yields data
(plus `partial` and warnings); **every** provider failing yields an error, never
an empty 200. Map: `unsupported_capability`→422, `unsupported_filter`→422,
`provider_unavailable`→503, `not_found`→404, `provider_failed`→502,
`unknown_provider`/`no_provider_requested`→500.

**Route inventory.** 34 plan §5.4 rows: 29 implemented, 5 deferred
(`syllabuses/{id}/content`, `resources/{id}/content`, `questions/{id}/crop`,
`assets/{id}/content`, `materials/{id}/content` — the binary transport is A11).
`runtime_pairs(app) == spec_pairs(app) == advertised_pairs()` (29 each); the
app is built with `openapi_url=None, docs_url=None, redoc_url=None` so runtime
routes equal exactly the `/api/v2` routes, while `app.openapi()` still builds in
memory. `agreement_problems(app) == []`.

## 4. Evidence

| evidence | label | file |
| --- | --- | --- |
| 82/82 offline probe scenarios pass | `synthetic_fixture` | `evidence/A10/api_stdout.txt` |
| staged suite green: 576 passed, 0 failed | `synthetic_fixture` | `evidence/A10/pytest_run_stdout.txt` |
| closing checks PASS | `static_inspection` + `synthetic_fixture` | `evidence/A10/final_checks.txt` |

What the probe demonstrates (all offline, in-process `TestClient`, no socket):

- route inventory agreement and OpenAPI agreement;
- envelope shape, request-id echo/replacement, error map membership;
- 404 unknown path/identity, 400 bad limit, 422 over-budget limit, 422
  unsupported filter, 405 framework method rejection;
- native identity preserved on container/question detail; container question
  order is the native order (`1, 1(a), 1(b), 2, 3`); catalog public ids are
  authoritative and never the provider's;
- answer conflict kept as two unresolved candidates with `manual_decision`
  null and an `answer_conflict` gap; IELTS `Q41` returns an empty list with a
  `missing_answer_slot` gap (no fabrication); `verification` never `verified`;
- region document hash (`document_sha256`) preserved, `evidence_status`
  `unverified`, `missing_region` gap; IELTS `/regions` is 422
  `unsupported_capability` (the IELTS provider has no REGIONS capability);
- `/audio` never dispatches → 200 with empty list, null association/alignment;
- pagination limit/cursor, no overlap, revision in envelope, stale cursor 409,
  tampered cursor 400;
- deferred families (materials/timetables/syllabuses/tags/jobs) are labelled
  `synthetic_fixture` + `deferred_active_owner` with `completeness unknown` and
  a deferred warning; tags are empty with a `deferred_source` gap;
- coverage never emits a percentage without a known denominator;
- no original path leaks in any payload; filter detail is sanitized.

## 5. Corrections made in this packet

The suite first ran at 566 passed / 10 failed. All ten were resolved; two were
real implementation defects, the rest were probe/test expectation errors against
an already-correct implementation:

1. **405 handler raised** (`app.py`): `_routing_error` built
   `ApiError(405, …)`, which `ApiError.__post_init__` refused because 405 is not
   in the §5.2 map. Fixed by documenting `FRAMEWORK_STATUSES = {405}` in
   `envelope.py` and allowing it in `__post_init__`; 405 stays outside the plan
   map and is described as framework-level.
2. **`view.filter` crashed on dict rows** (`view.py`): `_matches` assumed
   catalog entries (attribute access) but the deferred fixture routes pass plain
   dicts. Fixed with a `_matches_mapping` helper that duck-types `Mapping` rows;
   `filter` now accepts either shape.
3. `tag_questions` returned 404; the route is advertised as implemented, so it
   now answers an explicit deferred envelope (empty items + `deferred_source`
   gap + `completeness unknown`), mirroring `/tags`.
4. Probe/test expectation fixes: `info.systems` lists all five known systems;
   `available`/`deferred` paths are full paths; `limit="x"`→400
   `invalid_limit`, `limit=100000`→422 `limit_exceeded`; container detail exposes
   `native_identity`; answer items expose `conflicts`; `/tags/{id}/questions`
   path; stale cursor built with the frozen `make_cursor` (not by string
   substitution, which would instead trip the 400 tamper check);
   `entry_links` hrefs are compared after substituting `{id}`.
5. Dead code removed: the unused `filters` parameter of `_list_response` and the
   unused `_filters` helper.

## 6. Deliberate limitations

- **Deferred binary routes.** The five `/content` and `/crop` routes are not
  registered and are not advertised as links; `links.DEFERRED_SPECS` records
  each with a `deferred_reason`. A11 implements range/ETag/budget behaviour.
- **Resources and assets are one entity.** `/resources`, `/resources/{id}` and
  `/assets/{id}` are views of the catalog `asset` kind. The plan's resource
  roles (QP/MS/ER/GT/insert/audio) are not modelled by the frozen fixtures.
- **Deferred families are synthetic.** Materials, syllabuses, timetables and
  jobs are served from labelled fixtures; tags have no staged source at all
  (empty list + `deferred_source`). Active materials/timetable integration is
  deferred to the active owner.
- **Two UNKNOWN encodings.** Catalog dicts use `"__unknown__"`
  (`UNKNOWN_TOKEN`); contract models use `"unknown"` (`plain()`). Both are
  permitted by the plan ("unknown values remain null or explicitly unknown");
  they were not unified because that would require editing the closed A09
  `to_dict`.
- **405 is framework-level**, outside the §5.2 map (see §3).
- **`/info` lists all five known systems**, including the unavailable
  `gaokao`/`toefl`, so discovery is honest about scope rather than hiding a
  known system.

## 7. Remaining gaps

- Binary transport, range requests, ETag/If-Range, response budgets, temp-file
  cleanup and disconnect handling are A11.
- Legacy 71-route compatibility is A12; the frontend proposal is A13; the
  file-by-file merge map is A14; `PHASE_A_REPORT.md` is A15.
- No real data is served: the dataset is built from the frozen synthetic
  fixtures, so every route reports `synthetic_fixture` evidence.
- The staged API is not the production service and is not deployed; the live
  database, service restart, upstream crawl and CIE batch resume are Phase B and
  require explicit human release.

## 8. Next action

A11 — binary responses: implement the five deferred content/crop routes with
200/206/416 range handling and response budgets, path-traversal and
drive/UNC-path rejection, wrong-media-type handling, disconnect and temp-file
cleanup, using small immutable synthetic or copied samples; then flip the five
`DEFERRED_SPECS` rows to implemented and re-run the staged suite and probe.
