# B07 rehearsal review report (private preparation only)

Generated: 2026-10-07T07:40:51+08:00  
Packet: **B07** — operations view (jobs / coverage / diagnostics) over the private read API  
Status: `b07_private_rehearsal_complete_pending_human_release`  
Probe verdict: `b07_rehearsal_valid_private_only`  
Probe findings: 0

Nothing in this report has been merged or deployed. The original project was not read, imported or written by any B07 step. All seven gates are closed.

## 1. What B07 rehearsed

B07 owns the operations view over the private read API (jobs / coverage / diagnostics). What can be done without the human release is a rehearsal: carry the B06 candidate byte-for-byte, rewrite two modules — `app.py` (operations routes and diagnostics wiring) and `dataset.py` (operations projections) — and add the new `src/examdata/integration/operations/` package: `jobs.py` (read-only job views over a configured operations root; stopped jobs stay stopped and nothing is resumed or written back) and `published.py` (sanitized published-coverage projections with no raw paths, keys or secrets on any leaf), plus a fully synthetic operations fixture root (ten labelled files incl. seven batch checkpoints; proposed install target `examdata/tests/integration/fixtures/synthetic/operations/operations-root/`). The acceptance properties that do not need the original tree are then proven by the route probe: the J section drives the candidate's operations view through the synthetic fixture root (current-only jobs, checkpoint stages with superseded handling, a stopped 9191 batch flagged for resume with its error fixture-redacted, coverage and published projections without the internal schema tag, and the guarantee that the view leaves the candidate tree unchanged), while the carried B06 surface (frontend tree, discovery semantics and the private cross-stack rehearsal) is re-proven unchanged.

## 2. Candidate and lineage

- Candidate: `integration-staging/runtime/b07-rehearsal-2026-10-07/candidates/b07-operations-v1`
- Parent: `integration-staging/runtime/b06-rehearsal-2026-10-07/candidates/b06-frontend-v1` (the B06 frontend candidate)
- Parent tree: 208 files, sha256 `ffe774db608ff9d86246458a38265f9baa760b40880e48197e84d887f85d53f4`
- Candidate tree: 221 files (209 copied from the parent, of which 207 stay verbatim and 2 were rewritten, + 12 new operations files), sha256 `5df259843b26792910de697b2c646fc413c5b936edf3d95d04baf7afa482c179`
- Candidate digest reproducible from the tree on disk: `True` (re-checked independently by the validator, not just self-reported by the builder)
- Parent manifest sha256 unchanged at build time: `9af2e849573033aceb9e4b5f0acbea1d62b91565d8b87526b99e0a3db75b82cb`
- Count explanation: B06's digest covered 208 files and its on-disk non-cache count was 209 (208 + B06 manifest). B07 copies all 209, rewrites 2 and adds 12, so the candidate digest covers 221 = 207 verbatim + 2 rewritten + 12 new, and on-disk is 222 = 221 + the B07 manifest; the candidate carries no __pycache__ files (PYTHONDONTWRITEBYTECODE=1 throughout).

The rewritten `app.py` supersedes B06 BP-0002 (chain: A14 MM-0015 → B05 BP-0004 → B06 BP-0002 → B07) and the rewritten `dataset.py` supersedes B06 BP-0003 (chain: A14 MM-0017 → R0104 RP-0005 → B05 BP-0003 → B06 BP-0003 → B07); the two new operations modules and the ten fixture files are new against the parent. The merge proposal re-verifies all of this in its 11 digest checks (`supersession_chains_match`, `new_modules_match_sources`, `operations_fixture_files_match_sources`, `operations_target_conventions_match_b01`, `b06_merge_crossref_matches`, `parent_tree_reverified`, `candidate_tree_reverified`), all true.

## 3. Commands, working directory and exit codes

