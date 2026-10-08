# B00 Report — Phase B freeze, baseline observation, and Phase B ledger tool

- **Packet**: B00 (first packet of Phase B, `PHASE_B_PENDING_RELEASE`)
- **Run id**: `b00b01-20261006T132400`
- **Status**: `partial` — all work permitted without a release is done; the release-gated half is deferred and recorded as a gap, not as a pass.
- **Mode**: `PHASE_B_PENDING_RELEASE`
- **Write roots used**: `integration-staging/`, `docs/integration/execution/` only.
- **Original tree**: read-only throughout. No original file was written; `unexpected_original_changes` in the ledger is `[]`.

> **Staged, not merged.** Nothing in this report merges the integration into the original project, migrates any database, restarts any service, or deploys anything. Every gate remains closed. Phase B is still deferred pending a human release with all four elements (instruction text, timestamp, path scope, remaining constraints).

## 1. What B00 set out to do

Per `docs/integration/MASTER_EXECUTION_PLAN_EN.md` §12 and
`docs/integration/execution/PHASE_B00_B01_EXECUTOR_PROMPT_2026-10-06.md`, B00 has two halves:

1. **Release-independent (done here):**
   - freeze the A records byte-for-byte into the B00 evidence directory;
   - take a separate Phase B ledger tool (`b_ledger_update.py`) with its own rejection tests;
   - build an observation-only baseline and a route worksheet that preserves every baseline route.
2. **Release-gated (deferred):**
   - only if the human records a release with all four elements, open `original_paths_released`
     and take a fresh read-only baseline of the released paths, re-deriving the worksheet and
     re-classifying the deferred rows.

## 2. Delivered (release-independent)

### 2.1 A records frozen

`B00_A_SEALED_INPUTS_INDEX.json` records 12 byte-identical copies of the A-sealed governance
inputs, taken as the B00 starting snapshot. Originals were read only.

| Sealed input | Bytes | SHA256 (prefix) |
| --- | ---: | --- |
| `a_sealed_execution-ledger.json` | 490190 | `72b24d335d73` |
| `a_sealed_ownership.json` | 6780 | `bf11e22fe72d` |
| `a_sealed_A12_ROUTE_COMPATIBILITY_WORKSHEET.json` | 178558 | `76ce0abc077b` |
| `a_sealed_A14_MERGE_MAP.json` | 230459 | `29940a0b0582` |
| `a_sealed_A14_MERGE_MAP.md` | 78982 | `1cf2a41f0203` |
| `a_sealed_A14_RELEASE_MANIFEST.json` | 9154 | `ae938da2e35e` |
| `a_sealed_A14_REHEARSAL.json` | 7726 | `94adc824f1fb` |
| `a_sealed_ROUTE_INVENTORY_CURRENT.json` | 20756 | `946d3e90cbcc` |
| `a_sealed_PHASE_A_REPORT.md` | 12686 | `84a025649ef4` |
| `a_sealed_PHASE_A_DEFERRED_WORK.md` | 7657 | `2c09ea250627` |
| `a_sealed_PHASE_A_INDEPENDENT_REVIEW_2026-10-06.md` | 6286 | `b6a7ec12b110` |
| `a_sealed_independent_checks_2026-10-06.txt` | 137945 | `699604ae4254` |

### 2.2 Observation-only baseline

`B00_BASELINE.json` (`observation_kind: observed_only`, `release_present: false`):

- A14 bases: **12 checked, 0 drifted**.
- A14 planned original edits: **6 checked, 0 drifted**.
- Git observation of the active-owner tree: `examdata` HEAD `8da3a0917e017a6cbf5d3e58e1fbeb9d0b0b83c8`,
  49 tracked-modified, 1220 untracked. Recorded as observation, not as a merge claim.

### 2.3 Route inventory and worksheet

- `B00_ROUTE_INVENTORY.json` — method `static_ast_explicit_decorators`, **71 explicit routes**,
  `diff_vs_baseline = { added: [], removed: [] }`. No route added or removed since the baseline.
- `B00_ROUTE_COMPATIBILITY_WORKSHEET.json` — `status: preparation_only`, **71 rows**:
  68 `unchanged` + 3 `line_shift_only`, 0 `removed_in_current_tree`, 0 routes added by Kimi.
  Per-row `b00_disposition_note` explains the observed disposition.
