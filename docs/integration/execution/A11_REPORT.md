# A11 — Binary responses: content, crops, ranges (staged)

Packet A11 of `docs/integration/MASTER_EXECUTION_PLAN_EN.md` §11. Status:
**staged_pass** (staged in `integration-staging/`, not merged, not deployed).
All Phase B gates remain closed.

## 1. Scope

Flip the five deferred §5.4 binary routes to implemented with real byte
transport, still entirely inside the staged tree:

- `GET/HEAD /api/v2/syllabuses/{id}/content` — controlled syllabus retrieval;
- `GET/HEAD /api/v2/resources/{id}/content` — catalog asset alias;
- `GET/HEAD /api/v2/assets/{id}/content` — verified asset bytes;
- `GET/HEAD /api/v2/questions/{id}/crop` — question-crop PNG with provenance;
- `GET/HEAD /api/v2/materials/{id}/content` — labelled synthetic material.

Contract §5.3 requirements addressed: actual bytes with no JSON wrapper;
content type, safe content disposition, request ID, revision and validated
ETag/hash metadata; Range only with real 206/416 semantics; HEAD defined and
tested; streaming with total byte limits; temporary-file cleanup on
completion and early close; no arbitrary filesystem paths.

Private fixtures only: a deterministic generator renders 11 small synthetic
PDF/PNG samples plus `manifest.json` and `PROVENANCE.json` (13 files);
`--check` re-renders in memory and writes nothing.

Writable roots used: `integration-staging/` and
`docs/integration/execution/`. No original path was read or written; the
original application and its tests were never run.

## 2. Deliverables

Source — `integration-staging/src/examdata_integration/api/`:

| file | role |
| --- | --- |
| `binary.py` | `ContentStore` over the verified manifest (safe names, media whitelist, magic bytes, sha256/size checks; invalid entries dropped with problems recorded), `ContentLimits`/`enforce_budget`, `parse_range_header`, `etag_for`, `if_none_match_matches`, `iter_sample`/`iter_range`/`iter_crop_copy` (private temp copy removed on completion and on early close) |
| `app.py` | five GET/HEAD handlers wired into `create_app()`; 200/206/304/404/409/413/416/422 answers through the one envelope; `{id}.{extension}` content filenames |
| `links.py` | the five registry rows flipped to implemented; `DEFERRED_SPECS` now empty (34/34 implemented) |
| `envelope.py` | `BINARY_STATUSES = {206, 304, 416}` carve-out (same idea as `FRAMEWORK_STATUSES`); `EMITTABLE_STATUSES` documents 413/416 |
| `openapi.py` | `BINARY_ROUTE_RESPONSES` documenting per-route statuses/media; HEAD pairs in the document |
| `__init__.py` | exports for the new symbols |

Fixtures — `integration-staging/fixtures/synthetic/binary/` (13 files):
11 samples (6 documents/diagrams: cie-qp, cie-ms, cie-diagram, edexcel-qp,
edexcel-ms, ielts-diagram; 3 crop PNGs; 1 syllabus PDF; 1 material PDF),
`manifest.json` (`examdata.integration.content-manifest/1`, whitelist
`application/pdf` + `image/png`, declared placeholder identities preserved,
real byte sha256/size on disk, generator sha) and `PROVENANCE.json`
(`fixture-provenance/1`, 12 entries, all labelled `synthetic_fixture`).

Tests — `integration-staging/tests/` (132 new tests in three modules plus
updates to the A10 modules):

| file | tests |
| --- | --- |
| `test_api_binary_store.py` | 111 (manifest integrity, unsafe names, media/magic, budgets, ranges, etags, temp copy) |
| `test_api_binary_transport.py` | 15 (200/HEAD/206/416/304/404/409/413/422, media, filenames) |
| `test_api_binary_fixtures.py` | 6 (manifest/provenance/`--check`) |
| `test_api_envelope.py` | 32 (updated for the binary-status carve-out) |
| `test_api_links_openapi.py` | 20 (updated to 34 advertised routes) |
| `test_api_routes.py` | 53 (binary registration replaces the deferred expectations) |