| Step | Command | cwd | Exit |
| --- | --- | --- | --- |
| build candidate, first pass | `PYTHONIOENCODING=utf-8 PYTHONDONTWRITEBYTECODE=1 C:/Users/weo/Desktop/api/examdata/.venv/Scripts/python.exe b07_build_candidate.py 1> evidence/build_run.json 2> evidence/build_run.err; echo EXIT=$?` | `C:/Users/weo/Desktop/api/integration-staging/runtime/b07-rehearsal-2026-10-07` | 0 |
| smoke import, first pass | `PYTHONIOENCODING=utf-8 PYTHONDONTWRITEBYTECODE=1 C:/Users/weo/Desktop/api/examdata/.venv/Scripts/python.exe b07_smoke_import.py 1> evidence/smoke_import.json 2> evidence/smoke_import.err; echo EXIT=$?` | `C:/Users/weo/Desktop/api/integration-staging/runtime/b07-rehearsal-2026-10-07` | 0 |
| build candidate, second pass (the recorded build) | `PYTHONIOENCODING=utf-8 PYTHONDONTWRITEBYTECODE=1 C:/Users/weo/Desktop/api/examdata/.venv/Scripts/python.exe b07_build_candidate.py 1> evidence/build_run.json 2> evidence/build_run.err; echo EXIT=$?` | `C:/Users/weo/Desktop/api/integration-staging/runtime/b07-rehearsal-2026-10-07` | 0 |
| smoke import, second pass (the recorded smoke) | `PYTHONIOENCODING=utf-8 PYTHONDONTWRITEBYTECODE=1 C:/Users/weo/Desktop/api/examdata/.venv/Scripts/python.exe b07_smoke_import.py 1> evidence/smoke_import.json 2> evidence/smoke_import.err; echo EXIT=$?` | `C:/Users/weo/Desktop/api/integration-staging/runtime/b07-rehearsal-2026-10-07` | 0 |
| route probe, first capture attempt (kept) | `B07_CANDIDATE_ROOT="$PWD/candidates/b07-operations-v1" B07_WORKSPACE_ROOT="C:/Users/weo/Desktop/api" B07_TMP_DIR="$PWD/evidence/tmp" EXAMDATA_INTEGRATION_ROOT="$PWD/candidates/b07-operations-v1" EXAMDATA_OPERATIONS_ROOT="$PWD/candidates/b07-operations-v1/fixtures/synthetic/operations/operations-root" EXAMDATA_API_KEY=REDACTED_LOCAL_CREDENTIAL PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8 "C:/Users/weo/Desktop/api/examdata/.venv/Scripts/python.exe" b07_route_probe.py 1> evidence/probe_run1.json 2> evidence/probe_run1.err; echo "probe_exit=$?"` | `C:/Users/weo/Desktop/api/integration-staging/runtime/b07-rehearsal-2026-10-07` | 1 |
| route probe, clean rerun (the archived capture) | `B07_CANDIDATE_ROOT="$PWD/candidates/b07-operations-v1" B07_WORKSPACE_ROOT="C:/Users/weo/Desktop/api" B07_TMP_DIR="$PWD/evidence/tmp" EXAMDATA_INTEGRATION_ROOT="$PWD/candidates/b07-operations-v1" EXAMDATA_OPERATIONS_ROOT="$PWD/candidates/b07-operations-v1/fixtures/synthetic/operations/operations-root" EXAMDATA_API_KEY=REDACTED_LOCAL_CREDENTIAL PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8 "C:/Users/weo/Desktop/api/examdata/.venv/Scripts/python.exe" b07_route_probe.py 1> evidence/probe_run2.json 2> evidence/probe_run2.err; echo "probe_exit=$?"` | `C:/Users/weo/Desktop/api/integration-staging/runtime/b07-rehearsal-2026-10-07` | 0 |
| validate (probe from 3 cwds) | `rm -rf integration-staging/runtime/b07-rehearsal-2026-10-07/__pycache__ && cd integration-staging/runtime/b07-rehearsal-2026-10-07 && PYTHONIOENCODING=utf-8 PYTHONDONTWRITEBYTECODE=1 C:/Users/weo/Desktop/api/examdata/.venv/Scripts/python.exe b07_validate.py; echo "VALIDATE_EXIT=$?"` | `C:/Users/weo/Desktop/api` | 0 |
| isolated staged suite | `bash integration-staging/tools/run_staged_tests.sh -q (background task; its output log was copied to integration-staging/runtime/b07-rehearsal-2026-10-07/evidence/isolated_staged_suite.txt and suite_exit=0 appended)` | `C:/Users/weo/Desktop/api` | 0 |
| merge + rollback proposals | `PYTHONIOENCODING=utf-8 PYTHONDONTWRITEBYTECODE=1 C:/Users/weo/Desktop/api/examdata/.venv/Scripts/python.exe b07_build_proposals.py; echo "EXIT=$?"` | `C:/Users/weo/Desktop/api/integration-staging/runtime/b07-rehearsal-2026-10-07` | 0 |
| review report + progress ledger | `PYTHONIOENCODING=utf-8 PYTHONDONTWRITEBYTECODE=1 C:/Users/weo/Desktop/api/examdata/.venv/Scripts/python.exe b07_build_report.py; echo "EXIT=$?"` | `C:/Users/weo/Desktop/api/integration-staging/runtime/b07-rehearsal-2026-10-07` | 0 |

