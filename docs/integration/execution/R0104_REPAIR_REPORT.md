# R01–R04 repair report (private preparation only)

Date: 2026-10-06, Asia/Shanghai.
Run id: `r0104-repair-20261006`.
Source review: `docs/integration/execution/B00_B01_REVIEW_2026-10-06.md`.

## Verdict

The four review findings are corrected inside the two Phase A write roots. The private
repair is complete and verified. **Nothing has been merged into the original project and
nothing has been deployed.** All seven ledger gates are still `open: false`. The live
execution ledger is byte-unchanged at
`6d4449d3997b437fd3ea3a1fe7925fc78a7c0adbe0a5d3b793d6a8063101b4ba`.

This report does **not** claim `merged_pass`, deployment, or full B00/B01 completion.
The original-project reconciliation remains blocked pending an explicit human release.

## Scope and gate state

Write roots used, and only these:

- `integration-staging/`
- `docs/integration/execution/`

Not touched: original project source (`examdata/**`), any database, any service, any Kimi
output, and any sealed A record or evidence under
`docs/integration/execution/evidence/**`.

Gate observation at report time (`docs/integration/execution/execution-ledger.json`):

| item | value |
| --- | --- |
| ledger sha256 | `6d4449d3997b437fd3ea3a1fe7925fc78a7c0adbe0a5d3b793d6a8063101b4ba` (expected value, unchanged) |
| ledger `updated_at` | `2026-10-06T21:39:26+08:00` (last B01 write; no write since) |
| gates | 7 of 7 `open: false` |
| tasks | 27 |
| `unexpected_original_changes` | 0 |

## What changed

Sixteen files changed in the staging write root: eight edited staged files, one new staged
file, and seven collateral staging tools. Full per-file hashes, baselines and diff pointers
are in `integration-staging/runtime/r0104-repair-20261006/evidence/R0104_CHANGE_MANIFEST.json`.

### R01 — unsupported `done` status bypassed completion validation

`integration-staging/tools/b_ledger_update.py` now validates `--status` against an explicit
schema (`STATUSES`), refuses any status in `CLAIM_STATUSES` (`done`, `merged_pass`, `live`,
`deployed`, …) because those claim original-side effects this tool cannot validate, and
refuses unknown aliases with the allowed list in the message. Completion validation applies
to every status that can satisfy a dependency; `private_preparation` readiness is defined
separately from guarded-action completion.

### R02 — generic patches could overwrite protected invariants

The patch path is now a whitelist. Dependency, gate, ownership, effect and identity fields
(`dependencies`, `blocked_by`, `original_changes_applied`, `original_changes_applied_basis`,
`guarded_action_gates_open`, `guarded_action_gates_missing`, `action`, `status`, `mode`,
`task_id`, `allowed_write_roots`, `updated_at`, …) are reserved and any attempt to set them
via `--patch-file` is refused, as is any unknown patch field. The complete candidate record is
constructed and validated **before** the atomic publish; on any refusal the ledger file is not
written, so the ledger bytes are unchanged. Dependency changes require a dedicated audited
operation, not a generic patch.

### R03 — packet-wide gate requirements blocked independent work

Gate requirements are now **action-level**. Each packet declares the gates for each action it
performs (`PACKET_ACTIONS`), and `private_preparation` requires no gate at all. A
`private_preparation` pass never covers the packet's guarded action: the record is written with
`guarded_action_gates_open = False` and `guarded_action_gates_missing` set from the *primary*
action's gates, and such a pass no longer satisfies a non-private dependency
(`deps_incomplete` rejects a dependency that carries only a private-preparation pass). Live
service, live data, upstream, deployment and cleanup authorization are required only by the
action that performs that effect.

### R04 — target-layout runtime imports were broken

The product package no longer imports `..testing.guards`. A new module
`integration-staging/src/examdata_integration/runtime/paths.py` resolves the deployment/data
root from explicit configuration (`EXAMDATA_INTEGRATION_ROOT`, or an explicit argument) and
never from the directory name. Five product modules were re-pointed at it
(`runtime/manifest.py`, `runtime/runner.py`, `runtime/settings.py`, `api/dataset.py`,
`adapters/source_reader.py`, which previously used `parents[3]`). The isolation checks stay in
the test harness: `tests/conftest.py` now sets `EXAMDATA_INTEGRATION_ROOT` explicitly and the
harness keeps denying original paths. No staging-name workaround was added, the path guard was
not weakened, and the sealed candidate was not modified.