Tools — `integration-staging/tools/`: `build_binary_fixtures.py`
(generator; `--check` verifies without writing), `a11_probe_binary.py`
(88 offline scenarios), `a11_final_checks.py`, `a11_close_patch.py`;
`a10_probe_api.py` updated to 34/0 and re-run green (82/82).

Evidence and ledger — `docs/integration/execution/`: `A11_REPORT.md`,
`evidence/A11/{binary_stdout.txt, pytest_run_stdout.txt, final_checks.txt,
a10_probe_rerun.txt}`; ledger patch
`integration-staging/runtime/ledger-patches/A11_close.json`.

## 3. Transport contract

**Bytes, never envelopes.** Success answers are the actual verified bytes
(streamed in chunks); failures use the one §5.1 JSON envelope.

**Headers.** `content-type` is one of the whitelisted media (`application/pdf`,
`image/png`); `content-disposition: inline; filename="<id>.<ext>"`; a strong
`ETag` `"<sha256 of the bytes>"`; `x-content-sha256` (bytes hash, distinct
from the declared fixture identity); `accept-ranges: bytes`;
`x-evidence: synthetic_fixture`; `x-dataset-revision`; echoed
`x-request-id`; `content-length` on 200. Crop answers add
`x-document-sha256` (declared identity) and `x-page`.

**Ranges.** Single ranges only, and only where they are really satisfied:
206 with `content-range` and the verified slice (first-N, suffix `-N`, and
open `N-`); an unsatisfiable range is 416 with `content-range: bytes */size`
and a valid error envelope; a bare `bytes=-0` is 416; an inverted
`bytes=5-3` is ignored and answered 200. HEAD returns the GET headers with
an empty body.

**Conditional.** `If-None-Match` (weak comparison; quoted, `W/` and list
forms exercised; `*` supported by the matcher) yields 304 with no body and
no `content-length`; a non-matching etag is a normal 200.
`If-Modified-Since` and `If-Range` are not implemented (see §6).

**Failure codes.** 404 `not_found` (unknown identity), 404
`content_not_available` (known identity without a sample), 404
`crop_not_available`, 409 `hash_conflict` / `region_conflict` (crop
provenance vs. store), 413 `response_budget_exceeded` /
`crop_budget_exceeded` via `ContentLimits`, 422 `unsupported_capability`
(regionless crop — the IELTS provider has no REGIONS capability), 405
framework rejection.

**Budgets and cleanup.** `enforce_budget` runs before streaming; crop
streaming goes through a private temp copy that is deleted when the response
generator finishes, including an early `close()`; the probe's containment
scenario confirms no `crop-`/`a11-conflict-` leftovers under
`integration-staging/runtime/tmp`.

**Route agreement.** runtime == spec == advertised = 34 pairs (29 A10 + 5
binary, five of them HEAD); `DEFERRED_SPECS` empty;
`agreement_problems(app) == []`.

## 4. Evidence

| evidence | label | file |
| --- | --- | --- |
| 88/88 offline probe scenarios pass | `synthetic_fixture` | `evidence/A11/binary_stdout.txt` |
| staged suite green: 711 passed, 0 failed | `synthetic_fixture` | `evidence/A11/pytest_run_stdout.txt` |
| A10 probe regression green: 82/82 | `synthetic_fixture` | `evidence/A11/a10_probe_rerun.txt` |
| closing checks PASS | `static_inspection` + `synthetic_fixture` | `evidence/A11/final_checks.txt` |

What the probe demonstrates (all offline, in-process `TestClient`, no socket):
route/HEAD/OpenAPI agreement; store and provenance integrity against disk;
asset 200 byte-equal GET/HEAD and the resources alias; ranges 206/416 as
above; 304 via three `If-None-Match` forms; budgets 413; crop 409 conflicts
and regionless 422; syllabus/material 200/404; generator `--check`;
containment. The closing checks re-run the A11 probe and the A10 regression,
re-verify the generator's write-free `--check`, the api import containment,
the ledger state and the write-set roots, and hash both Phase A roots.

