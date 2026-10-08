# A01 — CLI Inventory (staged, read-only)

- Packet: A01 (plan §11); mode `PHASE_A_ISOLATED_ONLY`; evidence label `static_inspection`.
- Source of record: `evidence/A01/statics_extract.json`
  (tool `integration-staging/tools/a01_static_inventory.py`, run 18:34:46 +08:00, exit 0).
- Nothing below was executed; all rows are static scan results. No CLI is run in A01.

## 1. `examdata` Python CLI (Typer)

- Entry point: `examdata = "examdata.cli:app"` (`pyproject.toml [project.scripts]`).
- Source: `examdata/src/examdata/cli.py` (sha256 `514f04204f85ee14…`), 1510+ lines.
- Commands found: **36** (all registered on the Typer `app`).

| CLI command | Handler | CLI command | Handler |
| --- | --- | --- | --- |
| `import-cie-index` | `cmd_import_cie_index` | `enrich` | `cmd_enrich` |
| `initdb` | `cmd_initdb` | `classify-content` | `cmd_classify_content` |
| `adapters` | `cmd_adapters` | `override-set` | `cmd_override_set` |
| `cambridge-syllabuses` | `cmd_cambridge_syllabuses` | `override-list` | `cmd_override_list` |
| `cambridge-probe` | `cmd_cambridge_probe` | `review-list` | `cmd_review_list` |
| `cambridge-discover` | `cmd_cambridge_discover` | `review-resolve` | `cmd_review_resolve` |
| `fetch` | `cmd_fetch` | `provenance-rebuild` | `cmd_provenance_rebuild` |
| `parse-pdf` | `cmd_parse_pdf` | `provenance-trace` | `cmd_provenance_trace` |
| `sync` | `cmd_sync` | `reparse` | `cmd_reparse` |
| `parse-docs` | `cmd_parse_docs` | `explain` | `cmd_explain` |
| `search-papers` | `cmd_search_papers` | `explain-review` | `cmd_explain_review` |
| `search-questions` | `cmd_search_questions` | `serve` | `cmd_serve` |
| `show-question` | `cmd_show_question` | `db-stats` | `cmd_db_stats` |
| `sample-questions` | `cmd_sample_questions` | `paper-qa` | `cmd_paper_qa` |
| `monitor` | `cmd_monitor` | `tags` | `cmd_tags` |
| `taxonomy-sync` | `cmd_taxonomy_sync` | `tag-questions` | `cmd_tag_questions` |
| `taxonomy-assign` | `cmd_taxonomy_assign` | `question-crop` | `cmd_question_crop` |
| `difficulty-estimate` | `cmd_difficulty_estimate` | | |
| `similarity-find` | `cmd_similarity_find` | | |

Notes:
- `serve` is the legacy service entry point (uvicorn). It is **not** started in Phase A.
- `initdb`, `sync`, `import-cie-index`, `override-set`, `review-resolve`,
  `provenance-rebuild` are write-capable commands — they must never be pointed at
  original data; A13/A14 treat the CLI surface as legacy behavior to preserve.
- Argument defaults were not deep-scanned here; A12 reads them when filling worksheet
  cells; the CLI contract is re-verified against source at A14.

## 2. Python `__main__` guards (12 found)

| File | Line |
| --- | ---: |
| `examdata/src/examdata/cli.py` | 1511 |
| `examdata/src/examdata/edexcel_papers/__main__.py` | 501 |
| `examdata/src/examdata/specs/loader.py` | 286 |
| `examdata/src/examdata/specs/runner.py` | 140 |
| `examdata/src/examdata/tagging/__main__.py` | 7 |
| `examdata/src/examdata/timetable/build.py` | 214 |
| `examdata/src/examdata/timetable/build_edexcel.py` | 285 |
| `examdata/scripts/pip_sandbox.py` | 65 |
| `examdata/scripts/probe_edexcel.py` | 517 |
| `examdata/scripts/reset_derived.py` | 112 |
| `examdata/scripts/smoke_public_api.py` | 812 |
| `examdata/scripts/verify_state.py` | 141 |

`timetable/*` guards are inside active-owner (Kimi) modules — deferred; not copied
or executed in Phase A (matches worksheet `deferred_active_owner` rows).