A new versioned private candidate was built and validated:
`integration-staging/runtime/r0104-repair-20261006/candidates/r04-target-layout-v2`
and the same tree copied under an arbitrary directory name
`.../candidates/R04 目标 layout ünïcode` (spaces plus non-ASCII).

## Code diffs

Unified diffs are in `integration-staging/runtime/r0104-repair-20261006/evidence/DIFFS/`:

| diff | lines | sha256 (first 12) |
| --- | --- | --- |
| `b_ledger_update.patch` | 979 | `108ddd88cf38` |
| `runtime_settings.py.patch` | 39 | `fb6fcda950a1` |
| `runtime_manifest.py.patch` | 20 | `6ba8e60f2642` |
| `runtime_runner.py.patch` | 20 | `8bc1542b8008` |
| `adapters_source_reader.py.patch` | 14 | `3354d7ee6d5a` |
| `api_dataset.py.patch` | 13 | `cda48d8fdd09` |

`runtime/paths.py` is a new 65-line file, so it has no patch. The seven collateral staging
tools each gained one `os.environ.setdefault("EXAMDATA_INTEGRATION_ROOT", …)` line (exact line
numbers in the change manifest); they have no pre-change snapshot in the run tree, so they are
recorded as added lines rather than patches.

Key hashes:

| file | before | after |
| --- | --- | --- |
| `integration-staging/tools/b_ledger_update.py` | `ac9b01cbfc2733496f5041aa4cd0ace879a0ac8e40aae97c3c9a951ee1dd62b8` (frozen pre-fix copy) | `ec80a56ac2c950e9c7fa3ccb87acfe24c336c515a3235b92260c99e899f2702b` |
| `.../src/examdata_integration/runtime/paths.py` | — (new) | `d0207fc79d66…` |
| `.../src/examdata_integration/runtime/manifest.py` | `8a56f668cc72…` | `7ff0e084db5d…` |
| `.../src/examdata_integration/runtime/runner.py` | `5d45f6de87fb…` | `75001ddba5a6…` |
| `.../src/examdata_integration/runtime/settings.py` | `94e825030d13…` | `320f9e39fe65…` |
| `.../src/examdata_integration/api/dataset.py` | `5801f31c5c17…` | `c341ce3018f1…` |
| `.../src/examdata_integration/adapters/source_reader.py` | `42505ce1eb4a…` | `eb77e0004d3a…` |
| `integration-staging/tests/conftest.py` | `d15742bd1810…` | `4b28ad52a9bb…` |
| `integration-staging/tests/test_config_resolution.py` | `18cd2340adf0…` | `cc0a8fb6611d…` |

Baseline validity: of the 247 staged files recorded in `A14_MERGE_MAP.json`, 240 are still
byte-identical and exactly the 7 R04-edited staged files differ. The staged tree was therefore
stable from A14 (`2026-10-06T11:43+08:00`) until the R04 edits, so the A14 `staged_sha256` is a
valid pre-change baseline for those 7 files.

## Exact commands and results

All commands run from `C:/Users/weo/Desktop/api`.

| # | command | exit | result | transcript |
| --- | --- | --- | --- | --- |
| 1 | `./examdata/.venv/Scripts/python.exe integration-staging/runtime/r0104-repair-20261006/test_r0104_ledger_guards.py` | 0 | 36/36 checks passed, `ALL R01-R03 GUARDS ENFORCED` | `evidence/rerun_r0104_ledger_guards.txt` |
| 2 | `./examdata/.venv/Scripts/python.exe integration-staging/runtime/r0104-repair-20261006/regression/test_b_ledger_rejections.py` | 1 | 17 `[PASS]`, 1 `[FAIL]` (R15b, intentional — see below) | `evidence/rerun_regression_rejections.txt` |
| 3 | `bash integration-staging/tools/run_staged_tests.sh -q` | 0 | `887 passed, 1 warning in 47.78s` | `evidence/rerun_staged_suite.txt` |
| 4 | `./examdata/.venv/Scripts/python.exe integration-staging/runtime/r0104-repair-20261006/r04_build_candidate.py` | 0 | both candidates `all_ok: true` | `evidence/rerun_r04_build.txt` |
| 5 | `./examdata/.venv/Scripts/python.exe integration-staging/runtime/r0104-repair-20261006/r04_validate_layout.py` | 0 | `verdict: target_layout_valid_private_only`, `findings: []`, 4/4 probes exit 0 | `evidence/rerun_r04_validate.txt` |
| 6 | `./examdata/.venv/Scripts/python.exe integration-staging/runtime/r0104-repair-20261006/r0104_build_manifest.py` | 0 | change manifest written | — |
| 7 | `./examdata/.venv/Scripts/python.exe integration-staging/runtime/r0104-repair-20261006/r0104_build_proposals.py` | 0 | merge + rollback proposals written | — |