The staged suite is 711 passed / 6 warnings: five FastAPI duplicate
operation-ID warnings (GET/HEAD pairs share handler names) and one
Starlette/httpx deprecation warning — toolchain noise, no product failure.

## 5. Corrections made in this packet

Implementation corrections (found by tests/smoke, fixed in packet):

1. **Content filenames.** The content handlers first answered with the bare
   id as filename; the contract is `{id}.{extension}`. Fixed in `app.py`
   (three call sites) after the first full-suite run caught it.
2. **OpenAPI documentation of the binary rows.** The five rows were missing
   from the OpenAPI helper (first smoke); `BINARY_ROUTE_RESPONSES` was added
   and exported, then the documented 200 media lists were aligned to
   `pdf`/`png` (second smoke) — the third smoke passed end to end.
3. **Store-test setup.** The size-mismatch store test never wrote the
   declared bytes; fixed in the test.

Expectation/script corrections (no product change): a fixture-verification
heredoc assertion, a walrus `SyntaxError` in a probe heredoc, a
budget-semantics expectation, and a wrong `HTTP_METHODS` vocabulary
assumption.

Process corrections before close: the close-patch write set was found (by
comparing against files newer than `A10_close.json`) to omit
`tools/build_binary_fixtures.py` — added — and two probe-note phrases were
corrected against the probe source (`If-Modified-Since` was never
exercised; containment attribution).

The intermediate full-suite run after the route flip reported
`11 failed / 567 passed` while its exit code was masked to 0 by a
`| tail` pipeline without `pipefail`; the regression is recorded in the
ledger failures as `exit_code_masked` so it is not hidden. After the test
updates it was `579 passed`; after the two implementation fixes, `711
passed`.

## 6. Deliberate limitations

- **Conditional support is `If-None-Match` only** (quoted/weak/list, `*` in
  the matcher). `If-Modified-Since` and `If-Range` are neither implemented
  nor exercised; the plan requires HEAD and conditional behaviour "where
  declared", which is satisfied by the tested HEAD + 304 behaviour.
- **Disconnect cleanup is exercised as an early generator `close()`**, not a
  real socket disconnect — the isolated in-process harness has no real
  socket.
- **Samples are synthetic placeholders** (hundreds of bytes; whitelist
  `pdf` + `png` only, no audio/zip). Real ingestion, hashing and rights
  review remain Phase B.
- **206/304/416 are transport-level carve-outs** documented in
  `envelope.BINARY_STATUSES` outside the §5.2 JSON error map (which
  describes error bodies), analogous to `FRAMEWORK_STATUSES` 405.
- **Duplicate operation-ID warnings** for the five GET/HEAD pairs are
  tolerated FastAPI behaviour, not served output.

## 7. Remaining gaps

- Only synthetic fixtures and in-process TestClient requests are used: no
  original database, no upstream fetch, no CIE batch resume, no service
  start.
- The 11 samples are small synthetic placeholders (not real
  Cambridge/edexcel/IELTS material); real sample ingestion, hashing and
  rights review stay a Phase B concern.
- Syllabuses and materials content are served from labelled synthetic
  fixtures; active materials and historical timetable integration remain
  deferred to the active owner.
- `If-Modified-Since`/`If-Range` and a real socket disconnect are not
  covered (see §6); audio/zip media are not staged.
- Legacy 71-route compatibility is A12; the frontend proposal is A13; the
  file-by-file merge map is A14; `PHASE_A_REPORT.md` is A15.
- The staged API is not the production service and is not deployed; the live
  database, service restart, upstream crawl and CIE batch resume remain
  Phase B and require explicit human release.

## 8. Next action

A12 — legacy compatibility: one worksheet row per route of the 71-route
baseline (`docs/integration/ROUTE_INVENTORY_CURRENT.json`) plus any routes
added since, each with the allowed compatibility status, the staged v2
equivalent and the merge-time requirement; then A13 (frontend proposal,
copy-only), A14 (file-by-file merge map) and A15 (`PHASE_A_REPORT.md`).
