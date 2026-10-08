# B05 rehearsal review report (private preparation only)

Generated: 2026-10-07T03:05:06+08:00  
Packet: **B05** — active-owner seam for materials, syllabuses and timetables  
Status: `b05_private_rehearsal_complete_pending_human_release`  
Probe verdict: `b05_rehearsal_valid_private_only`  
Probe findings: 0

Nothing in this report has been merged or deployed. The original project was not read, imported or written by any B05 step. All seven gates are closed.

## 1. What B05 rehearsed

B05 owns the integration of the released materials, syllabus and timetable features. What can be done without the human release is a rehearsal: carry the B04 candidate byte-for-byte, add one new module — the active-owner adapter seam `src/examdata/integration/adapters/active_owner.py` — and rewrite `dataset.py` and `app.py` so the five feature families (syllabuses, materials, timetable seasons, events and windows) are read through `Dataset.features` instead of being replaced by staged fixture implementations. The seam validates every row, serves only clearly labelled synthetic fixtures, preserves null session/date fields, keeps unavailable seasons explicit and never invents clock or boundary times. The acceptance properties that do not need the original tree are then proven by the route probe: the seam refuses unlabelled or live-access data, and the B04 route surface plus the B04 ledger digests stay byte-stable under the new seam.

## 2. Candidate and lineage

- Candidate: `integration-staging/runtime/b05-rehearsal-2026-10-07/candidates/b05-adapters-v1`
- Parent: `integration-staging/runtime/b04-rehearsal-2026-10-07/candidates/b04-routes-v1` (the B04 routes candidate)
- Parent tree: 188 files, sha256 `fd806f4c6116c3f5507a7a7b13879ac5d59f627929c7a54c2767b7a1f85f9cbc`
- Candidate tree: 190 files (189 carried from the parent, of which 2 were rewritten, + 1 new), sha256 `d38a124e8595b61d21e41f778ba164471ffbfebb099813b812949d8213d02955`
- Candidate digest reproducible from the tree on disk: `True` (re-checked independently by the validator, not just self-reported by the builder)
- Parent manifest sha256 unchanged at build time: `99177c1239c60278aecc39dc3bb8c54e1c03390660bf782c5ea6ff3220dd9f57`
- Count explanation: the parent digest covers 188 files (B04's rule excluded B04's own manifest, and B04 on-disk was 189); B05 carries all 189, rewrites 2 and adds 1 new module, so the candidate digest covers 190 = 187 verbatim + 2 rewritten + 1 new, and on-disk non-cache is 191 = 190 + the B05 manifest; 49 __pycache__ bytecode files on disk are skipped by the digest rule.

The rewritten `dataset.py` supersedes the R0104-repaired staged bytes (chain: A14 MM-0017 → R0104 RP-0005 → B05) and the rewritten `app.py` supersedes the A14 MM-0015 staged bytes (chain: A14 MM-0015 → B05); both chains are re-verified in the merge proposal's `digest_checks`, and the parent tree digest was re-computed after the copy and again at proposal time and is unchanged (`parent_tree_reverified`).

## 3. Commands, working directory and exit codes