### Negative results — what is now refused (exit 2, ledger bytes preserved)

- R01: `--status done` (the original bypass), `merged_pass`, `live`, `deployed`; aliases
  `complete`, `finished`, `DONE`, `staged_pass_`; `done` with evidence supplied.
- R02: patch setting `original_changes_applied` (the original bypass), patch clearing
  `dependencies` + `blocked_by` (the original bypass), prerequisite-removal-then-completion,
  and patches touching `status`, `mode`, `task_id`, `action`, `guarded_action_gates_open`,
  `guarded_action_gates_missing`, `allowed_write_roots`, `updated_at`, plus unknown fields.
- R02: `--original-changes-applied true` on a private-preparation tool.
- R03: `service_cutover` on B02 without `existing_service_cutover_authorized`; unknown action;
  a dependency that carries only a private-preparation pass.
- Pre-existing suite: no-credential gate opening, partial credential, unblock guard,
  forged pass, input-digest change/missing, two gates at once, sealed-A modification,
  `merged_pass`, widened roots, scope mismatch, missing declaration, incomplete dependency,
  closed gate.

### Positive controls

- Legitimate partial progress is accepted and the record is truthful (`status=partial`,
  `original_changes_applied=false`).
- A private-preparation pass is accepted with no gate open, and records
  `action=private_preparation open=False missing=[]` — the guarded action stays uncovered.
- Opening a release gate with a synthetic credential in an explicitly labelled private fixture
  succeeds (and only in the private ledger copy).

## The one intentional regression: R15b

The pre-existing suite `test_b_ledger_rejections.py` is retained **byte-identical** as a
historical control (original in `runtime/phase-b/b00b01-20261006T132400/`; the copy in
`regression/` matches it). It contains 18 checks; 17 pass and R15b fails, because its
expectation encodes the pre-R03 packet-wide model:

```
guarded_action_gates_missing == ["existing_service_cutover_authorized"]
```

Under the corrected action-level model, B02's primary action is `config_integration`, which
requires only `original_paths_released` — open in that scenario — so
`guarded_action_gates_missing == []`, while `guarded_action_gates_open` stays `False` because a
private-preparation pass never covers the packet's guarded action. The pass is still accepted
(both subprocesses exit 0, which is what the `open=0 act=0` in the printed line means — those
are return codes, not gate fields); only the stale expectation on `missing` fails. This is the
R03 correction working as specified, and the corrected expectation is asserted as a positive
control in the new guard suite
(`POS private-prep guarded action uncovered: action=private_preparation open=False missing=[]`).

The sealed F04 transcript
(`docs/integration/execution/evidence/B00/b00b01-20261006T132400/b_ledger_rejections_run_f04.txt`,
tool sha256 `ac9b01cb…`) shows the same 18 checks all passing under the pre-fix tool, with
`missing=["existing_service_cutover_authorized"]` — confirming the failure is the intended
semantic change and not a new defect.

## R04 candidate import status

Both candidates pass every probe, run with `PYTHONPATH` removed and no staging-root override
(the validator deletes `PYTHONPATH` and `EXAMDATA_INTEGRATION_STAGING_ROOT` and fails if either
is present; the root is supplied explicitly through `EXAMDATA_INTEGRATION_ROOT`).