Run notes:

- **build candidate, first pass**: first pass; its candidate tree digest was 7a1985b7… but the pass was superseded by the rebuild that followed the published.py over-redaction fix; the recorded build_run.json is the second pass
- **smoke import, first pass**: first pass; it exposed the over-redacted public projection of the new operations view (the internal schema tag and a slash-bearing denominator label were rendered as redacted path strings), which was fixed with two edits inside tools/published.py and rebuilt
- **build candidate, second pass (the recorded build)**: recorded pass after the fix; candidate tree digest 5df25984…; evidence/build_run.json is this pass (all_ok=True, checks 21/21, digest reproducible after the manifest write, stderr empty)
- **smoke import, second pass (the recorded smoke)**: clean pass; the public projection no longer carries the internal schema tag and denominator labels use '#' separators; evidence/smoke_import.json is this pass (structural_ok=True, stderr empty)
- **route probe, first capture attempt (kept)**: failed exactly one check, J_section_completed, on a probe-internal attribute name ('JobView' object has no attribute 'public_id'); 145 checks were recorded (85 positive / 26 negative) before the J section aborted; this failed capture is kept at evidence/probe_run1.json and was NOT overwritten by the clean rerun
- **route probe, clean rerun (the archived capture)**: 174/174 checks clean with 30 negatives / 111 positives; a one-line fix inside the probe and a scratch preflight in evidence/tmp (removed at cleanup) preceded this rerun; this rerun is evidence/probe_run2.json; stderr holds only the Starlette deprecation warning
- **validate (probe from 3 cwds)**: the validator itself writes the frozen evidence under docs/integration/execution/evidence/B07/b07-rehearsal-2026-10-07/(B07_LAYOUT_VALIDATION.json, b07_validation_run.txt, probe_cwd1..3.json); all three runs 174/174 from the workspace root, an arbitrary directory name and a path with spaces and non-ASCII characters
- **isolated staged suite**: 887 passed, 1 warning in 43.72s; the transcript's last line records suite_exit=0; ran exactly once, after every product-code change had stabilised
- **merge + rollback proposals**: clean on the first run (no failed-run history in this packet); all 11 digest checks true; 15 entries, 14 requiring the human release, 1 staging-only
- **review report + progress ledger**: writes B07_PROGRESS_LEDGER.json, B07_PROGRESS_LEDGER.md and B07_REHEARSAL_REPORT.md into docs/integration/execution/; frozen evidence is read, never rewritten

## 4. Test results

- **Route probe**: 174 checks × 3 working directories = 522 check executions, 0 failed.
- **Isolated staged suite**: 887 passed, 1 warning in 43.72s (exit 0). Unchanged from the R04/B02/B03/B04/B05/B06 baseline of 887; B07 adds no test file to that suite.
- **Build checks**: 21/21.
- **Cross-stack rehearsal (part of the probe)**: 18 driver checks, 0 failed; the candidate frontend's Node test files passed 41/41.
- **Smoke import (operations view, in-process)**: 7 checkpoint observations (5 current / 2 superseded), 7 coverage rows, 7 job rows, 4 published rows; `structural_ok=True`.

### Negative results (the checks that must refuse or stay unchanged)

