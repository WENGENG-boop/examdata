# PHASE_A_REPORT — isolated integration staging (Phase A complete, awaiting human release)

Packet A15 of `docs/integration/MASTER_EXECUTION_PLAN_EN.md` section 11:

> **A15 — Finish Phase A and wait safely**
> **Write:** `PHASE_A_REPORT.md`, updated ledger, staged test logs, deferred-work list,
> ownership-release requirements.
> **Steps:** Finish all independent allowed tasks. Report what is staged, what is unverified,
> and which gates remain closed. Stop dependent original-project modifications.
> **Pass:** No claim that integration or deployment is complete. Original services remain
> untouched by this executor.
> **Next:** Await explicit human release. Do not poll forever or autonomously open Phase B.

This document reports Phase A of the integration described by
`docs/integration/MASTER_EXECUTION_PLAN_EN.md` (the governing English master plan) and
`docs/integration/EXECUTOR_PROMPT_EN.md`. Work packets **A00–A15** are done. Everything this
executor produced is **staged** under the two Phase A write roots; **nothing is merged into the
original project and nothing is deployed**. This report makes no completion claim for the
integration or for any deployment, and it does not release the original paths.

## 1. Status in one line

Phase A is complete and every deliverable is staged offline: **A00–A15 all `staged_pass`**,
**B00–B10 all `not_started`**, **all seven Phase B gates closed**, **no task carries a merged
status**, and the original project (source, data, configuration, tests, documentation, caches,
checkpoints, services, the live database, ports 5188/8000, the shared virtual environment, the
stopped CIE batch, and the Kimi-owned materials/timetable code) was **read-only** to this
executor throughout.

## 2. What Phase A is, and what it is not

| | Phase A (this work, done) | Phase B (not started, gated) |
| --- | --- | --- |
| Location | `integration-staging/` + `docs/integration/execution/` | the original project tree |
| Effect on originals | none — read-only observation only | merges, migrations, service integration, deployment |
| Evidence label | `staged_pass` | (would be) `merged_pass` |
| Trigger | the executor prompt | **explicit human release of the original paths** |

- **Staged** means: built, tested offline, and documented inside `integration-staging/`, with a
  file-by-file merge proposal and a reversal for every change.
- **Not merged** means: no original file was written; the six planned original edits are
  proposals with a recorded base hash, not applied changes.
- **Not deployed** means: no service was restarted or reconfigured, no bundle was installed, no
  remote target was touched, and no data root pointer was moved.

## 3. Packet-by-packet summary (A00–A15)

Statuses are read from `docs/integration/execution/execution-ledger.json`. The "staged suite"
column is the cumulative count of tests passing in the isolated harness (`integration-staging/`)
after the packet closed; the node figure is the staged frontend suite.

| Packet | Status | What it staged | Staged suite |
| --- | --- | --- | --- |
| A00 | staged_pass | Isolation roots created after a verified-absent check; `ownership.json`; the execution ledger (`examdata.integration.ledger/1`) with the seven gates | — |
| A01 | staged_pass | 71-route static baseline and the route-compatibility worksheet; statics/CLI/config/data-root inventories | — |
| A02 | staged_pass | Private test harness with an offline network guard (a deliberate non-loopback call is proven to fail) | 18 |
| A03 | staged_pass | Fixture capture: 6 `copied_snapshot` + 3 `synthetic` fixtures, each with a provenance manifest | 29 |
| A04 | staged_pass | Contracts, identity mapping and quality semantics — 30 schemas, 61/61 fixture↔model round-trips | 75 |
| A05 | staged_pass | Provider protocol + registry (filtering precedes dispatch; unsupported ≠ empty) | 141 |
| A06 | staged_pass | Runtime configuration + the controlled Node runner (timeout/overflow/cancellation, classified failures) | 232 |
| A07 | staged_pass | CIE/Edexcel read adapters (total read step; answer resolution; document hashes preserved) | 326 |
| A08 | staged_pass | IELTS/TOEFL read adapters (IELTS Q41 missing slot, hierarchy, tables, conflicts preserved) | 387 |
| A09 | staged_pass | Private catalog + revision publish/rollback (compare-and-swap, revision-bound cursors) | 430 |
| A10 | staged_pass | Isolated v2 API (`create_app`), never importing or running the original application | 576 |
| A11 | staged_pass | Binary transport (200/206/416), reproducible fixtures, no original path touched | 711 |
| A12 | staged_pass | Legacy-compatibility modules + registry; worksheet covers 71/71 baseline rows | 856 |
| A13 | staged_pass | Staged frontend copy + operations readers; provenance for 6 copied frontend files | 887 |
| A14 | staged_pass | File-by-file merge map (247 entries), release manifest proposal, six-unit rollback rehearsal | 887 |
| A15 | staged_pass | This report, the deferred-work list, the ownership-release requirements, the closing checks | 887 |