| Step | Command | cwd | Exit |
| --- | --- | --- | --- |
| build candidate | `PYTHONIOENCODING=utf-8 C:/Users/weo/Desktop/api/examdata/.venv/Scripts/python.exe b05_build_candidate.py > evidence/build_run.json 2> evidence/build_run.err.txt` | `C:/Users/weo/Desktop/api/integration-staging/runtime/b05-rehearsal-2026-10-07` | 0 |
| route probe (first and only run, clean) | `env -u PYTHONPATH -u EXAMDATA_INTEGRATION_STAGING_ROOT PYTHONIOENCODING=utf-8 PYTHONDONTWRITEBYTECODE=1 B05_CANDIDATE_ROOT=C:/Users/weo/Desktop/api/integration-staging/runtime/b05-rehearsal-2026-10-07/candidates/b05-adapters-v1 B05_WORKSPACE_ROOT=C:/Users/weo/Desktop/api B05_TMP_DIR=C:/Users/weo/Desktop/api/integration-staging/runtime/b05-rehearsal-2026-10-07/evidence/tmp EXAMDATA_INTEGRATION_ROOT=C:/Users/weo/Desktop/api/integration-staging/runtime/b05-rehearsal-2026-10-07/candidates/b05-adapters-v1 ./examdata/.venv/Scripts/python.exe integration-staging/runtime/b05-rehearsal-2026-10-07/b05_route_probe.py > integration-staging/runtime/b05-rehearsal-2026-10-07/evidence/probe_run1.json 2> integration-staging/runtime/b05-rehearsal-2026-10-07/evidence/probe_run1.err` | `C:/Users/weo/Desktop/api` | 0 |
| validate (probe from 3 cwds) | `./examdata/.venv/Scripts/python.exe integration-staging/runtime/b05-rehearsal-2026-10-07/b05_validate.py > integration-staging/runtime/b05-rehearsal-2026-10-07/evidence/validate_run1.json 2> integration-staging/runtime/b05-rehearsal-2026-10-07/evidence/validate_run1.err` | `C:/Users/weo/Desktop/api` | 0 |
| isolated staged suite | `bash integration-staging/tools/run_staged_tests.sh -q > integration-staging/runtime/b05-rehearsal-2026-10-07/evidence/isolated_staged_suite.txt 2>&1; echo "suite_exit=$?" >> integration-staging/runtime/b05-rehearsal-2026-10-07/evidence/isolated_staged_suite.txt` | `C:/Users/weo/Desktop/api` | 0 |
| merge + rollback proposals, first run | `./examdata/.venv/Scripts/python.exe integration-staging/runtime/b05-rehearsal-2026-10-07/b05_build_proposals.py` | `C:/Users/weo/Desktop/api` | 1 |
| merge + rollback proposals, rerun after the fix | `./examdata/.venv/Scripts/python.exe integration-staging/runtime/b05-rehearsal-2026-10-07/b05_build_proposals.py` | `C:/Users/weo/Desktop/api` | 0 |
| review report + progress ledger | `./examdata/.venv/Scripts/python.exe integration-staging/runtime/b05-rehearsal-2026-10-07/b05_build_report.py` | `C:/Users/weo/Desktop/api` | 0 |

Run notes:

- **route probe (first and only run, clean)**: 98/98 checks clean on the first run; the raw capture is evidence/probe_run1.json (stderr holds only the Starlette deprecation warning)
- **validate (probe from 3 cwds)**: the validator itself writes the frozen evidence under docs/integration/execution/evidence/B05/b05-rehearsal-2026-10-07/
- **merge + rollback proposals, first run**: failed exactly one digest check, new_files_exactly_one_vs_parent: the comparison took the parent file set to exclude the parent's own manifest while the child carries a byte-identical copy of it; fixed by comparing against the parent's full file set; details in process_observations
- **merge + rollback proposals, rerun after the fix**: all 8 digest checks true

## 4. Test results

- **Route probe**: 98 checks × 3 working directories = 294 check executions, 0 failed.
- **Isolated staged suite**: 887 passed, 1 warning in 43.11s (exit 0). Unchanged from the R04/B02/B03/B04 baseline of 887; B05 adds no test file to that suite.
- **Build checks**: 17/17.

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
- `D_stability_digests_match_b04_ledger`
- `D_stability_ids_and_delta_match_b04_ledger`
- `N1_legacy_probes_unchanged`

## 5. What the checks cover

