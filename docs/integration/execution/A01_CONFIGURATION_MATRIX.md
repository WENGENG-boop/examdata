# A01 — Configuration Matrix (staged, read-only)

- Packet: A01 (plan §11); mode `PHASE_A_ISOLATED_ONLY`; evidence label `static_inspection`.
- Source of record: `evidence/A01/statics_extract.json` (run 18:34:46 +08:00) plus
  direct reads of `examdata/src/examdata/core/config.py` and
  `examdata/src/examdata/api/security.py` (read-only).
- Nothing here executes anything; values are defaults observed in source, not measured runtime behavior.

## 1. Python Settings (`examdata/src/examdata/core/config.py`)

`Settings(BaseSettings)`: `env_prefix="EXAMDATA_"`, `env_file=".env"`, `extra="ignore"`.
Environment variables therefore take the form `EXAMDATA_<FIELD>`; a `.env` file in the
process working directory is also read.

| Setting (env var `EXAMDATA_...`) | Default | Notes |
| --- | --- | --- |
| `DATA_DIR` | `.data` | Relative to process CWD; dirs auto-created (see §6 risk) |
| `DATABASE_URL` | `sqlite:///.data/examdata.db` | Relative SQLite path by default; PostgreSQL URL supported |
| `USER_AGENT` | `ExamDataBot/0.1 (+https://example.invalid/examdata; contact=ops@example.invalid)` | Placeholder `.invalid` contact — must be replaced before any real upstream use (Phase B+) |
| `REQUEST_TIMEOUT_SECONDS` | `30.0` | |
| `MAX_RETRIES` | `3` | |
| `RETRY_BACKOFF_SECONDS` | `2.0` | |
| `MIN_HOST_INTERVAL_SECONDS` | `1.0` | Minimum per-host interval with jitter |
| `HOST_INTERVAL_JITTER_SECONDS` | `0.5` | |
| `RESPECT_ROBOTS` | `true` | |
| `MAX_CONCURRENCY` | `4` | |
| `PARSER_VERSION` | `0.1.0` | Key for derived-data rebuilds; must be preserved in identity/provenance work |

Derived properties: `artifacts_dir = data_dir/artifacts`, `assets_dir = data_dir/assets`,
`raw_pages_dir = data_dir/raw_pages`.

API-layer security env vars (constants in `api/security.py:47-48`, used at 99/110):

| Env var | Meaning |
| --- | --- |
| `EXAMDATA_CORS_ORIGINS` | Comma-separated origin allowlist, or `*` |
| `EXAMDATA_API_KEY` | When set, requests must carry the API key (except exempt paths) |

## 2. Python environment reads outside Settings (16 scan hits)

| File:line | Variable | Source text (abridged) |
| --- | --- | --- |
| `api/ielts.py:55` | `EXAMDATA_IELTS_MAX_CONCURRENT` | default `"4"` |
| `api/ielts.py:68` | `EXAMDATA_IELTS_QUEUE_TIMEOUT` | default `"5"` (seconds) |
| `api/ielts.py:85` | `EXAMDATA_IELTS_DIR` or `IELTS_API_DIR` | gateway data-dir override |
| `api/ielts.py:105` | `EXAMDATA_IELTS_TIMEOUT` | subprocess timeout override |
| `api/ielts.py:125` | `EXAMDATA_NODE` | Node binary override, fallback `shutil.which("node")` |
| `api/security.py:99` | `EXAMDATA_CORS_ORIGINS` (via `CORS_ORIGINS_ENV`) | |
| `api/security.py:110` | `EXAMDATA_API_KEY` (via `API_KEY_ENV`) | |
| `api/toefl.py:57` | `EXAMDATA_TOEFL_MAX_CONCURRENT` | default `"4"` |
| `api/toefl.py:70` | `EXAMDATA_TOEFL_QUEUE_TIMEOUT` | default `"5"` |
| `api/toefl.py:87` | `EXAMDATA_TOEFL_DIR` or `TOEFL_API_DIR` | gateway data-dir override |
| `api/toefl.py:107` | `EXAMDATA_TOEFL_TIMEOUT` | subprocess timeout override |
| `api/toefl.py:127` | `EXAMDATA_NODE` | as above |
| `timetable/build.py:39` | `EXAMDATA_ZONE5_PDF_DIR` | active-owner module (deferred) |
| `timetable/build.py:46` | `EXAMDATA_ZONE5_MATRIX` | active-owner module (deferred) |
| `timetable/build_edexcel.py:37` | `EXAMDATA_EDEXCEL_PDF_DIR` | active-owner module (deferred) |
| `timetable/build_edexcel.py:44` | `EXAMDATA_EDEXCEL_MANIFEST` | active-owner module (deferred) |

