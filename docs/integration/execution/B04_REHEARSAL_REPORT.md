# B04 rehearsal review report (private preparation only)

Generated: 2026-10-07T01:43:30+08:00  
Packet: **B04** — register v2 routes in the shared application  
Status: `b04_private_rehearsal_complete_pending_human_release`  
Probe verdict: `b04_rehearsal_valid_private_only`  
Probe findings: 0

Nothing in this report has been merged or deployed. The original project was not read, imported or written by any B04 step. All seven gates are closed.

## 1. What B04 rehearsed

B04 owns the registration of the staged v2 routes in the shared application. What can be done without the human release is a rehearsal: carry the B03 candidate byte-identically, add the one new composition module (the hook that attaches the v2 routes to the legacy application), then prove the acceptance properties that do not need the original tree — every baseline route stays registered byte-identically, the OpenAPI/route-inventory difference is exactly the 34 documented v2 paths, legacy defaults are unchanged, and the composition refuses double or late attaches.

## 2. Candidate and lineage

- Candidate: `integration-staging/runtime/b04-rehearsal-2026-10-07/candidates/b04-routes-v1`
- Parent: `integration-staging/runtime/b03-rehearsal-2026-10-07/candidates/b03-contracts-catalog-v1` (the B03 contracts/catalog candidate)
- Parent tree: 186 files, sha256 `bb745436318676eb0ed6f0f85d22eac55b369b45f7c555b9e0d1b437f6c4d0d5`
- Candidate tree: 188 files (187 carried from the parent + 1 new), sha256 `fd806f4c6116c3f5507a7a7b13879ac5d59f627929c7a54c2767b7a1f85f9cbc`
- Candidate digest reproducible from the tree on disk: `True` (re-checked independently by the validator, not just self-reported by the builder)
- Parent manifest sha256 unchanged at build time: `9cf639e53fa4a49022ce73d0acb35a9ec6f54e234a5786adaa8fb6029e3898cf`
- Count explanation: the parent digest covers 186 files (B03's rule excluded B03's own manifest); B04 copies all 187 B03 on-disk files and adds 1 new module, so the candidate digest covers 188 and on-disk is 189 = 188 + the B04 manifest.

The parent tree digest was re-computed after the copy and again at proposal time and is unchanged (`parent_tree_reverified` in the merge proposal).

## 3. Commands, working directory and exit codes

| Step | Command | cwd | Exit |
| --- | --- | --- | --- |
| build candidate | `./examdata/.venv/Scripts/python.exe integration-staging/runtime/b04-rehearsal-2026-10-07/b04_build_candidate.py` | `C:/Users/weo/Desktop/api` | 0 |
| route probe, manual iteration 1 | `B04_CANDIDATE_ROOT=integration-staging/runtime/b04-rehearsal-2026-10-07/candidates/b04-routes-v1 B04_WORKSPACE_ROOT=C:/Users/weo/Desktop/api B04_TMP_DIR=integration-staging/runtime/b04-rehearsal-2026-10-07/evidence/tmp EXAMDATA_INTEGRATION_ROOT=integration-staging/runtime/b04-rehearsal-2026-10-07/candidates/b04-routes-v1 PYTHONIOENCODING=utf-8 ./examdata/.venv/Scripts/python.exe integration-staging/runtime/b04-rehearsal-2026-10-07/b04_route_probe.py` | `C:/Users/weo/Desktop/api` | 1 |
| route probe, manual iteration 2 | `B04_CANDIDATE_ROOT=integration-staging/runtime/b04-rehearsal-2026-10-07/candidates/b04-routes-v1 B04_WORKSPACE_ROOT=C:/Users/weo/Desktop/api B04_TMP_DIR=integration-staging/runtime/b04-rehearsal-2026-10-07/evidence/tmp EXAMDATA_INTEGRATION_ROOT=integration-staging/runtime/b04-rehearsal-2026-10-07/candidates/b04-routes-v1 PYTHONIOENCODING=utf-8 ./examdata/.venv/Scripts/python.exe integration-staging/runtime/b04-rehearsal-2026-10-07/b04_route_probe.py` | `C:/Users/weo/Desktop/api` | 0 |
| validate (probe from 3 cwds) | `./examdata/.venv/Scripts/python.exe integration-staging/runtime/b04-rehearsal-2026-10-07/b04_validate.py` | `C:/Users/weo/Desktop/api` | 0 |
| isolated staged suite | `bash integration-staging/tools/run_staged_tests.sh -q` | `C:/Users/weo/Desktop/api` | 0 |
| merge + rollback proposals | `./examdata/.venv/Scripts/python.exe integration-staging/runtime/b04-rehearsal-2026-10-07/b04_build_proposals.py` | `C:/Users/weo/Desktop/api` | 0 |
| review report + progress ledger | `./examdata/.venv/Scripts/python.exe integration-staging/runtime/b04-rehearsal-2026-10-07/b04_build_report.py` | `C:/Users/weo/Desktop/api` | 0 |