Full suite: **887 passed / 0 failed** (pytest, isolated harness, private fixtures, offline);
staged frontend node suite **27/27**. Per-packet test evidence lives under
`docs/integration/execution/evidence/A00` … `evidence/A15` and in each packet's `Axx_REPORT.md`.

## 4. Deliverables

### 4.1 Staged implementation — `integration-staging/`

| Area | Contents |
| --- | --- |
| `src/examdata_integration/` | 62 files: contracts, identity mapping, quality rules, provider registry, Node runner, catalog, the isolated v2 API, binary transport |
| `contracts/` | 74 files: 30 JSON schemas + generated examples |
| `tests/` | 43 files: the isolated harness and 887 passing tests |
| `fixtures/` | 49 files: provenance manifests, synthetic fixtures, copied snapshots |
| `frontend/` | 13 staged client files + provenance (2 byte-identical snapshots, 4 modified copies) |
| `config/`, `docs/`, `components/` | configuration examples, staged docs (integration guide, release & rollback, v2 API reference), component manifest |
| `tools/` | the Phase A packet tools (`a00_*` … `a15_*`, `ledger_update.py`, `run_staged_tests.sh`) |

### 4.2 Execution record — `docs/integration/execution/`

| Artefact | What it is |
| --- | --- |
| `execution-ledger.json` | `examdata.integration.ledger/1`: 27 tasks, dependencies, input hashes, changed files, commands, cwd, exit codes, evidence, failures, remaining gaps, next action; the seven gates |
| `ownership.json` | The two write roots (created after a verified-absent check), the read-only scope, the prohibited operations, the release rule |
| `A00_INITIAL_REPORT.md` … `A15` (this file) | One report per packet |
| `A12_ROUTE_COMPATIBILITY_WORKSHEET.json` | The 71-route compatibility worksheet (64 `staged_pass` + 7 `deferred_active_owner`) |
| `A14_MERGE_MAP.json` / `.md` | The file-by-file merge map: 247 entries, 92 `not_merged`, 6 planned original edits, 12 recorded bases |
| `A14_RELEASE_MANIFEST.json` | The proposed release bundle: contents, observed dependency versions, smoke checks, rollback units, exclusions, `not_run` items |
| `A14_REHEARSAL.json` | The six-unit rollback rehearsal (5 rehearsed + 1 database unit `not_run`) |
| `PHASE_A_DEFERRED_WORK.md` | The deferred-work list and the ownership-release requirements |
| `evidence/A00` … `evidence/A15` | The command transcripts, stdout captures and closing-checks runs for every packet |

## 5. Validation model

Every claim in this report is backed by a reproducible offline check:

1. **Isolated harness with a network guard** (`integration-staging/tests/conftest.py`): tests
   run under `integration-staging/` with a pytest `basetemp` and cache dir inside the staging
   tree; a deliberate non-loopback socket call is proven to be rejected, so no test can reach an
   upstream source, the live database, or a service on ports 5188/8000.
2. **Private fixtures with honest labels**: every fixture records whether it is
   `copied_snapshot` (byte-identical to an immutable source), `synthetic` (constructed), or
   `modified_copy`. Synthetic and snapshot evidence is labelled as such and is never presented
   as live-source validation.