## 3. Node environment reads (23 scan hits)

| File:line | Variable | Role |
| --- | --- | --- |
| `ielts-api/data-store.mjs:36` | `EXAMDATA_IELTS_DATA_DIR` | override data root (default `<workspace>/ielts-data`) |
| `ielts-api/fetch-source.mjs:39-41` | `EXAMDATA_IELTS_MAX_REQUESTS` (200), `EXAMDATA_IELTS_MAX_BYTES` (1 GiB), `EXAMDATA_IELTS_MAX_BYTES_PER_REQUEST` (512 MiB) | fetch budgets |
| `ielts-api/pdf-adapter.mjs:46` | `EXAMDATA_IELTS_PYTHON` | Python binary for PDF adapter |
| `ielts-api/pte.mjs:129` | `IELTS_RUN_ID` / `EXAMDATA_IELTS_RUN_ID` | run-id tagging |
| `ielts-api/tests/*` | `C_ROOT`, `C_BODY`, `EXAMDATA_IELTS_DATA_DIR` | test-only env (private tmp roots in tests) |
| `ielts-api/tools/baseline.mjs:40,251-255,272-273` | `EXAMDATA_IELTS_DATA_DIR`, `EXAMDATA_IELTS_DIR`, `EXAMDATA_NODE`, `EXAMDATA_DATA_DIR`, `EXAMDATA_IELTS_TIMEOUT` | baseline tool reports env; resolves data dir |
| `ielts-api/tools/build-question-index.mjs:31` | `EXAMDATA_IELTS_DATA_DIR` | data root |
| `frontend/server.mjs:8` | `EXAMDATA_URL` | upstream API base (default `http://127.0.0.1:8000`) |
| `frontend/server.mjs:9` | `FRONTEND_PORT` | listen port (default `5188`) |
| `frontend/server.mjs:42` | `EXAMDATA_API_KEY` | adds `X-API-Key` header to proxied calls |

## 4. Env templates

- `env_templates`: **0 found** in scanned components — no `.env.example`/`.env.template`
  exists in the scanned roots. Actual `.env` files, if any, were not read (secret files).
- A06 must ship a staging env template (private roots, offline flags) for the isolated harness.

## 5. Gateway knobs summary (io limits to preserve)

Per provider gateway (Python side): `MAX_CONCURRENT` (4), `QUEUE_TIMEOUT` (5 s),
`TIMEOUT` (subprocess), `DIR` override, `EXAMDATA_NODE`.
Per Node fetcher: max requests / max bytes / max bytes-per-request (IELTS side shown above).
These are the request-budget facts A11 must preserve and make explicit in v2.

## 6. Risk flagged for A02+: Settings import side effect (§6.2 concern)

`core/config.py:61-69`: `get_settings()` calls `s.ensure_dirs()`, which `mkdir`s
`data_dir`, `data_dir/artifacts`, `data_dir/assets`, `data_dir/raw_pages`
**relative to the process working directory on first call**. Call sites already
observed: `api/app.py:564`, `api/unified.py:354`, `api/unified.py:367`.

Consequences:
- Any import/execution of the original app from the original tree can silently create
  or touch `.data/*` directories in the CWD — the exact reason Phase A forbids
  in-place imports/tests and why the A02 harness must (a) run with a private CWD,
  (b) set `EXAMDATA_DATA_DIR`-equivalent private roots, and (c) assert that every
  loaded module resolves under `integration-staging/` (module-resolution assertion).
- The workspace-root `.data/` (artifacts/, assets/, raw_pages/, created 2026-10-05
  11:14) is consistent with such a side effect having occurred in the original tree
  at some earlier point; it is now treated as original data and is read-only.
