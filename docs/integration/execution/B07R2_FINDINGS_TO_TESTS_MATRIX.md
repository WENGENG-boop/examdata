# B07R2 — findings-to-tests matrix

Run: `b07-reviewfix-20261007-774e4dad` (second private review-fix run).
Status: private, unmerged, undeployed; all seven gates closed.

Red evidence = tests failing against the frozen v1 implementation
(`evidence/step2_frozen_red_run1.log`, 20 failed / 8 passed, 1 warning).
Green evidence = the same durable tests against candidate v2
(`evidence/step6_candidate_regression_run1.log`, 28 passed, 1 warning). Every
test asserts at import that `examdata` resolves inside the intended candidate
root (`tests/b07r2_common.py`; origin record: `evidence/step6_import_origin.txt`).

## Findings table

| Finding | Test node IDs (`tests/…`) | v1 | v2 | Module under test (v2 line refs) |
|---------|---------------------------|----|----|----------------------------------|
| **F1** identity-known must not become verified without quality evidence | `test_b07r2_published_semantics.py::test_f1_review_reproduction_partial_unverified_entry_is_not_verified` | FAIL | PASS | `operations/published.py` `_quality_bucket` L225, `_content_complete` L210, `_answers_verified` L215 |
| F1 | `…::test_f1_verified_requires_content_and_answer_verification` | FAIL | PASS | same |
| F1 (guard) | `…::test_f1_identity_rules_still_hold` | pass | PASS | same |
| **F2** expected/observed conflicts never complete; counts stay distinct | `…::test_f2_review_reproduction_expected_below_published_is_not_complete` | FAIL | PASS | `operations/published.py` `_coverage_row` L240, `expected_below_published` L270 |
| F2 | `…::test_f2_missing_entries_stay_on_the_observed_side` | FAIL | PASS | same |
| F2 | `…::test_f2_zero_expected_empty_scope_is_not_complete` | FAIL | PASS | same |
| F2 | `…::test_f2_zero_expected_with_published_entries_is_a_conflict` | FAIL | PASS | same |
| F2 | `…::test_f2_exclusions_and_manifest_partials_keep_reasons` | FAIL | PASS | same |
| F2 (guard) | `…::test_f2_unknown_denominator_never_claims_completion` | pass | PASS | same |
| Multi-scope processing (F2 semantics across iterables) | `…::test_multi_scope_processing_accepts_supported_iterables[generator]` | FAIL | PASS | `operations/published.py` `build_published` L312, `entries = list(entries)` L318 |
| Multi-scope (guards) | `…::test_multi_scope_processing_accepts_supported_iterables[list\|tuple]` | pass | PASS | same |
| Contract (response shape unchanged) | `…::test_published_rows_keep_contract_fields_and_validate` | pass | PASS | `operations/published.py` (`Coverage.from_dict(row).validate() == []`) |
| **F3** scan budgets bound discovery + attempted work | `test_b07r2_scan_budgets.py::test_f3_review_reproduction_attempt_budget_counts_skipped_files` | FAIL | PASS | `operations/jobs.py` budgets L58–62, `scan_checkpoint_root` L148 |
| F3 | `…::test_f3_attempt_budget_exact_and_over_limit` | FAIL | PASS | same |
| F3 | `…::test_f3_directory_entry_budget_bounds_discovery` | FAIL | PASS | `operations/checkpoints.py` `_CheckpointPathWalk` L315, `iter_checkpoint_paths` L395 |
| F3 | `…::test_f3_retained_result_budget_bounds_skips` | FAIL | PASS | `operations/jobs.py` `MAX_SKIPPED_RESULTS` L61, `_retain_skip` L133 |
| F3 | `…::test_f3_read_byte_budget_bounds_cumulative_reads` | FAIL | PASS | `operations/jobs.py` `MAX_READ_BYTES` L62; `operations/checkpoints.py` `read_checkpoint_bounded` L202 |
| F3 | `…::test_f3_bounded_read_refuses_an_oversized_file` | FAIL | PASS | `operations/checkpoints.py` `CheckpointTooLargeError` L51, `DEFAULT_MAX_CHECKPOINT_BYTES` L64, `read_checkpoint_bounded` L202 |
| F3 | `…::test_f3_unreadable_file_is_an_attempted_file` | FAIL | PASS | `operations/jobs.py` `scan_checkpoint_root` L148 |
| F3 | `…::test_f3_walk_order_is_deterministic_and_lazy` | FAIL | PASS | `operations/checkpoints.py` L315 / L395 |
| F3 (guard: oversized file already skipped on v1) | `…::test_f3_oversized_file_is_skipped_and_counts_are_reported` | pass | PASS | `operations/checkpoints.py` `CheckpointTooLargeError` L51 |
| **F4** public sanitization covers dynamic mapping keys | `test_b07r2_sanitize_keys.py::test_f4_review_reproduction_secret_and_path_keys_are_redacted` | FAIL | PASS | `operations/jobs.py` `sanitize_tree` L78 |
| F4 | `…::test_f4_collision_suffix_never_overwrites_an_existing_key` | FAIL | PASS | same |
| F4 | `…::test_f4_operations_projection_redacts_keys` | FAIL | PASS | `operations/jobs.py` `sanitize_tree` L78 via `api/dataset.py` `to_public` L451 / `operations_view` L470 |
| F4 | `…::test_f4_http_routes_redact_keys` | FAIL | PASS | real candidate HTTP handler: `api/app.py` `create_app` + `api/links.py` `spec_for`; routes `/coverage` and `/jobs/{id}` (FastAPI testclient, synthetic fixtures) |
| F4 (guards) | `…::test_f4_nested_lists_keep_record_counts`, `…::test_f4_fixed_schema_keys_and_counts_survive` | pass | PASS | `operations/jobs.py` `sanitize_tree` L78 |

## Notes

- The red run leaves 8 passing tests on v1: five are intentional guards that
  hold before and after (`f1_identity_rules_still_hold`,
  `f2_unknown_denominator`, `f3_oversized`, `f4_nested_lists`,
  `f4_fixed_schema_keys`), one is the contract/preservation check
  (`published_rows_keep_contract_fields_and_validate`), and two are the
  `[list]`/`[tuple]` multi-scope variants. None of them is used to claim a fix.
- The single red check in the frozen route probe
  (`J_published_statuses_pinned`) is the expected consequence of F1/F2 and is
  documented in `evidence/step6_validation_note.md` §5 and
  `evidence/step6_pindiff_v1.json` / `step6_pindiff_v2.json`.
- All tests are durable files under `tests/` and run with
  `PYTHONPATH=<candidate>/src B07R2_EXPECT_CANDIDATE_ROOT=<candidate>`; the
  synthetic-fixture discipline is documented in `tests/b07r2_common.py`.