- **7 rows remain `deferred_active_owner`** (materials + timetable), untouched:
  `GET /api/v1/materials`, `GET /api/v1/materials/cie/in-paper`,
  `GET /api/v1/materials/{material_id}`, `GET /api/v1/materials/{material_id}/content`,
  `GET /api/v1/timetable`, `GET /api/v1/timetable/seasons`, `GET /api/v1/timetable/windows`.
  These are **not** re-classified and **no row is promoted to pass** without a release.

### 2.4 Phase B ledger tool and its rejection suite

`integration-staging/tools/b_ledger_update.py` (Phase B counterpart to the frozen Phase A tool;
sha256 `e65d2594d7527d5cdb81047d3613e5a37dab0792d8287cb43c8a94e553b1f0d7`) enforces, among others:

- versioned `--phase-b-mode` (no silent reuse of `PHASE_A_ISOLATED_ONLY`);
- per-packet `allowed_write_roots` that may never widen the two ledger roots;
- gate opening only with the human four-part credential, one gate at a time, scope must cover every
  declared path, and a gate in `blocked_by` needs an explicit `--allow-unblock`;
- refusal of original-side-effect statuses (`merged_pass`, `deployed`, `live`);
- `staged_pass` only with an explicit `original_changes_applied=false` and evidence-backed pass
  results; every status this tool writes records `original_changes_applied=false` with its basis;
- sealed A records (`A*`) are never modified;
- `--expect-inputs` re-hashes named files (relative to the workspace root) and refuses on digest
  change or missing file;
- atomic write + read-back validation; append-only `history`.

Rejection suite (`test_b_ledger_rejections.py`), run against a private ledger copy via
`EXAMDATA_B_LEDGER` so the real ledger is never touched:

```
[PASS] R1 no-credential            [PASS] R7  sealed-A
[PASS] R2 partial-credential       [PASS] R8  merged_pass
[PASS] R3 unblock-guard            [PASS] R9  widen-roots
[PASS] R4 forged-pass              [PASS] R10 scope-mismatch
[PASS] R4b missing-declaration     [PASS] R11 one-gate-only
[PASS] R5 digest-changed           [PASS] R12 digest-match accepted
[PASS] R5b input-missing           [PASS] R13 partial declares no-original-changes
[PASS] R6 two-gates
ALL REJECTIONS ENFORCED
```

12 rejections + 3 positive controls (R11/R12/R13), exit 0. Evidence:
`evidence/B00/b00b01-20261006T132400/b_ledger_rejections_run_final.txt`.

### 2.5 Tool defects fixed this round

Two real defects were found and fixed in `b_ledger_update.py` while wiring up the suite:

1. `--expect-inputs` resolved relative paths against `LEDGER.parents[2]` (i.e. `docs/`), so a real
   digest change was refused with the misleading reason "missing". Fixed by resolving against the
   workspace root (`WORKSPACE = Path(__file__).resolve().parents[2]`, the api root). R5 now asserts a
   genuine digest mismatch; R5b covers the truly-missing case; R12 is the matching-digest control.
2. `original_changes_applied=false` was recorded only for `staged_pass`; other statuses left it
   `null`. Fixed so every status this tool writes records `original_changes_applied=false` with its
   basis (covered by R13).

A first attempt to register B00 with a stale tool hash was refused by the tool itself (hash guard),
which is the intended behaviour; the registration below used the corrected hash.

## 3. Ledger registration

`execution-ledger.json` — `updated_at 2026-10-06T20:56:09+08:00`, ledger sha256
`793e94d6821915be68711673c8063eb9dfc8350056ba12f10493c019cdac2ef5`:

- Phase A records A00–A15: **16/16 `staged_pass`** (unchanged, sealed).
- B00: **`partial`**, mode `PHASE_B_PENDING_RELEASE`, `original_changes_applied=false`.
- B01–B10: `not_started`.
- Gates: **all seven `false`**, `history_events: 2`, `unexpected_original_changes: []`.