- **Section A — import and root configuration (12 checks)**: root env is the candidate, no staging-root override, no PYTHONPATH, candidate `src/` first on `sys.path`, every module origin inside the candidate (including the new `examdata.integration.adapters.active_owner`), no original-tree module loaded, no product import of testing guards, 28 schema files parse, quality dimensions and identity kinds match the code, synthetic Node discovery (`fake_cli`) resolves inside the candidate, legacy bridge entry imports from the candidate.
- **Section B — worksheet, registry and ordering (14 checks)**: the A12 worksheet holds 71 rows (70 GET + 1 POST `/sample`); the v2 registry has 34 implemented / 0 deferred specs of which 5 are binary; runtime, spec and advertised pairs agree; HEAD pairs are binary-only; GET 34/34 and HEAD 5/5 first-match their own route; no static route is shadowed; and no two distinct path patterns intersect (561 pairs).
- **Section C — host mechanics and behaviour (19 checks)**: host shape pre-attach (80 routes, 76 doc paths), the legacy prefix is kept 80→81, exactly one wrapper `_IncludedRouter` is appended; all 71 legacy rows and 7 extra probes stay byte-identical; the legacy stack-boom body stays pinned; binary fixture ids, 200 / 206 / 304 / HEAD responses pinned; the new `C_material_content_200_pinned` check pins the synthetic material content response under the seam; and the six v2 controls serve typed envelopes (invalid_request, internal_error, not_found, route_not_found, method_not_allowed, info envelope) that all differ from their pre-attach baselines.
- **Section D — combined OpenAPI and B04-ledger stability (10 checks)**: the path delta is exactly the registry (34 added, 0 removed, none unexpected); the 76 pre-attach paths' operations are unchanged; 115 operation ids are unique; the 39 v2 operation ids match the standalone app; binary rows are documented with their media types; non-binary 200 responses serve the envelope schema; `/openapi.json` serves the same document as the direct call; a second instance yields the same digest; and the two new stability checks confirm the combined OpenAPI, standalone v2, legacy-operations and composed-route-table digests plus the 39 ids and the 34-path delta still match the frozen B04 progress ledger.
- **Section E — stability (7 checks)**: candidate bytes unchanged by the probe; fixture and contract digests unchanged; the manifest recomputes to 190 files and the same tree digest; counts disclosed (190 digest / 191 on-disk non-cache); the B04 compose hook stays frozen (`e220c007…`); no embedded `data:` payloads; scratch marker written inside the run's evidence/tmp.
- **Section S — the active-owner seam (10 checks)**: the synthetic fixture source validates with 2 rows per family; the default dataset really uses the fixture source; row access returns isolated copies; deferred families flow through the seam unchanged; route rows carry the synthetic markers with all five routes at 200; CIE event null date/session/raw_text fields are preserved; unavailable seasons carry their reason; unknown window boundaries stay declared with null parsed values; a private injected source is served by the routes; and the default fixture path still serves after that injection.
- **Sections N1–N6 — route-layer negative controls (16 checks, 15 negative)**: a raw `include_router` would serve unshaped v2 errors and a wrong content type for the binary row (refused by the hook); the unscoped install would change exactly three legacy probes and rewrite their error shapes to envelopes (the deliberate, documented difference); mounting under the legacy prefix documents no v2 paths; double attach is refused and leaves the host unchanged; late attach is refused and adds no v2 paths; a non-FastAPI host is refused; and every legacy probe stays unchanged under the composed application (`N1_legacy_probes_unchanged`).
- **Section N7 — the seam refuse-path (10 negative checks)**: the seam refuses a missing synthetic evidence marker, a missing deferred status marker, non-synthetic source evidence, live-access material, an unavailable season without a reason, a date without its raw timetable text, an unknown boundary carrying a parsed value, an undeclared missing boundary, non-list family rows, and the dataset refuses an unvalidated source; the real active-owner integration stays `deferred_active_owner`.

## 6. Import status of the new candidate

The candidate's imports resolve from the candidate itself through `EXAMDATA_INTEGRATION_ROOT` only — no `PYTHONPATH`, no staging-root override — and the same result holds from all three working directories: the workspace root, an arbitrary directory name under the run's evidence/tmp, and a path containing spaces and non-ASCII characters (`cwd with spaces ünïcode`). Module origins, schema access, synthetic Node discovery and the runtime/legacy entry points were re-verified from those directories, and discovery, routing stability and seam digests are identical across all three (`discovery_identical_across_cwds`, `stability_identical_across_cwds`, `seam_identical_across_cwds` = True). Real Node/source validation against the original project remains `not_run`.

| Check | Result | Detail |
| --- | --- | --- |
| `A_env_root_is_candidate` | `True` | EXAMDATA_INTEGRATION_ROOT='C:\\Users\\weo\\Desktop\\api\\integration-staging\\runtime\\b05-rehearsal-2026-10-07\\candidates\\b05-adapters-v1' candidate=C:\Users\weo\Desktop\api\integration-staging\run… |
| `A_no_staging_override` | `True` | EXAMDATA_INTEGRATION_STAGING_ROOT must not be staged |
| `A_no_pythonpath` | `True` | PYTHONPATH=None |
| `A_candidate_src_first_on_path` | `True` | sys.path[0]='C:\\Users\\weo\\Desktop\\api\\integration-staging\\runtime\\b05-rehearsal-2026-10-07\\candidates\\b05-adapters-v1\\src' |
| `A_module_origins_within_candidate` | `True` | all candidate |
| `A_no_original_tree_module_loaded` | `True` | no module from the original tree |
| `A_product_no_testing_guard_imports` | `True` | no product import of testing guards |
| `A_schema_files_parse` | `True` | 28 schema file(s); malformed: none |
| `A_quality_dimensions_match_code` | `True` | all dimensions agree |
| `A_identity_kinds_match_code` | `True` | 14 kind(s); unrecognised: none |
| `A_node_discovery_candidate_root` | `True` | ids=['fake_cli'] problems=[] entry=C:\Users\weo\Desktop\api\integration-staging\runtime\b05-rehearsal-2026-10-07\candidates\b05-adapters-v1\components\fake-node-cli\fake-cli.mjs |
| `A_legacy_bridge_entry_imports_within_candidate` | `True` | C:\Users\weo\Desktop\api\integration-staging\runtime\b05-rehearsal-2026-10-07\candidates\b05-adapters-v1\src\examdata\integration\legacy\bridge.py |

