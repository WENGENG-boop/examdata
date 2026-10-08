# R0104 private progress ledger

Generated: 2026-10-06T23:07:30+08:00  
Kind: **private progress ledger** (not the live execution ledger).

The live execution ledger `docs/integration/execution/execution-ledger.json` is byte-unchanged at `6d4449d3997b…`, all 7 gates `open: false`. This file is a private progress record and does not replace it.

Status: `private_repair_complete_pending_human_release`. Not claimed: merged_pass, deployment, full B00/B01 completion.

## Changed counts

| count | value |
| --- | --- |
| edited staged files | 8 |
| new staged files | 1 |
| collateral staging tool edits | 7 |
| changed files total | 16 |
| diff artifacts | 6 |
| R04 candidates | 2 |

## Test counts and what changed

- **R01-R03 guards** — exit 0, 36/36 checks passed. New R01/R02/R03 guard suite written for this repair; all 36 checks are new, so there is no earlier count to compare against.
- **Isolated staged suite** — post-fix exit 0, 887 passed / 0 failed; pre-fix exit 1, 886 passed / 1 failed. The collected test count is unchanged at 887 in both runs. Pre-fix the run was 886 passed / 1 failed (exit 1): tests/test_config_resolution.py::test_config_file_outside_staging_refused failed with a PermissionError message mismatch from runtime/paths.py. The fix introduced PathOutsideRootError and the test now asserts it, moving that one test from fail to pass: 886 + 1 = 887 passed, exit 0. The delta is explained entirely by that one test outcome; no test was added or removed.
- **Pre-existing rejection suite** — exit 1, 17/18 passed, failing: R15b. Historical control kept byte-identical. 17 of 18 checks pass. R15b fails by design: it expects guarded_action_gates_missing == ['existing_service_cutover_authorized'], the pre-R03 packet-wide model. Under the corrected action-level model B02's primary action config_integration needs only original_paths_released (open), so missing == [] and the guarded action stays open=False. The corrected expectation is a positive control in the new guard suite.
- **R04 layout probes** — exit 0, verdict `target_layout_valid_private_only`, findings 0, 4/4 probes exit 0. Two candidates x two probes = 4 probe runs, all exit 0. Both candidates produce identical counts, so the numbers are reported as one value per candidate; the lists above hold one entry per candidate. No PYTHONPATH and no staging-root override in any probe environment.

## Artifacts

- change_manifest: `integration-staging/runtime/r0104-repair-20261006/evidence/R0104_CHANGE_MANIFEST.json`
- change_manifest_sha256: `6c77d80940c98d44ea3ddf17c81f689ee8af66eeea4ca502ff75628006076d36`
- merge_proposal: `docs/integration/execution/R0104_MERGE_PROPOSAL.json`
- rollback_proposal: `docs/integration/execution/R0104_ROLLBACK_PROPOSAL.json`
- review_report: `docs/integration/execution/R0104_REPAIR_REPORT.md`
- layout_validation: `docs/integration/execution/evidence/R0104/r0104-repair-20261006/R04_LAYOUT_VALIDATION.json`
- diffs: `integration-staging/runtime/r0104-repair-20261006/evidence/DIFFS/`
- transcripts: `integration-staging/runtime/r0104-repair-20261006/evidence/rerun_r0104_ledger_guards.txt`, `integration-staging/runtime/r0104-repair-20261006/evidence/rerun_regression_rejections.txt`, `integration-staging/runtime/r0104-repair-20261006/evidence/rerun_staged_suite.txt`, `integration-staging/runtime/r0104-repair-20261006/evidence/rerun_r04_build.txt`, `integration-staging/runtime/r0104-repair-20261006/evidence/rerun_r04_validate.txt`, `integration-staging/runtime/r0104-repair-20261006/evidence/staged_suite_run_pre_fix.txt`

## Remaining blockers

- original-project reconciliation awaits an explicit human release opening original_paths_released with an explicit scope
- real Node/source validation against the original tree stays not_run (not authorized)
- the pre-existing rejection suite keeps its stale R15b expectation until a human decides

## Not run

- real Node component execution (ielts-api / toefl-api) against the original tree
- any original-project source validation
- original merge, deployment, service cutover, upstream request, real data write
- original cleanup
