# A01 — Packet Report: read-only route/component inventory

- Goal: PHASE_A_ISOLATED_ONLY integration; packet A01 per plan §11 (first packet after A00).
- Status: **staged_pass** (closing checks: `evidence/A01/final_checks.txt`, forward reference).
- Date/window: 2026-10-05 18:29 – 18:45 +08:00 (Git Bash; workspace `C:/Users/weo/Desktop/api`).
- Evidence labels used: `static_inspection` only. No original app/test/DB/service was run,
  nothing outside the two Phase A write roots was written.

## 1. Objective and outcome

Produce, without executing anything in the original tree: component, route, CLI,
configuration, and data-root inventories; a compatibility worksheet row for every
route of the frozen 71-route baseline; source hashes and observation times; and a
deferred-work list for active-owner (Kimi) materials/timetable areas.

Outcome: all objectives met. The re-extracted route set is **identical to the
baseline (71/71)** even though the owner modified `timetable/router.py` at 18:10:36
during the packet; worksheet rows carry `not_started` (64) or
`deferred_active_owner` (7) only.

## 2. Runs (all commands via Git Bash; Python = `examdata/.venv/Scripts/python.exe`)

| # | Tool | Purpose | Result | Evidence |
| --- | --- | --- | --- | --- |
| 1 | `integration-staging/tools/a01_inventory_routes.py` | Re-extract explicit routes read-only (staged copy; 3 documented changes vs `docs/integration/tools/inventory_routes.py`) | exit 0; **71 routes**, groups 20/8/28/8/4/3; 0 duplicates | `evidence/A01/route_inventory_reextract.json` + `_stdout.txt`; tool diff in `route_tool_diff.txt` |
| 2 | `integration-staging/tools/a01_static_inventory.py` | Component layouts, metadata, CLI, env reads, data roots, hashes, git snapshot | **first attempt exit 1** (see §3); re-run exit 0; `STATIC_INVENTORY: PASS` | `evidence/A01/statics_extract.json` (+ stdout; failed transcript kept) |
| 3 | `integration-staging/tools/a01_worksheet_build.py` | Merge baseline ∪ re-extraction, AST enrichment, curate rules, self-validate | exit 0; `WORKSHEET_BUILD: PASS`; 71 rows, baseline 71/71, `problems: []` | `docs/integration/execution/A01_ROUTE_COMPATIBILITY_WORKSHEET.json` + stdout |
| 4 | `integration-staging/tools/ledger_update.py` | Set A01 `in_progress`; normalize ledger to canonical form | exit 0 | `execution-ledger.json` (pre-update `9ab29a6c…` → post `d6a62c32…`) |

Tool hashes (sha256) recorded in `evidence/A01/source_hashes_and_observation.txt`:
`ledger_update.py 36a7a48d…`, `a01_inventory_routes.py d6cdc885…`,
`a01_static_inventory.py 8af1c7e3…`, `a01_worksheet_build.py e4cf64c5…`;
original `docs/integration/tools/inventory_routes.py 5ad62a0d…` (unchanged).

## 3. Failure and fix (recorded, kept)

- Run 2 first attempt failed with exit 1: the tool's `git status` subprocess used
  `text=True` without an explicit encoding, so the locale GBK codec choked on UTF-8
  Chinese commit/status text (`UnicodeDecodeError: 'gbk' codec …`), cascading into an
  `AttributeError` on the buffered output.
- Fix: decode with `encoding="utf-8", errors="replace"` and guard `(stdout or "")`;
  removed an unused `import ast`. **Only the staging tool changed**; no original file
  was touched. Failed transcript preserved as
  `evidence/A01/statics_extract_stdout_FAILED_gbk_decode.txt`; re-run passed.
- Lesson applied: every staged tool call to external processes must pin an encoding.

## 4. Key findings

1. **Route set unchanged (71/71)** despite concurrent owner activity (timetable
   router edited 18:10:36; examdata working tree 1269 porcelain entries at 18:29).
   Baseline remains valid; A12 will re-freeze after owner quiescence.
