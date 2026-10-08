# B03 rehearsal review report (private preparation only)

Generated: 2026-10-07T00:38:28+08:00  
Packet: **B03** — integrate contracts, registry and local read catalog  
Status: `b03_private_rehearsal_complete_pending_human_release`  
Probe verdict: `b03_rehearsal_valid_private_only`  
Probe findings: 0

Nothing in this report has been merged or deployed. The original project was not read, imported or written by any B03 step. All seven gates are closed.

## 1. What B03 rehearsed

B03 owns the contracts, provider registry and local read catalog at the target layout. What can be done without the human release is a rehearsal: carry the B02 candidate byte-identically, then prove the acceptance properties that do not need the original tree — native lookup round trips, revision publication and rollback, and preserved decisions/provenance — plus the target-layout import and root configuration the earlier packets established.

## 2. Candidate and lineage

- Candidate: `integration-staging/runtime/b03-rehearsal-2026-10-07/candidates/b03-contracts-catalog-v1`
- Parent: `integration-staging/runtime/b02-rehearsal-20261006/candidates/b02-shared-config-v1` (the B02 shared-config candidate)
- Parent tree: 185 files, sha256 `463628cff11ef88ef9f42898cf31647483edcafb369bcc4c4b96dec2b7cb22cf`
- Candidate tree: 186 files (186 carried from the parent + 0 new), sha256 `bb745436318676eb0ed6f0f85d22eac55b369b45f7c555b9e0d1b437f6c4d0d5`
- Candidate digest reproducible from the tree on disk: `True` (re-checked independently by the validator, not just self-reported by the builder)
- Parent manifest sha256 unchanged at build time: `59dfc8c79b59d86ae67313cdb96048d5bb73e365405070de3e9b2a872264648d`
- Count explanation: the candidate digest covers 186 files = 185 parent-digest files + the carried B02 manifest (B02's own digest excluded that manifest; in B03 it is an ordinary carried file). On disk: 187 = 186 + the B03 manifest.

The parent tree digest was re-computed after the copy and again at proposal time and is unchanged (`parent_tree_reverified` in the merge proposal).

## 3. Commands, working directory and exit codes

| Step | Command | cwd | Exit |
| --- | --- | --- | --- |
| build candidate | `./examdata/.venv/Scripts/python.exe integration-staging/runtime/b03-rehearsal-2026-10-07/b03_build_candidate.py` | `C:/Users/weo/Desktop/api` | 0 |
| validate (probe from 3 cwds) | `./examdata/.venv/Scripts/python.exe integration-staging/runtime/b03-rehearsal-2026-10-07/b03_validate.py` | `C:/Users/weo/Desktop/api` | 0 |
| isolated staged suite | `bash integration-staging/tools/run_staged_tests.sh -q` | `C:/Users/weo/Desktop/api` | 0 |
| merge + rollback proposals | `./examdata/.venv/Scripts/python.exe integration-staging/runtime/b03-rehearsal-2026-10-07/b03_build_proposals.py` | `C:/Users/weo/Desktop/api` | 0 |
| review report + progress ledger | `./examdata/.venv/Scripts/python.exe integration-staging/runtime/b03-rehearsal-2026-10-07/b03_build_report.py` | `C:/Users/weo/Desktop/api` | 0 |

## 4. Test results

- **Probe**: 58 checks x 3 working directories = 174 check executions, 0 failed.
- **Isolated staged suite**: 887 passed, 1 warning in 41.70s (exit 0). Unchanged from the R04/B02 baseline of 887; B03 adds no test file to that suite.
- **Build checks**: 8/8.

### Negative results (the checks that must refuse or stay unchanged)

- `D_stale_publish_rejected_pointer_unchanged`
- `D_publish_none_rejected`
- `D_tampered_snapshot_rejected_pointer_unchanged`
- `D_cursor_tampered_invalid`
- `D_cursor_stale_revision_rejected`
- `F_edexcel_questions_unsupported`
- `F_cie_courses_filter_rejected`
- `F_unknown_alias_refused`
- `F_alias_rebind_refused`
- `F_unknown_provider_failed`
- `F_unavailable_provider_reported`
- `F_view_unknown_system_503`
- `F_failing_provider_sanitized`
- `G_duplicate_native_id_raises`
- `G_duplicate_native_id_build_fails`
- `G_unexplained_removal_rejected`
- `G_unexplained_quality_upgrade_rejected`
- `G_incomplete_reference_rejected`

### Positive controls

- `B_revision_reproducible`
- `B_snapshot_builds`
- `B_counts_match_independent_derivation`
- `B_reference_integrity`
- `C_course_roundtrip_cie`
- `C_container_roundtrip_cie`
- `C_question_roundtrip_cie`
- `C_question_roundtrip_ielts`
- `C_container_roundtrip_edexcel`
- `C_container_roundtrip_ielts`
- `C_assets_roundtrip`
- `D_publish_a_then_b_cas`
- `D_rollback_restores_previous`
- `D_cursor_roundtrip`
- `E_decisions_and_provenance_roundtrip`
- `E_provenance_fields_preserved`
- `E_unknown_token_roundtrip`
- `F_null_provider_empty_success`
- `G_explained_removal_accepted`
- `G_base_fixture_build_ok`
- `G_base_aliases_resolve`

## 5. What the checks cover

- **Section A — import and root configuration (12 checks)**: root env is the candidate, no staging-root override, no PYTHONPATH, candidate `src/` first on `sys.path`, every module origin inside the candidate, no original-tree module loaded, no product import of testing guards, schema files parse, quality dimensions and identity kinds match the code, synthetic Node discovery from the candidate, legacy bridge entry inside the candidate.
- **Section B — catalog build (6 checks)**: the catalog builds from synthetic fixture providers reproducibly, file counts match an independent derivation, and reference integrity holds (no dangling references).
- **Section C — native lookup round trips (7 checks)**: CIE course, container and question; IELTS question and container; Edexcel container; and asset locators.
- **Section D — publication, rollback, cursors (8 checks)**: publication is compare-and-swap (A then B), stale / tampered / none publications are rejected with the pointer bytes unchanged, rollback restores the previous revision, cursors round-trip and tampered / stale cursors are rejected.
- **Section E — decisions and provenance (5 checks)**: decisions and provenance round-trip, provenance fields are preserved, the unknown token round-trips, deferred systems report availability honestly, and deferred fixtures are labelled.
- **Section F — provider registry and view errors (9 checks)**: unsupported capability / filter refused (422), unknown alias refused, alias rebind refused, unknown provider fails, unavailable provider reported (503), failing provider sanitized, null provider returns empty success.
- **Section G — base fixture and registry guards (8 checks)**: base fixture builds, duplicate native id rejected, unexplained removal / quality upgrade rejected, explained removal accepted, incomplete reference rejected.
- **Section H — byte stability (3 checks)**: candidate bytes unchanged by the probe, fixture and contract digests unchanged, no embedded `data:` payloads.

## 6. Import status of the new candidate

The candidate's imports resolve from the candidate itself through `EXAMDATA_INTEGRATION_ROOT` only — no `PYTHONPATH`, no staging-root override — and the same result holds from all three working directories, including the path with spaces and non-ASCII characters.

| Check | Result | Detail |
| --- | --- | --- |
| `A_env_root_is_candidate` | `True` | EXAMDATA_INTEGRATION_ROOT='C:\\Users\\weo\\Desktop\\api\\integration-staging\\runtime\\b03-rehearsal-2026-10-07\\candidates\\b03-contracts-catalog-v1' candidate=C:\Users\weo\Desktop\api\integration-st… |
| `A_no_staging_override` | `True` | EXAMDATA_INTEGRATION_STAGING_ROOT must not be staged |
| `A_no_pythonpath` | `True` | PYTHONPATH=None |
| `A_candidate_src_first_on_path` | `True` | sys.path[0]='C:\\Users\\weo\\Desktop\\api\\integration-staging\\runtime\\b03-rehearsal-2026-10-07\\candidates\\b03-contracts-catalog-v1\\src' |
| `A_module_origins_within_candidate` | `True` | all candidate |
| `A_no_original_tree_module_loaded` | `True` | no module from the original tree |
| `A_product_no_testing_guard_imports` | `True` | no product import of testing guards |
| `A_schema_files_parse` | `True` | 28 schema file(s); malformed: none |
| `A_quality_dimensions_match_code` | `True` | all dimensions agree |
| `A_identity_kinds_match_code` | `True` | 14 kind(s); unrecognised: none |
| `A_node_discovery_candidate_root` | `True` | ids=['fake_cli'] problems=[] entry=C:\Users\weo\Desktop\api\integration-staging\runtime\b03-rehearsal-2026-10-07\candidates\b03-contracts-catalog-v1\components\fake-node-cli\fake-cli.mjs |
| `A_legacy_bridge_entry_imports_within_candidate` | `True` | C:\Users\weo\Desktop\api\integration-staging\runtime\b03-rehearsal-2026-10-07\candidates\b03-contracts-catalog-v1\src\examdata\integration\legacy\bridge.py |

## 7. Proposals

- Merge proposal: `docs/integration/execution/B03_MERGE_PROPOSAL.json` — 1 entry, 0 requiring the human release, 1 staging-only. B03 adds zero files, so no original-facing entry is re-proposed here.
- Rollback proposal: `docs/integration/execution/B03_ROLLBACK_PROPOSAL.json`.

Both are marked `proposal_only_not_merged`. Nothing has been applied to the original project.

## 8. Live ledger and gates

- `docs/integration/execution/execution-ledger.json` sha256 `6d4449d3997b437fd3ea3a1fe7925fc78a7c0adbe0a5d3b793d6a8063101b4ba`
- Expected frozen value: `6d4449d3997b437fd3ea3a1fe7925fc78a7c0adbe0a5d3b793d6a8063101b4ba`
- Byte-unchanged: `True`
- Gates open: [] (all closed: `True`)

## 9. Not run

- real Node component execution — gate original_paths_released is closed; only synthetic fake-node-cli discovery is rehearsed, never executed
- real Node/source validation against the original project — gate original_paths_released is closed; the original tree was never read, imported or written
- real database schema / data-root migration — gate real_data_write_authorized is closed; no database is staged or touched; schema and data roots unchanged
- live service / upstream provider calls — gate upstream_requests_authorized is closed; only synthetic fixture providers ran
- deployment to any target — gate remote_deployment_authorized is closed; this candidate is private-only
- credential usage of any kind — no credential gate exists in the seven-gate model and none is needed: no credential is used; nothing was read, fabricated or staged

## 10. Not claimed / remaining blockers

Not claimed: `merged_pass`, `deployment`, `full B00/B01 completion`.

- original-project merge of the B03 payload — gate original_paths_released is closed; an explicit human release with an explicit scope is required. B03 adds zero new files, so a release would apply the R0104 and B02 proposals.
- real Node component execution (ielts-api / toefl-api) — the original components are not released; only the synthetic fake-node-cli fixture is discovered and it is never executed
- real database schema / data-root migration — gate real_data_write_authorized is closed; schema and data roots are deliberately unchanged by B03
- deployment to any target — gate remote_deployment_authorized is closed; the candidate is private-only