## 7. Proposals

- Merge proposal: `docs/integration/execution/B05_MERGE_PROPOSAL.json` — 4 entries, 3 requiring the human release, 1 staging-only; 1 new file vs the parent and 2 rewritten staged files. The release-required entries are the new module `examdata/src/examdata/integration/adapters/active_owner.py` (add_file) and the two rewrites at `examdata/src/examdata/integration/api/dataset.py` (superseding R0104 RP-0005) and `examdata/src/examdata/integration/api/app.py` (superseding A14 MM-0015); all three are add_file semantics because the integration package is new relative to the original project.
- Rollback proposal: `docs/integration/execution/B05_ROLLBACK_PROPOSAL.json` — 4 entries; of the original-level actions 3 are reversible by deleting the added target file (guarded by the recorded sha256) and 1 has no original action at all.

Both are marked `proposal_only_not_merged`. Nothing has been applied to the original project. The seam serves only clearly labelled synthetic fixtures; the real active-owner integration remains `deferred_active_owner`.

## 8. Live ledger and gates

- `docs/integration/execution/execution-ledger.json` sha256 `6d4449d3997b437fd3ea3a1fe7925fc78a7c0adbe0a5d3b793d6a8063101b4ba`
- Expected frozen value: `6d4449d3997b437fd3ea3a1fe7925fc78a7c0adbe0a5d3b793d6a8063101b4ba`
- Byte-unchanged: `True`
- Gates open: [] (all closed: `True`)

The live execution ledger is byte-identical to its frozen pre-rehearsal value and was not written by this rehearsal; the seven gates remain closed.

## 9. Not run

- real merge into the original project — gate original_paths_released is closed; the plan entry remains a proposal (deferred_pending_release) and the original tree was never read, imported or written
- real active-owner integration (materials, syllabuses and timetables served by the original owner modules) — no owner release exists for the active-owner families; the seam serves only clearly labelled synthetic fixtures and the real integration stays deferred_active_owner
- real Node component execution — gate original_paths_released is closed; only synthetic fake-node-cli discovery is rehearsed, never executed
- real Node/source validation against the original project — gate original_paths_released is closed; the original tree was never read, imported or written
- real database schema / data-root migration — gate real_data_write_authorized is closed; no database is staged or touched; schema and data roots unchanged
- live service / upstream provider calls — gate upstream_requests_authorized is closed; only synthetic fixture providers ran
- deployment to any target — gate remote_deployment_authorized is closed; this candidate is private-only
- credential usage of any kind — no credential gate exists in the seven-gate model and none is needed: no credential is used; nothing was read, fabricated or staged

## 10. Not claimed / remaining blockers

Not claimed: `merged_pass`, `deployment`, `full B00/B01 completion`.

- original-project merge of the B05 entries — gate original_paths_released is closed; an explicit human release with an explicit scope is required. The merge proposal has 3 release-required entries, all add_file semantics because the whole integration package is new relative to the original project: add examdata/src/examdata/integration/adapters/active_owner.py; install the B05 bytes at examdata/src/examdata/integration/api/dataset.py (superseding R0104 RP-0005) and at examdata/src/examdata/integration/api/app.py (superseding A14 MM-0015); the candidate tree digest must be re-verified immediately before any original write.
- real active-owner integration (materials, syllabuses and timetables served by the original owner modules) — no owner release exists for the active-owner families; the seam serves only clearly labelled synthetic fixtures and the real integration stays deferred_active_owner
- real Node component execution (ielts-api / toefl-api) — gate original_paths_released is closed; only the synthetic fake-node-cli fixture is discovered (never executed)
- real database schema / data-root migration — gate real_data_write_authorized is closed; schema and data roots are deliberately unchanged by B05
- deployment to any target — gate remote_deployment_authorized is closed; the candidate is private-only