Commands recorded for B00 (seq 1–4) are the freeze, baseline, rejection suite, and the first
registration, all exit 0. (A follow-up backfill of the second registration as seq 5 is tracked in the
ledger `next_action`.)

## 4. Deferred — blocked by a closed gate

`gate:original_paths_released` is closed; **no human release credential exists in this session**.
Therefore the following are **not done** and are recorded as gaps, not passes:

- recording a release and opening `original_paths_released`;
- re-deriving the baseline/worksheet against a released tree;
- re-classifying the 7 `deferred_active_owner` rows;
- starting B01's private-copy three-way reconciliation (needs the released tree).

Exact missing release scope: the human must record `original_paths_released` with instruction text,
timestamp, path scope, and remaining constraints. Opening this gate opens none of the others, and
`staged_pass` is never recorded as `merged_pass`.

## 5. Evidence paths

```
docs/integration/execution/evidence/B00/b00b01-20261006T132400/
  B00_A_SEALED_INPUTS_INDEX.json
  B00_BASELINE.json
  B00_ROUTE_INVENTORY.json
  B00_ROUTE_COMPATIBILITY_WORKSHEET.json
  b_ledger_rejections_run_postfix.txt
  b_ledger_rejections_run_final_r11-stale-scope-fail.txt
  b_ledger_rejections_run_final.txt
  a_sealed_*                        (12 frozen A inputs)
```

## 6. Next action

B01 is gate-blocked. Resume only on an explicit human release; otherwise continue B01's
release-independent preparation in a private copy under `integration-staging/runtime/phase-b/` and
record B01 as `partial`/`blocked` with the exact missing release scope. Do not poll the owner, do not
treat silence or a "done" message as release, and do not force a pass.

## 7. F04: machine-checked dependencies and per-packet gate requirements

`b_ledger_update.py` now enforces, before the `blocked_by` gate guard:

- **Dependency completeness** — a `staged_pass` is refused while any listed dependency is
  not in a complete status (`staged_pass` / `merged_pass` / `done`). Refusal text:
  `REFUSED: <task> dependencies are not complete: <dep>=<status>`.
- **Per-packet gate requirement** — a `staged_pass` is refused while any gate the packet's
  guarded action needs is closed and `--private-preparation-only` is absent. Refusal text:
  `REFUSED: <task> requires gate(s) [...] for its guarded action`. With
  `--private-preparation-only` the pass is recorded and the record marks
  `guarded_action_gates_open=false` and the still-missing gates in
  `guarded_action_gates_missing`.
- `--validate-only` now emits `packet_checks` for every B packet (status, dependencies,
  `dependencies_incomplete`, `required_gates`, `required_gates_missing`,
  `guarded_action_open`).

Gate requirements per packet: B00/B01/B04/B09 need `original_paths_released`;
B02/B06/B07 add `existing_service_cutover_authorized`; B03 adds `real_data_write_authorized`;
B05 adds `upstream_requests_authorized`; B08 needs `real_data_write_authorized`; B10 adds
`remote_deployment_authorized` and `original_cleanup_authorized`.

Rejection suite extended to **R1–R15b (18 checks, all PASS, exit 0)**:

- R14 — B01 depends on B00=`partial` → refused on dependencies.
- R15 — B00's guarded action needs `original_paths_released` (closed) → refused on the gate
  check.
- R15b — positive control: with the dependency complete and `original_paths_released` open, a
  `--private-preparation-only` `staged_pass` on B02 is accepted and records
  `guarded_action_gates_open=false`, `guarded_action_gates_missing=["existing_service_cutover_authorized"]`,
  `original_changes_applied=false`.

Tool sha256 after the F04 change: `ac9b01cbfc2733496f5041aa4cd0ace879a0ac8e40aae97c3c9a951ee1dd62b8`.

Note on `mode`: the ledger's top-level `mode` remains `PHASE_A_ISOLATED_ONLY` — the workspace
safety posture is unchanged (no original path released, all seven gates closed). Each B packet
carries its own lifecycle mode `PHASE_B_PENDING_RELEASE`. This is intentional, not a stale field.

Evidence: `b_ledger_rejections_run_f04.txt`, `b_ledger_validate_packet_checks.txt`,
`b_ledger_registration_f04.txt`.

