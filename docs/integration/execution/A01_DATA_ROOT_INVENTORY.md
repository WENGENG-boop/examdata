# A01 — Data-Root Inventory (staged, read-only)

- Packet: A01 (plan §11); mode `PHASE_A_ISOLATED_ONLY`; evidence label `static_inspection`.
- Source of record: `evidence/A01/statics_extract.json` (run 18:34:46 +08:00, exit 0).
- Directory listings record names/mtimes only where listed; no database file was opened,
  no JSON payload was imported into the original app, nothing was copied in A01.

## 1. Data roots observed (15)

| Root | Exists | Top-level entries | Observed content (abridged) | Role / Phase A handling |
| --- | --- | ---: | --- | --- |
| `.data/` (workspace root) | yes | 3 | `artifacts/`, `assets/`, `raw_pages/` | Consistent with a `get_settings().ensure_dirs()` side effect in CWD (see config matrix §6). Read-only original; not used. |
| `examdata/.data/` | yes | 40 | `examdata.db` (+ `-shm`/`-wal` + 5 backup sets), `artifacts/`, `assets/`, `backup/`, `discovery.json`, `discovery.log`, `download_specs.py`, `edexcel_papers/` | Primary legacy SQLite data dir. **Never opened**; A03 fixtures use private copies only. |
| `examdata/.pytest_cache/` | yes | 40 | build/accept logs (`accept-*.log`), `accept-corpus-*`, `accept-empty-*`, `accept-installed-*`, `accept-portable/` | Test cache artifacts; evidence for legacy test behavior at A12; read-only. |
| `examdata/pytest-of-weo/` | yes | 5 | `pytest-10/`, `pytest-16/`, `pytest-19/`, `pytest-20/`, `pytest-21/` | pytest temp roots from prior runs; read-only. |
| `ielts-data/` | yes | 16 | `raw/`, `normalized/`, `derived/`, `indexes/`, `manifests/`, `decisions/`, `audio/`, `pdf/`, `assets/`, `refresh/`, `runs/`, `tools/`, `test-examdata/`, `test-s03/`, `test-s06/`, `test-s15/` | IELTS data root. Candidate source for A03 `copied_snapshot` fixtures. |
| `toefl-api/data/` | yes | 4 | `coverage.json`, `ddy-index.json`, `jj-index.json`, `kmf-index.json` | TOEFL derived JSON indexes; candidate fixture source (read-only). |
| `toefl-api/audit-20261005/` | yes | 7 | `audio-summary.json`, `cache-summary.json`, `cleanup-manifest.json`, `flow-summary.json`, `pytest-*.log`, `server.log` | TOEFL audit evidence; read-only context for A08. |
| `toefl-api/repair-20261005/` | yes | 8 | `PLAN.md`, `REPAIR_REPORT.md`, `backup/`, `evidence/`, `cleanup-manifest.json`, `evidence-summary.json`, `hash_files.py`, `hashes-before.json` | TOEFL repair evidence; contains a **backup copy** of `toefl-cli.mjs` (see CLI inventory §3). |
| `cie-location-batch/indexes/` | yes | 18 | subject dirs `0413 … 9868` (18) | CIE location batch index outputs (batch stopped; resume **not** authorized). |
| `cie-location-batch/work/` | yes | 40 | per-syllabus fix/repair JSONs, Python probe scripts, line/edge dumps | CIE batch work artifacts; context for A07 CIE read adapter; read-only. |
| `cie-location-batch/.data/` | yes | 6 | `examdata.db` (+ `-shm`/`-wal`), `artifacts/`, `assets/`, `raw_pages/` | CIE batch private SQLite; **never opened**. |
| `cie-index-batch-2026-10-01/` | yes | 2 | `9709/`, `review/` | Stopped CIE index batch outputs; read-only context (A07). |
| `cie-question-crops/out/` | yes | 1 | `9709_m26_qp_12/` | Crop outputs for one paper; read-only context (A13 image/asset path). |
| `examdata/build/` | yes | 2 | `bdist.win-amd64/`, `lib/` | Prior build outputs; packaging context (A14). |
| `examdata/research/` | yes | 7 | `cambridge.md`, `edexcel.md`, `exam-materials-cie.md`, `exam-materials-edexcel.md`, `exam-timetable-cie-zone5.md`, `exam-timetable-edexcel.md`, `implementation-status.md` | Research notes; read-only context. |

