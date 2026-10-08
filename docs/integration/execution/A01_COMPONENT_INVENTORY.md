# A01 — Component Inventory (staged, read-only)

- Packet: A01 (plan §11) — read-only route/component inventory, first packet after A00
- Mode: `PHASE_A_ISOLATED_ONLY`
- Assembled: 2026-10-05 ~18:45 +08:00 (Git Bash; workspace `C:/Users/weo/Desktop/api`)
- Evidence label: `static_inspection` — every row below comes from read-only static scans;
  no original application, test, database, or service was started or run.
- Sources of record:
  - `integration-staging/tools/a01_static_inventory.py` (run 18:34:46 +08:00, exit 0)
    → `docs/integration/execution/evidence/A01/statics_extract.json` (+ stdout)
  - `integration-staging/tools/a01_inventory_routes.py` (run 18:33 +08:00, exit 0)
    → `evidence/A01/route_inventory_reextract.json` (+ stdout, diff)
  - `integration-staging/tools/a01_worksheet_build.py` (run 18:35 +08:00, exit 0)
    → `docs/integration/execution/A01_ROUTE_COMPATIBILITY_WORKSHEET.json`
- Original-tree status at observation time: protected and read-only to this executor;
  the Kimi Code owner was still active (examdata working tree: HEAD
  `8da3a0917e017a6cbf5d3e58e1fbeb9d0b0b83c8`, 1269 porcelain entries at 18:29).

## 1. Workspace components (top level)

| Component | Exists | Top-level entries | Observed content (abridged) | Observed integration role |
| --- | --- | --- | --- | --- |
| `examdata/` | yes | 40 | `src/examdata/` (16 subpackages), `tests/`, `pyproject.toml`, `.venv/`, `.data/`, `docs/`, `scripts/` | Python service + library: FastAPI API (app/unified/ielts/toefl), materials, timetable, ingest/sync/query/CLI |
| `frontend/` | yes | 21 | `app.js`, `server.mjs`, `resources.mjs`, `search.mjs`, `catalog.json`, `syllabi.json`, `index.html` | Static frontend + Node proxy server (consumer of the API gateway) |
| `ielts-api/` | yes | 35 | `ielts-cli.mjs`, `ielts-api.mjs`, `v2-api.mjs`, catalog/audio/answer matchers, `tools/`, `tests/` | Zero-npm-dependency Node aggregator for IELTS, spawned by the Python gateway |
| `toefl-api/` | yes | 12 | `toefl-cli.mjs`, `lib/`, `tools/`, `data/` (JSON indexes), `audit-20261005/`, `repair-20261005/` | Node aggregator for TOEFL, spawned by the Python gateway |
| `ielts-data/` | yes | 16 | `raw/`, `normalized/`, `derived/`, `indexes/`, `manifests/`, `decisions/`, `audio/`, `pdf/` | IELTS data root (JSON/manifest/audio/PDF corpus) |
| `cie-location-batch/` | yes | 24 | `checkpoint.json`, `indexes/` (18 subject dirs), `work/`, `.data/` (SQLite) | CIE location/crop batch pipeline state (batch stopped; resume NOT authorized) |
| `cie-index-batch-2026-10-01/` | yes | 2 | `9709/`, `review/` | CIE index batch outputs (stopped; resume NOT authorized) |
| `cie-question-crops/` | yes | 7 | `crop_questions.py`, `out/`, `tests/` | CIE question crop utility |
| `gaokao-feasibility/` | yes | 7 | `REPORT.md`, `channels.md`, `coverage-matrix.csv`, `samples/`, `scripts/` | Feasibility research only (no service code) |
| `docs/` | yes | 6 | `PROJECT_STATUS.md`, `PROJECT_INTEGRATION_PLAN.md`, `ielts/`, `toefl/`, `integration/` | Cross-project documentation + the integration package itself |

`examdata` Python subpackages (16, observed): `adapters`, `api`, `core`, `edexcel_papers`,
`gaokao`, `governance`, `intelligence`, `markscheme`, `materials`, `paperqa`, `parsing`,
`query`, `specs`, `sync`, `tagging`, `timetable`.

## 2. Python package metadata (`examdata/pyproject.toml`, sha256 `f8d69e9dc11c66e0…`)

- `name = "examdata"`, version `0.1.0`, `requires-python >= 3.11`.
- Dependencies: `httpx`, `beautifulsoup4`, `lxml`, `sqlalchemy>=2`, `pydantic>=2.6`,
  `pydantic-settings>=2.2`, `pymupdf`, `typer`, `rich`, `fastapi`, `uvicorn`.
- Console entry point: `examdata = "examdata.cli:app"`.
- Optional groups: `dev` (`pytest`, `pytest-cov`), `postgres` (`psycopg[binary]`).
- pytest config: `testpaths=["tests"]`, `norecursedirs` incl. `.venv`, `.data`,
  `addopts="-q"`.

## 3. Node package metadata

- `frontend/package.json` (sha256 `d56c9707063df96c…`): name `examdata-workspace`,
  private, `type=module`; scripts `start` (`node server.mjs`) and `check`
  (`node --check server.mjs && node --check app.js`); **zero dependencies**.
- `ielts-api/package.json`, `toefl-api/package.json`, `examdata/package.json`: absent.
  The zero-npm-dependency design (Node ≥ current, stdlib only) is confirmed on disk.

## 4. Route inventory linkage

Route re-extraction found **exactly the 71 baseline routes** (no additions, no
removals) across six source modules:

| Source module | Routes |
| --- | ---: |
| `examdata/src/examdata/api/app.py` | 20 |
| `examdata/src/examdata/api/unified.py` | 8 |
| `examdata/src/examdata/api/ielts.py` | 28 |
| `examdata/src/examdata/api/toefl.py` | 8 |
| `examdata/src/examdata/materials/router.py` | 4 |
| `examdata/src/examdata/timetable/router.py` | 3 |
| **Total** | **71** |

Worksheet (`A01_ROUTE_COMPATIBILITY_WORKSHEET.json`): 71 rows, statuses
`not_started` 64 + `deferred_active_owner` 7 (materials 4 + timetable 3);
providers ielts 28, cie 15, toefl 8, platform 8, mixed 5, materials 4, timetable 3;
methods GET 70 + POST 1; `problems: []`.

## 5. Boundary notes

- No original application, tests, database, or service was run for this inventory;
  all statements are point-in-time static reads.
- Original roots remain read-only; the staged implementation (A02+) uses private
  copies/fixtures only.
- Kimi concurrently edits original files (timetable router was modified at 18:10:36
  during this packet; the route set was unaffected). All hashes here are
  point-in-time and will be re-frozen at A12/A14.
