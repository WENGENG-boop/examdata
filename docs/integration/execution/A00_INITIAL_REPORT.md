# A00 Initial Report — Establish the Protected Boundary

- Executor: Phase A integration executor (Kimi Code goal mode)
- Mode: `PHASE_A_ISOLATED_ONLY`
- Report date: 2026-10-05, ~18:09 +08:00
- Plan packet: `MASTER_EXECUTION_PLAN_EN.md` section 11, A00
- Staged vs merged: everything in this packet is staged/recorded only; nothing has been merged
  into the original project and nothing has been deployed.

## 1. Scope

A00 establishes the protected boundary for Phase A: mode, the two allowed output roots, the active
Kimi owner evidence, the all-false external gates, and the prohibited operations. All later packets
depend on this record. Companion records: `ownership.json` (boundary), `execution-ledger.json`
(task records and gates).

Governing inputs (hashes frozen in `evidence/A00/input_hashes_and_env.txt`):

| Document | sha256 |
| --- | --- |
| `docs/integration/EXECUTOR_PROMPT_EN.md` | `ee1ab92bc154cf63f59e588de138dce605189e6d6554c9deb29c1203c4b9953c` |
| `docs/integration/MASTER_EXECUTION_PLAN_EN.md` | `a81355545c4d4a4e6d3202767042685d1168456d9d8552d6c817602fcb19699b` |
| `docs/integration/ROUTE_INVENTORY_CURRENT.json` | `946d3e90cbccd54dc9ac9005f36f8f940b6b7d2fe1a5ae515b119d3c00e55baf` |
| `docs/PROJECT_STATUS.md` | `808eee86b2c1bbe1cdaefb3ea5e3801bd092b5e826c8e22f4fba13e3d063dcb9` |

## 2. Writable-root boundary

| Root | Role | Existed before creation | Created | Evidence |
| --- | --- | --- | --- | --- |
| `integration-staging/` | staged implementation tree | no | 2026-10-05T18:04:38+08:00 | `evidence/A00/pre_creation_absence.txt` |
| `docs/integration/execution/` | ledger, evidence, reports | no | 2026-10-05T18:04:38+08:00 | `evidence/A00/pre_creation_absence.txt` |

Both roots were absent immediately before creation (plan section 0.4 reuse check satisfied by
absence); they were created fresh with mkdir exit 0 (creation record annexed to
`checks_after_root_creation.txt`). Nothing was reused, overwritten, or erased. Ownership was
unambiguous, so no unique-child fallback was needed.

Everything else is read-only for this executor. Protected paths (plan section 0.5) include:
`examdata/**`, `frontend/**`, `ielts-api/**`, `ielts-data/**`, `toefl-api/**`,
`cie-location-batch/**`, `cie-index-batch-2026-10-01/**`, `cie-question-crops/**`,
`gaokao-feasibility/**`, `tmp_edexcel_tt_probe/**`, `tmp_materials_probe/**`, `.data/**`,
`docs/ielts/**`, `docs/toefl/**`, `SESSION_CONTINUATION_PLAN.md`.

## 3. Active owner evidence

Owner is ACTIVE at observation time 2026-10-05T18:00:44+08:00
(evidence: `evidence/A00/owner_observation.txt`):

- newest Kimi session `session_278e5996-bc2d-4809-ad6c-2a9d3061648a` created 17:58;
- plan session `session_de1b801c-...` wire last written 18:01 (52,885,432 bytes);
- `tmp_edexcel_tt_probe/` shows owner writes 17:48–17:56.

Release rule: only an explicit human instruction releases original paths for Phase B. Kimi
inactivity or a "done" message does not. No instructions were sent to any running session and no
processes were touched by this executor.

## 4. Phase B gates — all closed

| Gate | State |
| --- | --- |
| `original_paths_released` | false |
| `real_data_write_authorized` | false |
| `existing_service_cutover_authorized` | false |
| `upstream_requests_authorized` | false |
| `cie_resume_authorized` | false |
| `remote_deployment_authorized` | false |
| `original_cleanup_authorized` | false |

Gates are recorded in `execution-ledger.json` → `gates` (source: plan section 0.8). Only explicit
human instructions open a gate; each opened gate must record instruction text, timestamp, scope,
and constraints. No gate was changed during A00.

## 5. Prohibited operations (plan section 0.6)

1. Do not edit, format, rename, move, delete, restore, reset, stash, stage, commit, or overwrite
   original project files.
2. Do not kill, pause, restart, signal, reconfigure, or attach a debugger to Kimi or existing services.
3. Do not send instructions to the active Kimi session.
4. Do not change port 8000, port 5188, shared environment files, user-level environment variables,
   proxy settings, installed packages, or the existing virtual environment.
5. Do not run pytest from the original repository (its `conftest.py` creates a directory under the
   original `.pytest_cache` even before ordinary tests execute).
6. Do not import the original application to inspect routes; configuration and imports can create
   directories or initialize data.
7. Do not call existing service routes that can fetch upstream data, write caches, or launch
   subprocesses.
8. Do not execute `build-syllabi.mjs`, refresh tools, batch crawlers, or source verification
   commands against the live workspace.
9. Do not copy a live SQLite database by copying only its `.db` file; do not access a live database
   during Phase A — use synthetic fixtures or already exported immutable evidence.
