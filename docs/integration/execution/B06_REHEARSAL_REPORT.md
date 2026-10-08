# B06 rehearsal review report (private preparation only)

Generated: 2026-10-07T05:13:50+08:00  
Packet: **B06** — frontend migration (staged frontend, discovery semantics, v2 switch)  
Status: `b06_private_rehearsal_complete_pending_human_release`  
Probe verdict: `b06_rehearsal_valid_private_only`  
Probe findings: 0

Nothing in this report has been merged or deployed. The original project was not read, imported or written by any B06 step. All seven gates are closed.

## 1. What B06 rehearsed

B06 owns the frontend migration: the staged search frontend, the frontend-shaped discovery semantics of the read API and the v2 switch. What can be done without the human release is a rehearsal: carry the B05 candidate byte-for-byte, rewrite three modules — `app.py` (discovery projection and resources wiring), `dataset.py` (frontend-shaped query semantics) and `view.py` — and bring the frontend across: fifteen staged files copied byte-for-byte from `integration-staging/frontend/` (thirteen carried from the B01/A14 records MM-0229..MM-0241 plus the two staging PROVENANCE records B01 excluded from the merge), the rewritten `frontend/server.mjs` (the B01 planned original edit, packet B06) and the new `frontend/tests/server.test.mjs`. The acceptance properties that do not need the original tree are then proven by the route probe: the staged frontend tree, the discovery semantics (the G section: six sorted rows with discovery blocks, the 21-case query matrix, boundary rules and detail routes) and a real but private cross-stack rehearsal on ephemeral loopback ports (the H section: the staged frontend server in front of the private read API, driven by the candidate frontend's Node client and bridge), while the B05 ledger digests stay byte-stable.

## 2. Candidate and lineage

- Candidate: `integration-staging/runtime/b06-rehearsal-2026-10-07/candidates/b06-frontend-v1`
- Parent: `integration-staging/runtime/b05-rehearsal-2026-10-07/candidates/b05-adapters-v1` (the B05 adapters candidate)
- Parent tree: 190 files, sha256 `d38a124e8595b61d21e41f778ba164471ffbfebb099813b812949d8213d02955`
- Candidate tree: 208 files (191 copied from the parent, of which 188 stay verbatim and 3 were rewritten, + 17 new frontend files), sha256 `ffe774db608ff9d86246458a38265f9baa760b40880e48197e84d887f85d53f4`
- Candidate digest reproducible from the tree on disk: `True` (re-checked independently by the validator, not just self-reported by the builder)
- Parent manifest sha256 unchanged at build time: `c4341576bf1a6b5d56a01098f46a77eb4081db30225c7f5cc4176be2abe9e008`
- Count explanation: B05's digest covered 190 files and its on-disk non-cache count was 191 (190 + B05 manifest). B06 copies all 191, rewrites 3 and adds 17, so the candidate digest covers 208 = 188 verbatim + 3 rewritten + 17 new, and on-disk is 209 = 208 + the B06 manifest; the candidate carries no __pycache__ files (PYTHONDONTWRITEBYTECODE=1 throughout).

The rewritten `app.py` supersedes B05 BP-0004, the rewritten `dataset.py` supersedes B05 BP-0003 / R0104 RP-0005 and the rewritten `view.py` supersedes A14 MM-0022; all three supersession chains are re-verified in the merge proposal's `digest_checks` (`supersession_chains_match`), the frontend entries are re-verified against the B01 records (`frontend_matches_b01_records` and the `frontend_check_detail`), and the parent tree digest was re-computed after the copy and again at proposal time and is unchanged (`parent_tree_reverified`).

## 3. Commands, working directory and exit codes

| Step | Command | cwd | Exit |
| --- | --- | --- | --- |
| build candidate | `PYTHONIOENCODING=utf-8 PYTHONDONTWRITEBYTECODE=1 C:/Users/weo/Desktop/api/examdata/.venv/Scripts/python.exe b06_build_candidate.py > evidence/build_run.json 2> evidence/build_run.err.txt` | `C:/Users/weo/Desktop/api/integration-staging/runtime/b06-rehearsal-2026-10-07` | 0 |
| route probe, first capture attempt | `CAND="$PWD/candidates/b06-frontend-v1" B06_CANDIDATE_ROOT="$CAND" B06_WORKSPACE_ROOT="C:/Users/weo/Desktop/api" B06_TMP_DIR="$PWD/evidence/tmp" EXAMDATA_INTEGRATION_ROOT="$CAND" PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8 "C:/Users/weo/Desktop/api/examdata/.venv/Scripts/python.exe" b06_route_probe.py 1> evidence/probe_run1.json 2> evidence/probe_run1.err; echo "probe_exit=$?"` | `C:/Users/weo/Desktop/api/integration-staging/runtime/b06-rehearsal-2026-10-07` | 1 |
| route probe, clean rerun (the archived capture) | `PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8 "C:/Users/weo/Desktop/api/examdata/.venv/Scripts/python.exe" -m py_compile b06_route_probe.py && rm -rf __pycache__ && CAND="$PWD/candidates/b06-frontend-v1" B06_CANDIDATE_ROOT="$CAND" B06_WORKSPACE_ROOT="C:/Users/weo/Desktop/api" B06_TMP_DIR="$PWD/evidence/tmp" EXAMDATA_INTEGRATION_ROOT="$CAND" PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8 "C:/Users/weo/Desktop/api/examdata/.venv/Scripts/python.exe" b06_route_probe.py 1> evidence/probe_run1.json 2> evidence/probe_run1.err; echo "probe_exit=$?"` | `C:/Users/weo/Desktop/api/integration-staging/runtime/b06-rehearsal-2026-10-07` | 0 |
| validate (probe from 3 cwds) | `PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8 "C:/Users/weo/Desktop/api/examdata/.venv/Scripts/python.exe" -m py_compile b06_validate.py && rm -rf __pycache__ && echo "compile_ok" && PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8 "C:/Users/weo/Desktop/api/examdata/.venv/Scripts/python.exe" b06_validate.py; echo "validate_exit=$?"` | `C:/Users/weo/Desktop/api/integration-staging/runtime/b06-rehearsal-2026-10-07` | 0 |
| isolated staged suite | `bash integration-staging/tools/run_staged_tests.sh -q > integration-staging/runtime/b06-rehearsal-2026-10-07/evidence/isolated_staged_suite.txt 2>&1; echo "suite_exit=$?" >> integration-staging/runtime/b06-rehearsal-2026-10-07/evidence/isolated_staged_suite.txt` | `C:/Users/weo/Desktop/api` | 0 |
| merge + rollback proposals, first run | `PYTHONIOENCODING=utf-8 PYTHONDONTWRITEBYTECODE=1 "C:/Users/weo/Desktop/api/examdata/.venv/Scripts/python.exe" b06_build_proposals.py; echo "EXIT=$?"` | `C:/Users/weo/Desktop/api/integration-staging/runtime/b06-rehearsal-2026-10-07` | 1 |
| merge + rollback proposals, rerun after the fix | `PYTHONIOENCODING=utf-8 PYTHONDONTWRITEBYTECODE=1 "C:/Users/weo/Desktop/api/examdata/.venv/Scripts/python.exe" b06_build_proposals.py; echo "EXIT=$?"` | `C:/Users/weo/Desktop/api/integration-staging/runtime/b06-rehearsal-2026-10-07` | 0 |
| review report + progress ledger | `PYTHONIOENCODING=utf-8 PYTHONDONTWRITEBYTECODE=1 "C:/Users/weo/Desktop/api/examdata/.venv/Scripts/python.exe" b06_build_report.py` | `C:/Users/weo/Desktop/api/integration-staging/runtime/b06-rehearsal-2026-10-07` | 0 |

Run notes:

- **build candidate**: build record all_ok=True with 21/21 checks; evidence/build_run.err.txt is 0 bytes
- **route probe, first capture attempt**: failed exactly two checks in the new F section (F_frontend_tree_is_seventeen_files on a key-space mismatch, and its cascade F_section_completed with a doubled frontend/frontend path); fixed inside the probe and rerun; the failed capture at evidence/probe_run1.json was overwritten by the clean rerun and is not archived separately - details in process_observations
- **route probe, clean rerun (the archived capture)**: 138/138 checks clean; this rerun is evidence/probe_run1.json; stderr holds only the Starlette deprecation warning
- **validate (probe from 3 cwds)**: the validator itself writes the frozen evidence under docs/integration/execution/evidence/B06/b06-rehearsal-2026-10-07/ (B06_LAYOUT_VALIDATION.json, b06_validation_run.txt, probe_cwd1..3.json)
- **isolated staged suite**: 887 passed; the transcript's last line records suite_exit=0
- **merge + rollback proposals, first run**: failed exactly one digest check, frontend_matches_b01_records: the expected B01 frontend id list was generated without zero padding (MM-229... instead of MM-0229...); fixed one line and rerun; details in process_observations
- **merge + rollback proposals, rerun after the fix**: all 11 digest checks true; both proposal JSONs on disk are the post-fix regenerated versions

## 4. Test results

- **Route probe**: 138 checks × 3 working directories = 414 check executions, 0 failed.
- **Isolated staged suite**: 887 passed, 1 warning in 40.93s (exit 0). Unchanged from the R04/B02/B03/B04/B05 baseline of 887; B06 adds no test file to that suite.
- **Build checks**: 21/21.
- **Cross-stack rehearsal (part of the probe)**: 18 driver checks, 0 failed; the candidate frontend's Node test files passed 41/41.

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
- `D_stability_digests_match_b05_ledger`
- `D_stability_ids_and_delta_match_b05_ledger`
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

## 5. What the checks cover

- **Section A — import and root configuration (12 checks)**: root env is the candidate, no staging-root override, no PYTHONPATH, candidate `src/` first on `sys.path`, every module origin inside the candidate, no original-tree module loaded, no product import of testing guards, 28 schema files parse, quality dimensions and identity kinds match the code, synthetic Node discovery (`fake_cli`) resolves inside the candidate, legacy bridge entry imports from the candidate.
- **Section B — worksheet, registry and ordering (14 checks)**: the A12 worksheet holds 71 rows (70 GET + 1 POST `/sample`); the v2 registry has 34 implemented / 0 deferred specs of which 5 are binary; runtime, spec and advertised pairs agree; HEAD pairs are binary-only; GET 34/34 and HEAD 5/5 first-match their own route; no static route is shadowed; and no two distinct path patterns intersect (561 pairs).
- **Section C — host mechanics and behaviour (19 checks)**: host shape pre-attach, the legacy prefix is kept, exactly one wrapper is appended; all 71 legacy rows and 7 extra probes stay byte-identical; the legacy stack-boom body stays pinned; binary fixture ids and 200 / 206 / 304 / HEAD responses pinned; the synthetic material content response pinned; and the six v2 controls serve typed envelopes that all differ from their pre-attach baselines.
- **Section D — combined OpenAPI and B05-ledger stability (10 checks)**: the path delta is exactly the registry; the pre-attach paths' operations are unchanged; operation ids are unique; the v2 operation ids match the standalone app; binary rows are documented with their media types; non-binary 200 responses serve the envelope schema; `/openapi.json` serves the same document as the direct call; a second instance yields the same digest; and the two renamed stability checks confirm the combined OpenAPI, standalone v2, legacy-operations and composed-route-table digests plus the operation ids and the 34-path delta still match the frozen B05 progress ledger (`b06_vs_b05_ledger_consistent` = `True`).
- **Section E — stability (7 checks)**: candidate bytes unchanged by the probe; fixture and contract digests unchanged; the manifest recomputes to 208 files and the same tree digest; counts disclosed (208 digest / 209 on-disk); the B04 compose hook stays frozen; no embedded `data:` payloads; scratch marker written inside the run's evidence/tmp.
- **Section S — the active-owner seam (10 checks)**: the synthetic fixture source validates with 2 rows per family; the default dataset really uses the fixture source; row access returns isolated copies; deferred families flow through the seam unchanged; route rows carry the synthetic markers; CIE event null fields are preserved; unavailable seasons carry their reason; unknown window boundaries stay declared with null parsed values; a private injected source is served by the routes; and the default fixture path still serves after that injection.
- **Section F — the staged frontend tree (7 checks)**: the candidate frontend holds exactly seventeen files; the fifteen staged files are byte-equal to `integration-staging/frontend/`; the two new files are byte-equal to the run's tooling sources; the provenance records match the candidate and the source; Node is available; the new frontend JS parses; and the candidate frontend's Node test files pass 41/41.
- **Section G — frontend-shaped discovery semantics (9 checks)**: the assets route returns six sorted rows with their discovery blocks; an empty query returns all six; the system filter narrows the rows; an unknown filter yields a typed 422 `unsupported_filter`; the 21-case query matrix all answers as specified; the boundary rules hold (Mar leaves mark_scheme alone; `202` is not `2024`; paper suffix `01` matches); and the detail routes carry the discovery key.
- **Section H — cross-stack rehearsal on ephemeral loopback ports (24 checks)**: an ephemeral uvicorn upstream and the staged frontend server start on 127.0.0.1; the frontend serves index and its static bytes (index/catalog/syllabi) byte-equal, root alias, missing 404, method 405; the Node client checks single-season and fanout discovery for CIE and Edexcel (cross-season duplicates included); the Node bridge checks rows, empty-seasons fanout, dedupe and the guard 400; content is byte-equal across proxy, direct API and disk fixture (content triple); v2 info via proxy; the gateway denies and forwards as specified; the cross-stack driver's 18 checks all pass; and both rehearsal processes are stopped again.
- **Sections N1–N6 — route-layer negative controls (16 checks, 15 negative) and section N7 — the seam refuse-path (10 negative checks)**: identical to B05 - raw include, unscoped install, mounts, double/late attach, non-FastAPI host, and the ten seam refuse paths; the negative control list is unchanged from B05.

## 6. Import status of the new candidate

The candidate's imports resolve from the candidate itself through `EXAMDATA_INTEGRATION_ROOT` only — no `PYTHONPATH`, no staging-root override — and the same result holds from all three working directories: the workspace root, an arbitrary directory name under the run's evidence/tmp, and a path containing spaces and non-ASCII characters (`cwd with spaces ünïcode`). Module origins, schema access, synthetic Node discovery and the runtime/legacy entry points were re-verified from those directories, and discovery, routing stability, the seam, the staged-frontend tree, the discovery projection and the cross-stack summary are identical across all three (`discovery_identical_across_cwds`, `stability_identical_across_cwds`, `seam_identical_across_cwds`, `frontend_identical_across_cwds` = `True`, `cross_stack_identical_across_cwds` = `True`). Real Node/source validation against the original project remains `not_run`.

| Check | Result | Detail |
| --- | --- | --- |
| `A_env_root_is_candidate` | `True` | EXAMDATA_INTEGRATION_ROOT='C:\\Users\\weo\\Desktop\\api\\integration-staging\\runtime\\b06-rehearsal-2026-10-07\\candidates\\b06-frontend-v1' candidate=C:\Users\weo\Desktop\api\integration-staging\run… |
| `A_no_staging_override` | `True` | EXAMDATA_INTEGRATION_STAGING_ROOT must not be staged |
| `A_no_pythonpath` | `True` | PYTHONPATH=None |
| `A_candidate_src_first_on_path` | `True` | sys.path[0]='C:\\Users\\weo\\Desktop\\api\\integration-staging\\runtime\\b06-rehearsal-2026-10-07\\candidates\\b06-frontend-v1\\src' |
| `A_module_origins_within_candidate` | `True` | all candidate |
| `A_no_original_tree_module_loaded` | `True` | no module from the original tree |
| `A_product_no_testing_guard_imports` | `True` | no product import of testing guards |
| `A_schema_files_parse` | `True` | 28 schema file(s); malformed: none |
| `A_quality_dimensions_match_code` | `True` | all dimensions agree |
| `A_identity_kinds_match_code` | `True` | 14 kind(s); unrecognised: none |
| `A_node_discovery_candidate_root` | `True` | ids=['fake_cli'] problems=[] entry=C:\Users\weo\Desktop\api\integration-staging\runtime\b06-rehearsal-2026-10-07\candidates\b06-frontend-v1\components\fake-node-cli\fake-cli.mjs |
| `A_legacy_bridge_entry_imports_within_candidate` | `True` | C:\Users\weo\Desktop\api\integration-staging\runtime\b06-rehearsal-2026-10-07\candidates\b06-frontend-v1\src\examdata\integration\legacy\bridge.py |

## 7. Proposals

- Merge proposal: `docs/integration/execution/B06_MERGE_PROPOSAL.json` — 21 entries, 18 requiring the human release, 3 staging-only; 17 new files vs the parent and 3 rewritten staged modules. The release-required entries are the three rewritten modules (add_file semantics; app.py supersedes B05 BP-0004, dataset.py supersedes B05 BP-0003 / R0104 RP-0005, view.py supersedes A14 MM-0022) and the fifteen frontend entries (MM-0229..MM-0241 plus frontend/server.mjs and frontend/tests/server.test.mjs; the two PROVENANCE records stay staging-only and are never installed).
- Rollback proposal: `docs/integration/execution/B06_ROLLBACK_PROPOSAL.json` — 21 entries; at the original level 11 are reversible by deleting the added target file (guarded by the recorded sha256), 6 by restoring the recorded base bytes, 1 is a reconciliation case and 3 has no original action at all.

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
- credential usage of any kind — no credential gate exists in the seven-gate model and none is needed: no credential is used, read, fabricated or staged; the routing controls are synthetic request parameters with no secret values
- real frontend cutover (the staged page and server on the live service) — gate existing_service_cutover_authorized is closed; the staged frontend ran only on an ephemeral 127.0.0.1 port against the private read API
- real source-provider fetching from the frontend process — gate upstream_requests_authorized is closed; the candidate frontend carries no source-discovery logic and only proxies the private read API

## 10. Not claimed / remaining blockers

Not claimed: `merged_pass`, `deployment`, `full B00/B01 completion`.

- original-project merge of the B06 entries — gate original_paths_released is closed; an explicit human release with an explicit scope is required. The merge proposal has 18 release-required entries of 21: the three rewritten modules (app.py, dataset.py, view.py; add_file semantics because the whole integration package is new relative to the original project) and the fifteen frontend entries (thirteen B01 records plus frontend/server.mjs and frontend/tests/server.test.mjs); the candidate tree digest must be re-verified immediately before any original write.
- frontend reconcile_modify reconciliation and the production port decision — four frontend entries are reconcile_modify (app.js, index.html, README.md, tests/search.test.mjs) and need the three-way semantic reconciliation against the released original tree that B01 deferred (three_way=false, gate was closed); the merged static server's production port strategy additionally needs an explicit human decision - the staged server defaults to an ephemeral port and refuses to bind 5188/8000 as a staging safety measure.
- real Node component execution (ielts-api / toefl-api) — gate original_paths_released is closed; the cross-stack rehearsal ran only against the private candidate and its staged frontend, on ephemeral loopback ports
- real database schema / data-root migration — gate real_data_write_authorized is closed; schema and data roots are deliberately unchanged by B06
- real frontend cutover and source-provider fetching — gates existing_service_cutover_authorized and upstream_requests_authorized are closed; the candidate frontend carries no source-discovery logic and only proxies the private read API
- deployment to any target — gate remote_deployment_authorized is closed; the candidate is private-only