2. **Settings import side effect**: `get_settings()` runs `ensure_dirs()`, creating
   `data_dir/{artifacts,assets,raw_pages}` **relative to process CWD** on first call
   (`core/config.py:61-69`; call sites `api/app.py:564`, `api/unified.py:354,367`).
   This is the concrete §6.2 hazard: the A02 harness must pin private CWD/env roots
   and prove module resolution stays under `integration-staging/`.
3. **Configuration surface**: `EXAMDATA_*` env namespace (Settings prefix), security
   vars `EXAMDATA_CORS_ORIGINS` / `EXAMDATA_API_KEY`, per-gateway
   `EXAMDATA_{IELTS,TOEFL}_*` knobs, `EXAMDATA_NODE`, fetch budgets on the Node side,
   frontend `EXAMDATA_URL`/`FRONTEND_PORT`/`EXAMDATA_API_KEY`. **No env template file
   exists** → A06 must ship one for staging. `USER_AGENT` still carries a
   `example.invalid` placeholder → must change before any real upstream use (Phase B+).
4. **Node surface**: 24 CLI candidates; entry points for the gateways are
   `ielts-cli.mjs` / `toefl-cli.mjs` (zero npm dependencies); a **backup copy** of
   the TOEFL CLI lives under `repair-20261005/backup/` (context, not an entry point).
5. **Data roots**: 15 observed; live-looking SQLite (with `-shm`/`-wal`) in
   `examdata/.data/` and `cie-location-batch/.data/` — never to be opened in Phase A.
   IELTS/TOEFL/CIE JSON data are the fixture candidates for A03.
6. **Test-run hygiene debt in the original tree** (`examdata/.pytest_cache` accept
   logs, `pytest-of-weo/` roots) is read-only context proving why A02/A12 must run
   tests with `--basetemp` and `cache_dir` under staging.

## 5. Deliverables produced by A01

- `docs/integration/execution/A01_ROUTE_COMPATIBILITY_WORKSHEET.json` (71 rows;
  proposals vocabulary `proposed:/api/v2/…` | `keep_legacy_only` |
  `keep_legacy_namespace` | `tbd_at_A08`; extra row keys `row_origin`,
  `handler_doc_line`).
- `docs/integration/execution/A01_COMPONENT_INVENTORY.md`
- `docs/integration/execution/A01_CLI_INVENTORY.md`
- `docs/integration/execution/A01_CONFIGURATION_MATRIX.md`
- `docs/integration/execution/A01_DATA_ROOT_INVENTORY.md`
- Evidence: `evidence/A01/` — `source_hashes_and_observation.txt`,
  `route_inventory_reextract.json` + `_stdout.txt`, `route_tool_diff.txt`,
  `statics_extract.json` + `statics_extract_stdout.txt` +
  `statics_extract_stdout_FAILED_gbk_decode.txt`, `worksheet_build_stdout.txt`,
  `final_checks.txt` (closing; forward reference at report time).

## 6. Deferred work / carried risks

- Materials (4) and timetable (3) worksheet rows stay `deferred_active_owner` —
  Kimi-owned; no copy/execution; release only in Phase B (B05).
- A12 remains `pending` for the 64 `not_started` cells (fixture IDs, test IDs,
  legacy shapes) until the staged v2 API and fixtures exist.
- `EXAMDATA_USER_AGENT` placeholder and missing env template carried to A06.
- Ledger normalized to canonical JSON in this packet (pre `9ab29a6c…` →
  post `d6a62c32…`); A00-era hash remains a point-in-time record only.

## 7. Next action

**A02 — private staging harness** (plan §11): private runtime roots under
`integration-staging/`; copy-for-execution of the Python service tree under private
paths; module-resolution assertion (every loaded app module resolves under staging);
proven network guard rejecting real calls; pytest with
`--basetemp .\runtime\pytest-temp -o cache_dir=.\runtime\pytest-cache` run from
`integration-staging`; all writes confined to the two Phase A roots.