## 4. Test results

- **Route probe**: 75 checks x 3 working directories = 225 check executions, 0 failed.
- **Isolated staged suite**: 887 passed, 1 warning in 44.76s (exit 0). Unchanged from the R04/B02/B03 baseline of 887; B04 adds no test file to that suite.
- **Build checks**: 11/11.

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

### Positive controls

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
- `N1_legacy_probes_unchanged`

## 5. What the checks cover

- **Section A — import and root configuration (12 checks)**: root env is the candidate, no staging-root override, no PYTHONPATH, candidate `src/` first on `sys.path`, every module origin inside the candidate, no original-tree module loaded, no product import of testing guards, 28 schema files parse, quality dimensions and identity kinds match the code, synthetic Node discovery (`fake_cli`) resolves inside the candidate, legacy bridge entry imports from the candidate.
- **Section B — worksheet, registry and ordering (14 checks)**: the A12 worksheet holds 71 rows (70 GET + 1 POST `/sample`); the v2 registry has 34 implemented / 0 deferred specs of which 5 are binary; runtime, spec and advertised pairs agree; HEAD pairs are binary-only; GET 34/34 and HEAD 5/5 first-match their own route; no static route is shadowed; and no two distinct path patterns intersect (561 pairs).
- **Section C — host mechanics and behaviour (18 checks)**: host shape pre-attach (80 routes, 76 doc paths), the legacy prefix is kept 80→81, exactly one wrapper `_IncludedRouter` is appended; all 71 legacy rows and 7 extra probes stay byte-identical; the legacy stack-boom body stays pinned; binary fixture ids, 200 / 206 / 304 / HEAD responses pinned; and the six v2 controls serve typed envelopes (invalid_request, internal_error, not_found, route_not_found, method_not_allowed, info envelope) that all differ from their pre-attach baselines.
- **Section D — combined OpenAPI (8 checks)**: the path delta is exactly the registry (34 added, 0 removed, none unexpected); the 76 pre-attach paths' operations are unchanged; 115 operation ids are unique; the 39 v2 operation ids match the standalone app; binary rows are documented with their media types; non-binary 200 responses serve the envelope schema; `/openapi.json` serves the same document as the direct call; a second instance yields the same digest.
- **Section E — stability (7 checks)**: candidate bytes unchanged by the probe; fixture and contract digests unchanged; the manifest recomputes to 188 files; counts disclosed (188 digest / 189 on disk); the compose hook matches its tooling source; no embedded `data:` payloads; scratch marker written inside the run's evidence/tmp.
- **Sections N1-N6 — negative controls (16 checks, 15 negative)**: a raw `include_router` would serve unshaped v2 errors and a wrong content type for the binary row (refused by the hook); the unscoped install would change exactly three legacy probes and rewrite their error shapes to envelopes (the deliberate, documented difference); mounting under the legacy prefix documents no v2 paths; double attach is refused and leaves the host unchanged; late attach is refused and adds no v2 paths; a non-FastAPI host is refused; and every legacy probe stays unchanged under the composed application.

## 6. Import status of the new candidate

The candidate's imports resolve from the candidate itself through `EXAMDATA_INTEGRATION_ROOT` only — no `PYTHONPATH`, no staging-root override — and the same result holds from all three working directories, including the path with spaces and non-ASCII characters. The routing stability digests (combined OpenAPI, standalone v2, legacy operations, composed route table, 39 operation ids, path delta) are identical across all three working directories.