## 3. Node CLI candidates (24 files with shebang/metadata)

| File | Size (B) | Reads argv |
| --- | ---: | --- |
| `ielts-api/ielts-api.mjs` | 69172 | no |
| `ielts-api/ielts-cli.mjs` | 12457 | yes |
| `ielts-api/pdf-adapter.mjs` | 11370 | yes |
| `ielts-api/verify-pdfs.mjs` | 8941 | yes |
| `ielts-api/tools/audit-all.mjs` | 36251 | yes |
| `ielts-api/tools/baseline.mjs` | 11536 | yes |
| `ielts-api/tools/build-alignment-gold.mjs` | 12441 | yes |
| `ielts-api/tools/build-index.mjs` | 12074 | yes |
| `ielts-api/tools/build-manifest.mjs` | 16760 | no |
| `ielts-api/tools/build-question-index.mjs` | 10667 | no |
| `ielts-api/tools/check-route-inventory.mjs` | 9142 | yes |
| `ielts-api/tools/compare-official.mjs` | 10192 | yes |
| `ielts-api/tools/import-pdf.mjs` | 11744 | yes |
| `ielts-api/tools/refresh.mjs` | 28287 | yes |
| `ielts-api/tools/run-alignment.mjs` | 18033 | yes |
| `ielts-api/tools/verify-audio.mjs` | 37921 | yes |
| `ielts-api/tools/verify-decisions.mjs` | 11902 | yes |
| `toefl-api/toefl-cli.mjs` | 15518 | yes |
| `toefl-api/repair-20261005/backup/toefl-api/toefl-cli.mjs` | 13914 | yes (backup copy inside repair evidence; not a live entry point) |
| `toefl-api/tools/prefetch_jj.mjs` | 3905 | yes |
| `toefl-api/tools/prefetch_kmf.mjs` | 3850 | yes |
| `toefl-api/tools/prefetch_kmf_sw.mjs` | 4633 | yes |
| `toefl-api/tools/verify_live_evidence.mjs` | 7332 | yes |
| `frontend/build-syllabi.mjs` | 8492 | yes (no shebang; invoked via node) |

The gateway-perceived entry points are `ielts-api/ielts-cli.mjs` and
`toefl-api/toefl-cli.mjs` (both spawned by the Python gateway; see §4).
`ielts-api/ielts-api.mjs`, `build-manifest.mjs`, `build-question-index.mjs` are
library-style (no argv handling).

## 4. Gateway spawn facts (static)

- 90 matching text rows were extracted: 57 in `examdata/src/examdata/api/ielts.py`,
  33 in `examdata/src/examdata/api/toefl.py` (mostly docstrings/comments describing
  the Node CLI; two actual `asyncio.create_subprocess_exec(` call sites were found,
  one per gateway).
- Observed spawn pattern (static): Python gateway runs
  `node <ielts-api/ielts-cli.mjs | toefl-api/toefl-cli.mjs>` per request through a
  controlled subprocess, resolving the Node binary via `EXAMDATA_NODE` (fallback
  `shutil.which("node")`), with queue/limit knobs read from `EXAMDATA_IELTS_*` /
  `EXAMDATA_TOEFL_*` (see configuration matrix).
- The exact argv/env/timeout contract will be re-derived verbatim from source when
  building the controlled Node runner in **A06**; A06 owns the freeze.

## 5. Frontend scripts and call sites

- `frontend/package.json` scripts: `start` = `node server.mjs`, `check` = syntax check.
- Network call sites found (33): `server.mjs` 8, `build-syllabi.mjs` 6, `resources.mjs` 5,
  `syllabi.test.mjs` 5, `app.js` 4, `search.test.mjs` 4, `index.html` 1.
- `frontend/server.mjs` env: `EXAMDATA_URL` (default `http://127.0.0.1:8000`),
  `FRONTEND_PORT` (default `5188`), `EXAMDATA_API_KEY` (adds `X-API-Key` header).

## 6. Phase A handling

- No CLI was executed in A01; none will be executed against original paths in Phase A.
- Write-capable commands are listed here so A13/A14 keep the legacy surface compatible
  and so A02's harness can prove no test accidentally reaches them.
