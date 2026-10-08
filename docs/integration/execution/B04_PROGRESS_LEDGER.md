# B04 private progress ledger

Generated: 2026-10-07T01:43:30+08:00  
Status: `b04_private_rehearsal_complete_pending_human_release`

This is a private progress record, not the live execution ledger (`docs/integration/execution/execution-ledger.json`).

| Item | Value |
| --- | --- |
| live ledger sha256 | `6d4449d3997b437fd3ea3a1fe7925fc78a7c0adbe0a5d3b793d6a8063101b4ba` |
| live ledger byte-unchanged | `True` |
| all gates closed | `True` |
| new staging scripts | 5 |
| new candidate module sources | 1 |
| candidates | 1 |
| candidate tree files | 188 |
| new files added by B04 | 1 |
| original project files written | 0 |
| frozen evidence files rewritten | 0 |
| probe check executions | 225 (0 failed) |
| isolated staged suite | 887 passed, 1 warning in 44.76s |
| probe verdict | `b04_rehearsal_valid_private_only` |

## Count explanations

- **new_staging_scripts**: 5 new B04 scripts: b04_build_candidate.py, b04_route_probe.py, b04_validate.py, b04_build_proposals.py, b04_build_report.py
- **new_candidate_module_source_files**: 1 new private module source: tools/compose.py, byte-identical to the candidate's src/examdata/integration/api/compose.py (both sha256 e220c007…)
- **candidates**: 1 new private candidate: b04-routes-v1, a child of the B03 candidate
- **candidate_files_copied_from_parent**: 187 = the B03 on-disk files (186 digest files + B03_CANDIDATE_MANIFEST.json) carried byte-identically
- **new_files_added_by_b04**: 1 = src/examdata/integration/api/compose.py (the composition hook); everything else is carried verbatim
- **candidate_tree_files**: 188 digest files = 187 carried + 1 new module; B04's digest rule excludes its own manifest
- **candidate_files_on_disk**: 189 = 188 digest files + B04_CANDIDATE_MANIFEST.json
- **parent_tree_files**: 186 = B03's digest count, which excluded B03's own manifest (B03 on-disk was 187); the two numbers describe different file sets by rule
- **original_project_files_written**: 0: nothing was written outside integration-staging/ and docs/integration/execution/
- **frozen_evidence_files_rewritten**: 0: evidence/B01/**, B02/**, B03/**, evidence/R0104/**, the B02/B03/R0104 runtime candidates and runtime/phase-b/** were read-only or untouched

## Not run

- real merge into examdata/src/examdata/api/app.py — gate original_paths_released is closed; the app.py change remains a proposal (deferred_pending_release) and the original tree was never read, imported or written
- real Node component execution — gate original_paths_released is closed; only synthetic fake-node-cli discovery is rehearsed, never executed
- real Node/source validation against the original project — gate original_paths_released is closed; the original tree was never read, imported or written
- real database schema / data-root migration — gate real_data_write_authorized is closed; no database is staged or touched; schema and data roots unchanged
- live service / upstream provider calls — gate upstream_requests_authorized is closed; only synthetic fixture providers ran
- deployment to any target — gate remote_deployment_authorized is closed; this candidate is private-only
- credential usage of any kind — no credential gate exists in the seven-gate model and none is needed: no credential is used; nothing was read, fabricated or staged

## Remaining blockers

- original-project merge of the B04 entries — gate original_paths_released is closed; an explicit human release with an explicit scope is required. The merge proposal has 2 release-required entries: add examdata/src/examdata/integration/api/compose.py and the planned edit to examdata/src/examdata/api/app.py, which stays deferred_pending_release; the app.py base hash (753749fa…) must be re-verified at release time.
- real Node component execution (ielts-api / toefl-api) — the original components are not released; only the synthetic fake-node-cli fixture is discovered and it is never executed
- real database schema / data-root migration — gate real_data_write_authorized is closed; schema and data roots are deliberately unchanged by B04
- deployment to any target — gate remote_deployment_authorized is closed; the candidate is private-only