| Check | Result | Detail |
| --- | --- | --- |
| `A_env_root_is_candidate` | `True` | EXAMDATA_INTEGRATION_ROOT='C:\\Users\\weo\\Desktop\\api\\integration-staging\\runtime\\b04-rehearsal-2026-10-07\\candidates\\b04-routes-v1' candidate=C:\Users\weo\Desktop\api\integration-staging\runti… |
| `A_no_staging_override` | `True` | EXAMDATA_INTEGRATION_STAGING_ROOT must not be staged |
| `A_no_pythonpath` | `True` | PYTHONPATH=None |
| `A_candidate_src_first_on_path` | `True` | sys.path[0]='C:\\Users\\weo\\Desktop\\api\\integration-staging\\runtime\\b04-rehearsal-2026-10-07\\candidates\\b04-routes-v1\\src' |
| `A_module_origins_within_candidate` | `True` | all candidate |
| `A_no_original_tree_module_loaded` | `True` | no module from the original tree |
| `A_product_no_testing_guard_imports` | `True` | no product import of testing guards |
| `A_schema_files_parse` | `True` | 28 schema file(s); malformed: none |
| `A_quality_dimensions_match_code` | `True` | all dimensions agree |
| `A_identity_kinds_match_code` | `True` | 14 kind(s); unrecognised: none |
| `A_node_discovery_candidate_root` | `True` | ids=['fake_cli'] problems=[] entry=C:\Users\weo\Desktop\api\integration-staging\runtime\b04-rehearsal-2026-10-07\candidates\b04-routes-v1\components\fake-node-cli\fake-cli.mjs |
| `A_legacy_bridge_entry_imports_within_candidate` | `True` | C:\Users\weo\Desktop\api\integration-staging\runtime\b04-rehearsal-2026-10-07\candidates\b04-routes-v1\src\examdata\integration\legacy\bridge.py |

## 7. Proposals

- Merge proposal: `docs/integration/execution/B04_MERGE_PROPOSAL.json` — 3 entries, 2 requiring the human release, 1 staging-only. The release-required entries are the new module `examdata/src/examdata/integration/api/compose.py` and the planned edit to `examdata/src/examdata/api/app.py` (deferred_pending_release).
- Rollback proposal: `docs/integration/execution/B04_ROLLBACK_PROPOSAL.json`.

Both are marked `proposal_only_not_merged`. Nothing has been applied to the original project.

## 8. Live ledger and gates

- `docs/integration/execution/execution-ledger.json` sha256 `6d4449d3997b437fd3ea3a1fe7925fc78a7c0adbe0a5d3b793d6a8063101b4ba`
- Expected frozen value: `6d4449d3997b437fd3ea3a1fe7925fc78a7c0adbe0a5d3b793d6a8063101b4ba`
- Byte-unchanged: `True`
- Gates open: [] (all closed: `True`)

## 9. Not run

- real merge into examdata/src/examdata/api/app.py — gate original_paths_released is closed; the app.py change remains a proposal (deferred_pending_release) and the original tree was never read, imported or written
- real Node component execution — gate original_paths_released is closed; only synthetic fake-node-cli discovery is rehearsed, never executed
- real Node/source validation against the original project — gate original_paths_released is closed; the original tree was never read, imported or written
- real database schema / data-root migration — gate real_data_write_authorized is closed; no database is staged or touched; schema and data roots unchanged
- live service / upstream provider calls — gate upstream_requests_authorized is closed; only synthetic fixture providers ran
- deployment to any target — gate remote_deployment_authorized is closed; this candidate is private-only
- credential usage of any kind — no credential gate exists in the seven-gate model and none is needed: no credential is used; nothing was read, fabricated or staged

## 10. Not claimed / remaining blockers

Not claimed: `merged_pass`, `deployment`, `full B00/B01 completion`.

- original-project merge of the B04 entries — gate original_paths_released is closed; an explicit human release with an explicit scope is required. The merge proposal has 2 release-required entries: add examdata/src/examdata/integration/api/compose.py and the planned edit to examdata/src/examdata/api/app.py, which stays deferred_pending_release; the app.py base hash (753749fa…) must be re-verified at release time.
- real Node component execution (ielts-api / toefl-api) — the original components are not released; only the synthetic fake-node-cli fixture is discovered and it is never executed
- real database schema / data-root migration — gate real_data_write_authorized is closed; schema and data roots are deliberately unchanged by B04
- deployment to any target — gate remote_deployment_authorized is closed; the candidate is private-only