- `N1_raw_include_serves_v2_unshaped_errors`
- `N1_raw_include_binary_row_keeps_application_json`
- `N2_unscoped_install_changes_exactly_three_probes`
- `N2_unscoped_legacy_500_becomes_json_envelope`
- `N2_unscoped_legacy_422_becomes_400_envelope`
- `N2_unscoped_legacy_404_becomes_envelope`
- `N2_post_build_handler_install_is_invisible`
- `N3_mount_documents_no_v2_paths`
- `N3_mount_direct_info_is_wrong_route_envelope`
- `N3_mount_requires_doubled_prefix`
- `N4_double_attach_refused`
- `N4_double_attach_leaves_host_unchanged`
- `N5_late_attach_refused`
- `N5_late_attach_no_v2_paths`
- `N6_non_fastapi_host_refused`
- `N7_refuses_missing_evidence_marker`
- `N7_refuses_missing_status_marker`
- `N7_refuses_non_synthetic_source_evidence`
- `N7_refuses_live_access_material`
- `N7_refuses_unavailable_season_without_reason`
- `N7_refuses_date_without_raw_text`
- `N7_refuses_unknown_boundary_with_parsed_value`
- `N7_refuses_undeclared_missing_boundary`
- `N7_refuses_non_list_family_rows`
- `N7_dataset_refuses_unvalidated_source`
- `J_operations_disabled_when_unconfigured`
- `J_route_leaves_carry_no_raw_paths_or_secrets`
- `J_disabled_app_has_no_operations_key`
- `J_missing_root_is_reported_not_raised`
- `J_operations_modules_expose_no_write_surface`

### Positive controls

- `S_fixture_source_valid_counts`
- `S_default_dataset_uses_fixture_source`
- `S_rows_copy_isolated`
- `S_deferred_fixtures_through_seam`
- `S_route_rows_carry_markers`
- `S_cie_event_null_fields_preserved`
- `S_seasons_unavailable_with_reason`
- `S_windows_unknown_boundaries_declared`
- `S_private_source_served_by_routes`
- `S_fixture_path_still_serves_after_injection`
- `B_ordering_get_first_match_own_route`
- `B_ordering_head_first_match_own_route`
- `B_no_param_static_shadowing`
- `B_no_pattern_intersections`
- `C_route_table_prefix_kept`
- `C_route_table_single_wrapper_appended`
- `C_legacy_inventory_byte_identical`
- `C_legacy_extras_byte_identical`
- `C_legacy_boom_bytes_pinned`
- `C_binary_fixture_ids_pinned`
- `C_binary_content_200`
- `C_binary_range_206`
- `C_binary_conditional_304`
- `C_binary_head_200`
- `C_material_content_200_pinned`
- `C_v2_typed_400_invalid_request`
- `C_v2_stack_boom_500_internal_error`
- `C_v2_jobs_404_not_found`
- `C_v2_unknown_404_route_not_found`
- `C_v2_post_info_405_method_not_allowed`
- `C_v2_info_200_envelope`
- `C_v2_controls_differ_from_baseline`
- `D_path_delta_is_exactly_registry`
- `D_pre_paths_operations_unchanged`
- `D_operation_ids_unique`
- `D_v2_operation_ids_match_standalone`
- `D_binary_rows_documented`
- `D_nonbinary_200_schema_is_envelope`
- `D_openapi_route_serves_same_document`
- `D_second_instance_document_digest_equal`
- `D_stability_digests_match_b06_ledger`
- `D_stability_ids_and_delta_match_b06_ledger`
- `F_frontend_tree_is_seventeen_files`
- `F_staged_frontend_bytes_match_workspace_source`
- `F_new_frontend_files_match_run_sources`
- `F_provenance_records_match_candidate_and_source`
- `F_node_available`
- `F_node_check_parses_new_frontend_js`
- `F_node_test_suite_41_passed`
- `G_rows_six_sorted_with_discovery_blocks`
- `G_empty_query_returns_all_six`
- `G_system_filter_rows`
- `G_unknown_filter_422_unsupported_filter`
- `G_query_matrix_all_21_cases`
- `G_boundary_mar_leaves_mark_scheme_alone`
- `G_boundary_202_is_not_2024`
- `G_boundary_paper_suffix_01_matches`
- `G_detail_routes_carry_discovery_key`
- `H_upstream_uvicorn_started`
- `H_frontend_server_ephemeral_banner`
- `H_frontend_serves_index`
- `H_node_static_index_bytes_equal`
- `H_node_static_root_alias_serves_index`
- `H_node_static_missing_404`
- `H_node_method_405_allow_get`
- `H_node_catalog_json_bytes_equal`
- `H_node_syllabi_json_bytes_equal`
- `H_node_client_cie_single_season`
- `H_node_client_cie_fanout`
- `H_node_client_edexcel_single_june`
- `H_node_client_edexcel_fanout_cross_season_duplicates`
- `H_node_bridge_cie_single_rows`
- `H_node_bridge_cie_fanout_empty_seasons_ok`
- `H_node_bridge_edexcel_fanout_deduped`
- `H_node_bridge_guard_400`
- `H_node_content_bytes_via_proxy`
- `H_node_v2_info_via_proxy`
- `H_node_gateway_denied_404`
- `H_node_gateway_allowed_forwarded_to_upstream`
- `H_cross_stack_all_18_pass`
- `H_content_triple_proxy_direct_disk`
- `H_rehearsal_processes_stopped`
- `N1_legacy_probes_unchanged`
- `J_operations_enabled_from_environment`
- `J_jobs_by_id_serves_current_only`
- `J_stages_reflect_the_checkpoints`
- `J_superseded_only_in_superseded_lists`
- `J_no_job_conflicts`
- `J_view_scanned_once_and_clean`
- `J_route_9191_stays_stopped_and_flags_resume`
- `J_route_9191_error_is_fixture_redacted`
- `J_route_9191_has_no_superseded_or_conflicts`
- `J_operations_warning_appended_on_route`
- `J_route_9191_envelope_completeness`
- `J_route_leaves_expose_the_placeholders`
- `J_route_8888_current_running_old_stopped_only_superseded`
- `J_deferred_job_fixture_still_served`
- `J_coverage_route_items_gaps_identical_with_and_without_operations`
- `J_route_coverage_warning_appended`
- `J_route_root_block_disclosed`
- `J_checkpoints_seven_rows_five_current_two_superseded`
- `J_checkpoint_payload_hashes_recompute_7_of_7`
- `J_checkpoint_payload_hashes_pin_three`
- `J_unsupported_checkpoint_recorded_unknown`
- `J_checkpoints_conflicts_empty`
- `J_jobs_briefs_show_stopped_and_superseded_states`
- `J_published_four_rows_and_schema_absent`
- `J_published_rows_pass_the_coverage_contract`
- `J_published_statuses_pinned`
- `J_computed_at_is_utc_second_precision`
- `J_candidate_tree_unchanged_by_the_view`