## 2. Database files observed (8 rows; none opened)

| Path | Exists | Size |
| --- | --- | ---: |
| `explore-examdata.db` (workspace root) | no | — |
| `proto-examdata.db` (workspace root) | no | — |
| `proto2-examdata.db` (workspace root) | no | — |
| `qsvc_check.db` (workspace root) | no | — |
| `examdata/explore-examdata.db` | yes | 4,182,016 B (mtime 2026-09-30 07:59) |
| `examdata/proto-examdata.db` | yes | 4,182,016 B (2026-09-30 08:00) |
| `examdata/proto2-examdata.db` | yes | 4,182,016 B (2026-09-30 08:02) |
| `examdata/qsvc_check.db` | yes | 4,182,016 B (2026-09-30 08:01) |

Additional observed (directory listing of `examdata/.data/`): the live-looking
`examdata.db` with `-shm`/`-wal` sidecar files and at least five timestamped backup
sets (`bak-pre-jev-apply2`, `bak-pre-provrebuild`, `bak-pre-r13`, `bak-pre-r13fix`, …).
WAL files indicate recent write activity; **no Phase A step may open, copy, or
checkpoint these files**. CIE batch `.data/` holds a similar SQLite trio.

## 3. Reports manifest (17 files; sha256 truncated for display — full values in `statics_extract.json`)

| Report | Size (B) | sha256 (first 16 hex) |
| --- | ---: | --- |
| `docs/PROJECT_STATUS.md` | 8272 | `0bb307bf292169a4…` |
| `docs/integration/MASTER_EXECUTION_PLAN_EN.md` | 79435 | `a81355545c4d4a4e…` |
| `docs/integration/EXECUTOR_PROMPT_EN.md` | 4445 | `ee1ab92bc154cf63…` |
| `docs/integration/ROUTE_INVENTORY_CURRENT.json` | 20756 | `946d3e90cbccd54d…` |
| `SESSION_CONTINUATION_PLAN.md` | 1945 | `7d9bb269b84edadb…` |
| `gaokao-feasibility/REPORT.md` | 8433 | `eb6ae1ca587dce5c…` |
| `gaokao-feasibility/channels.md` | 8609 | `b2357e9805befb0b…` |
| `gaokao-feasibility/coverage-matrix.csv` | 3917 | `aefab84c64b21512…` |
| `gaokao-feasibility/scope-map.md` | 5213 | `cce27a99fa09b036…` |
| `toefl-api/REPORT.md` | 43793 | `d5aa7fa5473fcbbf…` |
| `toefl-api/AUDIT_REPORT_20261005.md` | 12185 | `bc2e2dd0e47e0583…` |
| `toefl-api/AGENT_FIX_PROMPT_20261005.md` | 9140 | `60e9f747b90a32d9…` |
| `ielts-api/API.md` | 32498 | `c5debe7e19a20d80…` |
| `ielts-api/AUDIT_REPORT.md` | 19448 | `149bb8995663b19e…` |
| `ielts-api/DEVELOPMENT.md` | 19048 | `0b5c9cafb0b4044b…` |
| `examdata/README.md` | 12441 | `503787d25301d1e6…` |
| `frontend/README.md` | 3307 | `df197ba44cf1d2d2…` |

Also observed report dirs: `examdata/docs/` (15 top-level entries; includes
`AGENT_HANDOFF.md`, `API.md`, `DEPLOY.md`, …) and `cie-index-batch-2026-10-01/`
(`9709/`, `review/`). These are context only; they are not modified.

## 4. Fixture-design implications (inputs to A03)

- Candidate `copied_snapshot` sources: `ielts-data/` (manifests/decisions/normalized),
  `toefl-api/data/*.json`, `cie-location-batch/indexes/` + `work/` (redacted tails),
  `frontend` catalog/syllabi JSON.
- Never-to-copy: every `*.db` (+ `-shm`/`-wal`), any `.env`-style secrets, live
  service state, Kimi-active materials/timetable outputs (worksheet
  `deferred_active_owner`).
- A03 must record source path + sha256 + capture time for every copied fixture and
  keep the original bytes untouched (no normalization-in-place).