| probe | r04-target-layout-v2 | `R04 目标 layout ünïcode` |
| --- | --- | --- |
| import probe exit | 0 | 0 |
| modules walked | 62 | 62 |
| entry points | 9 | 9 |
| import errors | 0 | 0 |
| modules outside candidate | 0 | 0 |
| `pythonpath_env` | `None` | `None` |
| `staging_override_present` | `False` | `False` |
| `examdata_within_candidate` | `True` | `True` |
| resource probe exit | 0 | 0 |
| entry points OK | 9 | 9 |
| schema files / loaded OK | 28 / 28 | 28 / 28 |
| synthetic node components admitted | 1 | 1 |
| checks / failed | 26 / 0 | 26 / 0 |

Candidate manifests:
`candidates/r04-target-layout-v2/R04_CANDIDATE_MANIFEST.json` (`923e7a298179…`, 182 files) and
`candidates/R04 目标 layout ünïcode/R04_CANDIDATE_MANIFEST.json` (`3ed586ab6437…`, 182 files).
Machine-readable evidence:
`docs/integration/execution/evidence/R0104/r0104-repair-20261006/R04_LAYOUT_VALIDATION.json`
plus the four `probe_*.json` files.

Real Node/source validation against the original tree remains `not_run`.

## Regenerated artifacts (no frozen evidence overwritten)

| artifact | path |
| --- | --- |
| change manifest (per-file hashes) | `integration-staging/runtime/r0104-repair-20261006/evidence/R0104_CHANGE_MANIFEST.json` |
| merge proposal | `docs/integration/execution/R0104_MERGE_PROPOSAL.json` / `.md` |
| rollback proposal | `docs/integration/execution/R0104_ROLLBACK_PROPOSAL.json` / `.md` |
| candidate manifests | the two `R04_CANDIDATE_MANIFEST.json` above |
| progress ledger | `docs/integration/execution/R0104_PROGRESS_LEDGER.json` / `.md` |
| layout validation evidence | `docs/integration/execution/evidence/R0104/r0104-repair-20261006/` |

Merge/rollback proposals are proposals only: 16 entries, 8 require `original_paths_released`
(the product and test files), 8 are staging-only tooling with no original-project action.
Nothing in them has been applied.

## Unchanged observations

| item | sha256 / state |
| --- | --- |
| `docs/integration/execution/execution-ledger.json` | `6d4449d3997b…` — unchanged; gates 7/7 closed |
| `docs/integration/execution/A14_MERGE_MAP.json` | `29940a0b0582…` — unchanged |
| `docs/integration/execution/A14_RELEASE_MANIFEST.json` | `ae938da2e35e…` — unchanged |
| `evidence/B00/**` | 23 files, tree `4885490c6b44…`, newest mtime `2026-10-06T21:27:28+08:00` |
| `evidence/B01/**` | 13 files, tree `be49454739e0…`, newest mtime `2026-10-06T21:39:26+08:00` |

## Process observation PO-1

The pre-existing rejection suite was run **in place** inside its own private Phase B run tree
before being copied for the post-fix run. That regenerated the suite's own outputs at
`integration-staging/runtime/phase-b/b00b01-20261006T132400/` between
`2026-10-06T22:11:49+08:00` and `2026-10-06T22:13:08+08:00`: its ten fixture files
(`cred_*.json`, `inputs_*.json`, `patch_*.json`) and four `ledger-copy/execution-ledger*.json`
copies. `test_b_ledger_rejections.py` writes exactly those files under its own run directory on
every execution, so these are its self-generated artifacts, not sealed evidence.

Sealed evidence (`docs/integration/execution/evidence/**`), the live ledger, and the original
project were not affected. The immediate pre-22:11 bytes of those self-generated fixtures are
not archived, so the regeneration cannot be byte-diffed against them; the script is
deterministic (fixed JSON literals plus copies of the unchanged live ledger). Recorded
truthfully in `R0104_CHANGE_MANIFEST.json` under `process_observations`.

## Not run

- Real Node component execution (`ielts-api`, `toefl-api`) against the original tree.
- Any original-project source validation.
- Original merge, deployment, service cutover, upstream request, real data write, cleanup.
- Opening any real gate (synthetic credentials used only in explicitly labelled private
  fixtures).

## Remaining blockers

1. **Original-project reconciliation** is blocked pending an explicit human release opening
   `original_paths_released` with an explicit scope. Until then no staged file is merged and
   the merge/rollback proposals stay unapplied.
2. Real Node/source validation against the original tree stays `not_run` because it is not
   authorized.
3. The pre-existing rejection suite keeps its stale R15b expectation until a human decides
   whether to update that historical control.