## 5. What the checks cover

- **Section A — import and root configuration (15 checks)**: root env is the candidate, no staging-root override, no PYTHONPATH, candidate `src/` first on `sys.path`, every module origin inside the candidate, no original-tree module loaded, no product import of testing guards, 28 schema files parse, quality dimensions and identity kinds match the code, synthetic Node discovery (`fake_cli`) resolves inside the candidate, legacy bridge entry imports from the candidate; and the three new checks pin the operations root to the candidate's own fixture directory, the API key to a fixture-labelled synthetic control value, and the operations-root environment variable name (`EXAMDATA_OPERATIONS_ROOT`).
- **Section B — worksheet, registry and ordering (14 checks)**: the A12 worksheet holds 71 rows (70 GET + 1 POST `/sample`); the v2 registry has 34 implemented / 0 deferred specs of which 5 are binary; runtime, spec and advertised pairs agree; HEAD pairs are binary-only; GET 34/34 and HEAD 5/5 first-match their own route; no static route is shadowed; and no two distinct path patterns intersect (561 pairs).
- **Section C — host mechanics and behaviour (19 checks)**: host shape pre-attach, the legacy prefix is kept, exactly one wrapper is appended; all 71 legacy rows and 7 extra probes stay byte-identical; the legacy stack-boom body stays pinned; binary fixture ids and 200 / 206 / 304 / HEAD responses pinned; the synthetic material content response pinned; and the six v2 controls serve typed envelopes that all differ from their pre-attach baselines.
- **Section D — combined OpenAPI and B06-ledger stability (10 checks)**: the path delta is exactly the registry; the pre-attach paths' operations are unchanged; operation ids are unique; the v2 operation ids match the standalone app; binary rows are documented with their media types; non-binary 200 responses serve the envelope schema; `/openapi.json` serves the same document as the direct call; a second instance yields the same digest; and the two renamed stability checks confirm the combined OpenAPI, standalone v2, legacy-operations and composed-route-table digests plus the operation ids and the 34-path delta still match the frozen B06 progress ledger (`b07_vs_b06_ledger_consistent` = `True`).
- **Section E — stability (7 checks)**: candidate bytes unchanged by the probe; fixture and contract digests unchanged; the manifest recomputes to 221 files and the same tree digest; counts disclosed (221 digest / 222 on-disk); the B04 compose hook stays frozen; no embedded `data:` payloads; scratch marker written inside the run's evidence/tmp.
- **Section S — the active-owner seam (10 checks)**: the synthetic fixture source validates with 2 rows per family; the default dataset really uses the fixture source; row access returns isolated copies; deferred families flow through the seam unchanged; route rows carry the synthetic markers; CIE event null fields are preserved; unavailable seasons carry their reason; unknown window boundaries stay declared with null parsed values; a private injected source is served by the routes; and the default fixture path still serves after that injection.
- **Section F — the staged frontend tree (7 checks)**: the candidate frontend holds exactly seventeen files; the fifteen staged files are byte-equal to `integration-staging/frontend/`; the two new files are byte-equal to the run's tooling sources; the provenance records match the candidate and the source; Node is available; the new frontend JS parses; and the candidate frontend's Node test files pass 41/41.
- **Section G — frontend-shaped discovery semantics (9 checks)**: the assets route returns six sorted rows with their discovery blocks; an empty query returns all six; the system filter narrows the rows; an unknown filter yields a typed 422 `unsupported_filter`; the 21-case query matrix all answers as specified; the boundary rules hold (Mar leaves mark_scheme alone; `202` is not `2024`; paper suffix `01` matches); and the detail routes carry the discovery key.
- **Section H — cross-stack rehearsal on ephemeral loopback ports (24 checks)**: an ephemeral uvicorn upstream and the staged frontend server start on 127.0.0.1; the frontend serves index and its static bytes (index/catalog/syllabi) byte-equal, root alias, missing 404, method 405; the Node client checks single-season and fanout discovery for CIE and Edexcel (cross-season duplicates included); the Node bridge checks rows, empty-seasons fanout, dedupe and the guard 400; content is byte-equal across proxy, direct API and disk fixture (content triple); v2 info via proxy; the gateway denies and forwards as specified; the cross-stack driver's 18 checks all pass; and both rehearsal processes are stopped again.
- **Section J — the operations view over the synthetic fixture root (33 checks; 28 positive + 5 negative controls)**: the view is enabled from the environment only (root = the candidate's own synthetic fixture directory, API key = a fixture-labelled synthetic control); jobs are served current-only by id; stage rows reflect the checkpoints; superseded checkpoints appear only in superseded lists; no job conflicts are reported; the view scans the root once and cleanly; route 9191 stays stopped and flags resume; its error is fixture-redacted (no raw paths or secrets); it carries no superseded rows or conflicts; the operations warning is appended on the route; the 9191 envelope reports completeness; route leaves expose the placeholders; route 8888 serves the current running / old stopped rows only in superseded lists; a deferred job fixture is still served; the coverage route's items and gaps are identical with and without the operations view; the coverage warning is appended; the root block is disclosed without raw paths; seven checkpoint rows resolve to five current and two superseded; the checkpoint payload hashes recompute 7/7 with three pinned; the unsupported checkpoint is recorded as unknown; checkpoint conflicts stay empty; job briefs show stopped and superseded states; the published route serves four rows and the internal schema tag is absent; the published rows pass the coverage contract; statuses are pinned; `computed_at` is UTC second-precision; and the candidate tree is unchanged by the view. The five negative controls cover the disabled/unconfigured paths: operations stay off without configuration; route leaves carry no raw paths or secrets; a disabled app has no operations key; a missing root is reported, not raised; and the operations modules expose no write surface.
- **Sections N1–N6 — route-layer negative controls (16 checks, 15 negative) and section N7 — the seam refuse-path (10 negative checks)**: identical to B06 - raw include, unscoped install, mounts, double/late attach, non-FastAPI host, and the ten seam refuse paths; the negative control list extends B06's by exactly the five J negatives.

## 6. Import status of the new candidate

The candidate's imports resolve from the candidate itself through `EXAMDATA_INTEGRATION_ROOT` only — no `PYTHONPATH`, no staging-root override — and the same result holds from all three working directories: the workspace root, an arbitrary directory name under the run's evidence/tmp, and a path containing spaces and non-ASCII characters (`cwd with spaces ünïcode`). Module origins, schema access, synthetic Node discovery and the runtime/legacy entry points were re-verified from those directories, and discovery, routing stability, the seam, the operations view, the staged-frontend tree, the discovery projection and the cross-stack summary are identical across all three (`discovery_identical_across_cwds`, `stability_identical_across_cwds`, `seam_identical_across_cwds`, `operations_identical_across_cwds` = `True`, `frontend_identical_across_cwds` = `True`, `cross_stack_identical_across_cwds` = `True`). Real Node/source validation against the original project remains `not_run`.

| Check | Result | Detail |
| --- | --- | --- |
| `A_env_root_is_candidate` | `True` | EXAMDATA_INTEGRATION_ROOT='C:\\Users\\weo\\Desktop\\api\\integration-staging\\runtime\\b07-rehearsal-2026-10-07\\candidates\\b07-operations-v1' candidate=C:\Users\weo\Desktop\api\integration-staging\r… |
| `A_no_staging_override` | `True` | EXAMDATA_INTEGRATION_STAGING_ROOT must not be staged |
| `A_no_pythonpath` | `True` | PYTHONPATH=None |
| `A_candidate_src_first_on_path` | `True` | sys.path[0]='C:\\Users\\weo\\Desktop\\api\\integration-staging\\runtime\\b07-rehearsal-2026-10-07\\candidates\\b07-operations-v1\\src' |
| `A_module_origins_within_candidate` | `True` | all candidate |
| `A_no_original_tree_module_loaded` | `True` | no module from the original tree |
| `A_product_no_testing_guard_imports` | `True` | no product import of testing guards |
| `A_schema_files_parse` | `True` | 28 schema file(s); malformed: none |
| `A_quality_dimensions_match_code` | `True` | all dimensions agree |
| `A_identity_kinds_match_code` | `True` | 14 kind(s); unrecognised: none |
| `A_node_discovery_candidate_root` | `True` | ids=['fake_cli'] problems=[] entry=C:\Users\weo\Desktop\api\integration-staging\runtime\b07-rehearsal-2026-10-07\candidates\b07-operations-v1\components\fake-node-cli\fake-cli.mjs |
| `A_legacy_bridge_entry_imports_within_candidate` | `True` | C:\Users\weo\Desktop\api\integration-staging\runtime\b07-rehearsal-2026-10-07\candidates\b07-operations-v1\src\examdata\integration\legacy\bridge.py |
| `A_operations_root_is_candidate_fixture` | `True` | C:\Users\weo\Desktop\api\integration-staging\runtime\b07-rehearsal-2026-10-07\candidates\b07-operations-v1\fixtures\synthetic\operations\operations-root |
| `A_api_key_is_labelled_synthetic_control` | `True` | fixture-labelled synthetic control value |
| `A_operations_root_env_name_pinned` | `True` | EXAMDATA_OPERATIONS_ROOT |

## 7. Proposals

- Merge proposal: `docs/integration/execution/B07_MERGE_PROPOSAL.json` — 15 entries, 14 requiring the human release, 1 staging-only; 12 new files vs the parent and 2 rewritten staged modules. The release-required entries are the two rewritten modules (BP-0002 app.py, BP-0003 dataset.py; add_file semantics at the proposed targets because the whole integration package is new relative to the original project - superseding the unapplied B06 BP-0002/BP-0003) and the twelve new files: BP-0004 `operations/jobs.py`, BP-0005 `operations/published.py`, and the ten fixture files BP-0006–BP-0015 under `examdata/tests/integration/fixtures/synthetic/operations/operations-root/`. The single staging-only entry is BP-0001, the candidate container (kept in integration-staging/; no original-project action proposed).
- Rollback proposal: `docs/integration/execution/B07_ROLLBACK_PROPOSAL.json` — 15 entries; at the original level 14 are reversible by deleting the added target file (guarded by the recorded sha256), 0 by restoring the recorded base bytes, 0 is a reconciliation case and 1 has no original action at all.

Both are marked `proposal_only_nothing_merged_not_deployed`. Nothing has been applied to the original project. The merge proposal's `action_level_gate_model` records the gate discipline this rehearsal followed: a gate is required only for the action that performs that effect, private preparation requires no gate, and no original write may proceed without the applicable human release.

## 8. Live ledger and gates

- `docs/integration/execution/execution-ledger.json` sha256 `6d4449d3997b437fd3ea3a1fe7925fc78a7c0adbe0a5d3b793d6a8063101b4ba`
- Expected frozen value: `6d4449d3997b437fd3ea3a1fe7925fc78a7c0adbe0a5d3b793d6a8063101b4ba`
- Byte-unchanged: `True`
- Gates open: [] (all closed: `True`)

The live execution ledger is byte-identical to its frozen pre-rehearsal value and was not written by this rehearsal; the seven gates remain closed.

## 9. Not run

- real merge into the original project — gate original_paths_released is closed; the plan entry remains a proposal (deferred_pending_release) and the original tree was never read or written
- real active-owner integration (materials, syllabuses and timetables served by the original owner modules) — no owner release exists for the active-owner families; the seam serves only clearly labelled synthetic fixtures and the real integration stays deferred_active_owner
- real baseline verification against the actual legacy application — gate original_paths_released is closed; the legacy side was simulated from the frozen A12 route-compatibility worksheet, not from the original app
- real Node component execution (fake-cli.mjs run via the Node runtime) — gate original_paths_released is closed; only synthetic discovery and importability of the component are rehearsed
- real Node/source validation against the original project — gate original_paths_released is closed; the original tree was never read
- real database schema / data migration — gate real_data_write_authorized is closed; no database is staged or touched
- live service / upstream provider calls — gate upstream_requests_authorized is closed; only synthetic fixture providers ran
- cutover of the existing service — gate existing_service_cutover_authorized is closed
- deployment to any target — gate remote_deployment_authorized is closed; this candidate is private-only
- cleanup of the original project — gate original_cleanup_authorized is closed
- credential usage of any kind — no credential gate exists in the seven-gate model and none is needed: no real credential is used, read, fabricated or staged; the only credential-shaped value anywhere is the fixture-labelled synthetic control string the operations fixtures carry, and the routing controls are synthetic request parameters with no secret values
- real frontend cutover (the staged page and server on the live service) — gate existing_service_cutover_authorized is closed; the staged frontend ran only on an ephemeral 127.0.0.1 port against the private read API
- real source-provider fetching from the frontend process — gate upstream_requests_authorized is closed; the candidate frontend carries no source-discovery logic and only proxies the private read API
- real job-service interaction (resume / cancel / enqueue against a live queue) — no job-service release exists and none is needed: the operations view is read-only by construction, and a stopped job is only observed as stopped; it is never resumed, restarted or written back
- writes of any kind to an operations root (checkpoint repair, resume flags, published manifests) — gate original_paths_released is closed; the only operations root touched was the candidate's own synthetic fixture directory, read once and never modified

## 10. Not claimed / remaining blockers

Not claimed: `merged_pass`, `deployment`, `full B00/B01 completion`.

- original-project merge of the B07 entries — gate original_paths_released is closed; an explicit human release with an explicit scope is required. The merge proposal has 14 release-required entries of 15: the two rewritten modules (app.py, dataset.py; add_file semantics because the whole integration package is new relative to the original project) and the twelve new files (operations/jobs.py, operations/published.py and the ten labelled synthetic operations fixtures); the candidate tree digest must be re-verified immediately before any original write.
- release decision spans both proposals — the B06 merge proposal's 18 release-required entries and B07's 14 should be decided together or stay deferred; the B07 proposal re-verifies the cross-reference against the B06 proposal (b06_merge_crossref_matches, supersession_chains_match) rather than re-proposing B06's entries
- real Node component execution (ielts-api / toefl-api) — gate original_paths_released is closed; the cross-stack rehearsal ran only against the private candidate and its staged frontend, on ephemeral loopback ports
- real database schema / data-root migration — gate real_data_write_authorized is closed; schema and data roots are deliberately unchanged by B07
- real operations enablement and source fetching/recovery — gates existing_service_cutover_authorized, upstream_requests_authorized and cie_resume_authorized are closed; the only operations root is the labelled synthetic fixture, and the stopped cie 9191 batch stays stopped - nothing is resumed, fetched or written back
- deployment to any target — gate remote_deployment_authorized is closed; the candidate is private-only
