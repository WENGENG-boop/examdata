# B07R — findings-to-tests matrix

Run: `b07-reviewfix-20261007-fzgu78c6`. Status: private, unmerged, undeployed.
Red evidence = tests failing against the frozen v1 implementation
(`evidence/step2_frozen_red_run2.log`, 18 failed / 8 passed). Green evidence =
the same durable tests against candidate v2
(`evidence/step6_candidate_regression_run1.log`, 26 passed). Every test asserts
at import that `examdata` resolves inside the intended candidate root
(`tests/b07r_common.py`; origin record: `evidence/step6_import_origin.txt`).

## Findings table

| Finding | Test node IDs (`tests/…`) | v1 | v2 | Module under test (v2 line refs) |
|---------|---------------------------|----|----|----------------------------------|
| **F1** identity-known must not become verified without quality evidence | `test_b07r_published_semantics.py::test_f1_identity_known_unverified_entry_is_not_verified` | FAIL | PASS | `operations/published.py` `_quality_bucket` L237, `build_published` L319 |
| F1 | `…::test_f1_verified_requires_content_and_answer_verification` | FAIL | PASS | same |
| F1 (guard) | `…::test_f1_identity_rules_still_hold` | pass | PASS | same |
| **F2** expected/observed conflicts never complete; counts stay distinct | `…::test_f2_expected_below_published_is_never_complete` | FAIL | PASS | `operations/published.py` `_coverage_row` L254 |
| F2 | `…::test_f2_missing_entries_stay_on_the_expected_side` | FAIL | PASS | same |
| F2 | `…::test_f2_zero_expected_empty_scope_is_not_complete` | FAIL | PASS | same |
| F2 | `…::test_f2_zero_expected_with_published_entries_is_a_conflict` | FAIL | PASS | same |
| F2 | `…::test_f2_exclusions_and_manifest_partials_keep_reasons` | FAIL | PASS | same |
| F2 (guard) | `…::test_f2_unknown_denominator_never_claims_completion` | pass | PASS | same |
| Multi-scope processing (F2 semantics across iterables) | `…::test_multi_scope_processing_accepts_supported_iterables[generator]` | FAIL | PASS | `operations/published.py` `build_published` L319 |
| Multi-scope (guards) | `…::test_multi_scope_processing_accepts_supported_iterables[list\|tuple]` | pass | PASS | same |
| Contract (response shape unchanged) | `…::test_published_rows_keep_contract_fields_and_validate` | pass | PASS | `operations/published.py` |
| **F3** scan budgets bound discovery + attempted work | `test_b07r_scan_budgets.py::test_f3_attempt_budget_counts_skipped_files` | FAIL | PASS | `operations/jobs.py` L60-64, `scan_checkpoint_root` L131 |
| F3 | `…::test_f3_attempt_budget_exact_and_over_limit` | FAIL | PASS | same |
| F3 | `…::test_f3_directory_entry_budget_bounds_discovery` | FAIL | PASS | `operations/checkpoints.py` `_CheckpointPathWalk` L301, `iter_checkpoint_paths` L372 |
| F3 | `…::test_f3_retained_result_budget_bounds_skips` | FAIL | PASS | `operations/jobs.py` L62 |
| F3 | `…::test_f3_read_byte_budget_bounds_cumulative_reads` | FAIL | PASS | `operations/jobs.py` L64; `checkpoints.py` `read_checkpoint_bounded` L190 |
| F3 | `…::test_f3_unreadable_file_is_an_attempted_file` | FAIL | PASS | `operations/jobs.py` `scan_checkpoint_root` L131 |
| F3 | `…::test_f3_walk_order_is_deterministic_and_lazy` | FAIL | PASS | `operations/checkpoints.py` L301/L372 |
| F3 (guard: oversized file already skipped on v1) | `…::test_f3_oversized_file_is_skipped_and_counts_are_reported` | pass | PASS | `operations/checkpoints.py` `CheckpointTooLargeError` L51 |
| **F4** public sanitization covers dynamic mapping keys | `test_b07r_sanitize_keys.py::test_f4_secret_and_path_keys_are_redacted_without_losing_entries` | FAIL | PASS | `operations/jobs.py` `sanitize_tree` L80 |
| F4 | `…::test_f4_operations_projection_redacts_keys` | FAIL | PASS | `operations/jobs.py` `to_public` L274 / projection path |
| F4 | `…::test_f4_http_routes_redact_keys` | FAIL | PASS | real candidate public projection + HTTP handler (FastAPI testclient, synthetic fixtures) |
| F4 (guards) | `…::test_f4_nested_lists_keep_record_counts`, `…::test_f4_fixed_schema_keys_and_counts_survive` | pass | PASS | `operations/jobs.py` `sanitize_tree` L80 |

## Notes

- The red run leaves 8 passing tests on v1: three are intentional guards that
  hold before and after (`f1_identity_rules_still_hold`,
  `f2_unknown_denominator`, `f3_oversized`), three are contract/preservation
  checks (`published_rows_keep_contract_fields`, `f4_nested_lists`,
  `f4_fixed_schema_keys`), and two are the `[list]`/`[tuple]` multi-scope
  variants. None of them is used to claim a fix.
- The single red check in the frozen route probe
  (`J_published_statuses_pinned`) is the expected consequence of F1/F2 and is
  documented in `evidence/step6_validation_note.md` §5 and
  `evidence/step6_pindiff_v1.json` / `step6_pindiff_v2.json`.
- All tests are durable files under `tests/` and run with
  `PYTHONPATH=<candidate>/src B07R_EXPECT_CANDIDATE_ROOT=<candidate>`; the
  synthetic-fixture discipline is documented in `tests/b07r_common.py`.
