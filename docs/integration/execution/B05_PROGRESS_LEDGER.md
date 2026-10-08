# B05 private progress ledger

Generated: 2026-10-07T03:05:06+08:00  
Status: `b05_private_rehearsal_complete_pending_human_release`

This is a private progress record, not the live execution ledger (`docs/integration/execution/execution-ledger.json`).

| Item | Value |
| --- | --- |
| live ledger sha256 | `6d4449d3997b437fd3ea3a1fe7925fc78a7c0adbe0a5d3b793d6a8063101b4ba` |
| live ledger byte-unchanged | `True` |
| all gates closed | `True` |
| new staging scripts | 5 |
| new candidate module sources | 1 |
| edited candidate module sources | 2 |
| candidates | 1 |
| candidate tree files | 190 |
| candidate files on disk | 191 |
| new files added by B05 | 1 |
| edited files rewritten by B05 | 2 |
| original project files written | 0 |
| frozen evidence files rewritten | 0 |
| probe check executions | 294 (0 failed) |
| isolated staged suite | 887 passed, 1 warning in 43.11s |
| probe verdict | `b05_rehearsal_valid_private_only` |

## Count explanations

- **new_staging_scripts**: 5 new B05 scripts: b05_build_candidate.py, b05_route_probe.py, b05_validate.py, b05_build_proposals.py, b05_build_report.py
- **new_candidate_module_source_files**: 1 new private module source: tools/active_owner.py, byte-identical to the candidate's src/examdata/integration/adapters/active_owner.py (both sha256 0d8116f0…)
- **edited_candidate_module_source_files**: 2 rewritten module sources under tools/: dataset.py (c341ce30… → a9a72a7a…) and app.py (afa2602e… → aa3ba9c5…), each byte-identical to the candidate's copy; evidence/source_edits.diff records both rewrites plus the new module against the B04 bytes
- **candidates**: 1 new private candidate: b05-adapters-v1, a child of the B04 routes candidate
- **candidate_files_copied_from_parent**: 189 = the B04 on-disk files (188 digest files + B04_CANDIDATE_MANIFEST.json) carried byte-for-byte; 187 of them stay verbatim and 2 are rewritten by B05
- **new_files_added_by_b05**: 1 = src/examdata/integration/adapters/active_owner.py (the active-owner seam module); everything else is carried or rewritten from the parent
- **edited_files_rewritten_by_b05**: 2 = src/examdata/integration/api/dataset.py and src/examdata/integration/api/app.py, rewritten to read the five feature families through the seam; both supersede previously staged bytes (dataset: A14 MM-0017 → R0104 RP-0005 → B05; app: A14 MM-0015 → B05)
- **candidate_tree_files**: 190 digest files = 189 carried (187 verbatim + 2 rewritten) + 1 new module; B05's digest rule excludes its own manifest and skips __pycache__/.pytest_cache
- **candidate_files_on_disk**: 191 = 190 digest files + B05_CANDIDATE_MANIFEST.json (non-cache files on disk); the 49 __pycache__ .pyc files are not counted by the digest rule
- **parent_tree_files**: 188 = B04's digest count, which excluded B04's own manifest (B04 on-disk was 189); the two numbers describe different file sets by rule
- **original_project_files_written**: 0: nothing was written outside integration-staging/ and docs/integration/execution/
- **frozen_evidence_files_rewritten**: 0 existing frozen files rewritten: evidence/A00–B04/**, evidence/R0104/** and the B02/B03/B04 runtime trees were read-only; B05's own evidence under evidence/B05/b05-rehearsal-2026-10-07/ was created new and nothing there was overwritten

## Not run

- real merge into the original project — gate original_paths_released is closed; the plan entry remains a proposal (deferred_pending_release) and the original tree was never read, imported or written
- real active-owner integration (materials, syllabuses and timetables served by the original owner modules) — no owner release exists for the active-owner families; the seam serves only clearly labelled synthetic fixtures and the real integration stays deferred_active_owner
- real Node component execution — gate original_paths_released is closed; only synthetic fake-node-cli discovery is rehearsed, never executed
- real Node/source validation against the original project — gate original_paths_released is closed; the original tree was never read, imported or written
- real database schema / data-root migration — gate real_data_write_authorized is closed; no database is staged or touched; schema and data roots unchanged
- live service / upstream provider calls — gate upstream_requests_authorized is closed; only synthetic fixture providers ran
- deployment to any target — gate remote_deployment_authorized is closed; this candidate is private-only
- credential usage of any kind — no credential gate exists in the seven-gate model and none is needed: no credential is used; nothing was read, fabricated or staged

## Remaining blockers

- original-project merge of the B05 entries — gate original_paths_released is closed; an explicit human release with an explicit scope is required. The merge proposal has 3 release-required entries, all add_file semantics because the whole integration package is new relative to the original project: add examdata/src/examdata/integration/adapters/active_owner.py; install the B05 bytes at examdata/src/examdata/integration/api/dataset.py (superseding R0104 RP-0005) and at examdata/src/examdata/integration/api/app.py (superseding A14 MM-0015); the candidate tree digest must be re-verified immediately before any original write.
- real active-owner integration (materials, syllabuses and timetables served by the original owner modules) — no owner release exists for the active-owner families; the seam serves only clearly labelled synthetic fixtures and the real integration stays deferred_active_owner
- real Node component execution (ielts-api / toefl-api) — gate original_paths_released is closed; only the synthetic fake-node-cli fixture is discovered (never executed)
- real database schema / data-root migration — gate real_data_write_authorized is closed; schema and data roots are deliberately unchanged by B05
- deployment to any target — gate remote_deployment_authorized is closed; the candidate is private-only