3. **Per-packet closing checks**: each packet's `aNN_final_checks.py` re-verifies its own
   artefacts, recomputes staged hashes against disk, and writes a transcript under
   `evidence/Axx/`.
4. **Cross-packet closing checks** (`a14_build_artifacts.py --check`,
   `a14_rehearsal.py --check`) re-prove the merge map and the rollback rehearsal from the frozen
   staging tree.
5. **Phase-A closing checks** (`a15_final_checks.py`): re-verifies the ledger state (A00–A15
   `staged_pass`, B00–B10 `not_started`, seven gates closed, no merged status), the close-patch
   consistency, the worksheet coverage, and both roots' `sha256` manifest, and asserts that
   these two A15 documents contain no completion claim. Transcript:
   `docs/integration/execution/evidence/A15/final_checks.txt`.

## 6. Compatibility coverage

`docs/integration/execution/A12_ROUTE_COMPATIBILITY_WORKSHEET.json` has one row for every route
of the 71-route baseline (`docs/integration/ROUTE_INVENTORY_CURRENT.json`):

- **71 / 71 baseline rows covered** — 64 `staged_pass` (behaviour reproduced offline in the
  staged application) and 7 `deferred_active_owner` (the Kimi-owned materials/timetable routes,
  whose integration is deferred to Phase B after release);
- 0 problems; every row carries a `legacy_path`, a `status`, and a `compatibility_strategy`.

Routes that Kimi adds after this snapshot are **not** covered yet: the worksheet is re-derived
in Phase B (B00) against the released tree, preserving every baseline route and adding the new
ones. No route is dropped or shadowed by the staged v2 application.

## 7. Deferred work and open gates

The full list is in `docs/integration/execution/PHASE_A_DEFERRED_WORK.md`. In summary:

- **DEF-01** — materials/syllabus/timetable read features (Kimi-owned active code) → B05.
- **DEF-02** — the Kander review module → offered to the user at Phase B kickoff.
- **DEF-03** — packets B00–B10 (merge, migration, service integration, deployment) → on release.
- **DEF-04** — the stopped CIE batch → only with a `cie_resume_authorized` instruction.
- **DEF-05** — remote deployment → Phase B only, with a `remote_deployment_authorized`
  instruction.
- **DEF-06** — auto-promotion of staged work → never automatic.

All seven Phase B gates are closed in the ledger:

`original_paths_released`, `real_data_write_authorized`,
`existing_service_cutover_authorized`, `upstream_requests_authorized`, `cie_resume_authorized`,
`remote_deployment_authorized`, `original_cleanup_authorized` — each `open: false`.

**What is unverified / not yet provable in Phase A** (stated so it is not mistaken for done):
the wheel is not built (the shared venv has no build backend and may not be changed); the
database rollback unit is `not_run` (no live database in Phase A); the final module layout is a
proposal pending B01/B02; the six planned original edits have no staged file; base hashes are
point-in-time observations of an actively edited tree; the staged docs are drafts; and the
worksheet does not yet cover Kimi-added routes.

## 8. Ownership release requirements

Phase A ends here and waits. **Only an explicit human instruction releases the original paths.**
Kimi going quiet, finishing, or sending a "done" message does **not** release any path, and this
executor does not poll for it or open Phase B on its own.

To open the `original_paths_released` gate, the human user must record (the ledger's
`gates.original_paths_released` fields and `ownership.json.gates_record.rule`):

1. **The instruction text** — the exact human instruction that releases the paths.
2. **The timestamp** — when the release was given.
3. **The scope** — which original paths are released (or all of them).
4. **The constraints** — what remains protected.

Opening `original_paths_released` opens **none** of the other six gates. Database migration,
service cutover, upstream requests, CIE resume, remote deployment and original cleanup each
require their own explicit authorization. Permission to merge code does not authorize any of
them.

## 9. Next action

Await explicit human release of the original paths. On release, Phase A's `staged_pass` records
are the input to Phase B (B00), which records the release instruction and takes a fresh baseline
of Kimi's final work before any merge. Until then, no further original-project work is performed
and this report stands as the Phase A deliverable.