10. Do not run `git clean`, `git reset --hard`, broad recursive deletion, a blanket formatter, a
    dependency upgrade, or a lock-file regeneration in the original project.
11. Do not interpret the plan as authorization to resume the stopped CIE batch.
12. Do not automatically promote staging changes after tests pass.

(The same list is machine-readable in `ownership.json` → `prohibited_operations`.)

## 6. Baseline observations (point-in-time)

- `examdata` HEAD: `8da3a0917e017a6cbf5d3e58e1fbeb9d0b0b83c8` (2026-10-05 15:05:10 +0800).
- tracked-modified count 48; all-entries count 1266.
- The workspace root `C:/Users/weo/Desktop/api` is not a git repository; only `examdata/` is.

These are observations, not integrity assertions (plan section 0.9). The owner is active, so counts
may legitimately drift. A01 re-observes with a recorded observation time.

## 7. Environment and conventions

- Python 3.14.7 (both system `python` and `examdata/.venv/Scripts/python.exe`); Node v24.19.0;
  git 2.55.0.windows.3.
- Every command runs with `PYTHONDONTWRITEBYTECODE=1`, `PYTHONIOENCODING=utf-8`,
  `GIT_OPTIONAL_LOCKS=0` (exported by `integration-staging/tools/_env.sh`); working directory is
  always `C:/Users/weo/Desktop/api` or a subdirectory of it.
- Never install into the shared virtual environment; never run `npm install`. Later packets vendor
  Node dependencies by file copy only.

## 8. Applicable rules scan

- No project-level `AGENTS.md`/`CLAUDE.md` exists anywhere scanned (14 workspace directories; zero
  FOUND lines — evidence: `evidence/A00/agents_md_scan.txt`).
- User-global Kander rules therefore apply. Dispositions decided for this task:
  1. `rules.code` — adopted: staged code follows the architecture/quality rules.
  2. `rules.reporting` — one-line end-of-task report; non-kanban, non-git → "no commits; branch N/A".
  3. `rules.review` — DEFERRED during Phase A: its git-commit/worktree/reviewer-runtime mechanics
     conflict with isolation (no git operations, no worktrees). Will be offered to the user at
     Phase B; recorded in ledger `deferred_work`.
  4. `rules.task_intake` — satisfied: the user chose direct execution; no card intake needed.
  5. `rules.task_groups` — N/A: no cards/worktrees; git module not in scope.
  6. `rules.git`, `rules.collaboration`, `rules.kanban` — not loaded; no git or kanban operations.
- The Kander config was read directly as a file (read-only) instead of running
  `kander config --json`, so no command could write outside the two Phase A roots.

## 9. Writes performed by A00

All new files; all within the two allowed roots; no deletions, no renames, no writes to original
paths. Elsewhere only read-only commands ran (ls, sha256sum, git status with optional locks
disabled, python reads).

| # | Path | Purpose | Producer |
| --- | --- | --- | --- |
| 1 | `integration-staging/README.md` | staging-tree boundary and conventions | write |
| 2 | `integration-staging/tools/_env.sh` | environment conventions | write |
| 3 | `docs/integration/execution/ownership.json` | ownership/boundary record | write |
| 4 | `docs/integration/execution/evidence/A00/owner_observation.txt` | active-owner evidence | write |
| 5 | `docs/integration/execution/evidence/A00/pre_creation_absence.txt` | root-absence evidence | write |
| 6 | `docs/integration/execution/evidence/A00/agents_md_scan.txt` | rules scan + rule-tree probe | write |
| 7 | `docs/integration/execution/evidence/A00/input_hashes_and_env.txt` | input hashes, toolchain, git baseline | write |
| 8 | `docs/integration/execution/evidence/A00/checks_after_root_creation.txt` | post-creation checks | tee |
| 9 | `docs/integration/execution/A00_INITIAL_REPORT.md` | this report | write |
| 10 | `docs/integration/execution/execution-ledger.json` | ledger (tasks A00–A15, B00–B10; gates) | write |
| 11 | `docs/integration/execution/evidence/A00/final_checks.txt` | closing checks + artifact hashes | tee |
| 12 | `integration-staging/tools/a00_final_checks.sh` | stored closing-checks runner (produces row 11's transcript) | write |

Evidence transcripts were re-extracted verbatim from the session event log on 2026-10-05 between
18:06 and 18:09 (+08:00).

## 10. A00 pass checklist and next action

- [x] Every A00 command ran with cwd `C:/Users/weo/Desktop/api` (allowed) and wrote only into the
  two allowed roots.
- [x] Both roots were absent before creation; created fresh; nothing reused/overwritten/deleted.
- [x] All seven gates recorded false; no gate changed.
- [x] Original project, services, venv, environment, and databases untouched by this executor
  (read-only commands only; observed owner changes are concurrent, plan section 0.9).
- [x] Ownership record, execution ledger, and initial report delivered (this file); validated by
  `evidence/A00/checks_after_root_creation.txt` and `evidence/A00/final_checks.txt`.

Next action: A01 — read-only inventory (plan section 11): static parsing only, never importing the
original application; a route compatibility worksheet with a row for every route of the 71-route
baseline; component, CLI, configuration, and data-root inventories under
`docs/integration/execution/`; record source hashes and observation time; mark active-owned file
mappings deferred.
