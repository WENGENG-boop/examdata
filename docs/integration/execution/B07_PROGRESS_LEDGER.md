# B07 private progress ledger

Generated: 2026-10-07T07:40:51+08:00  
Status: `b07_private_rehearsal_complete_pending_human_release`

This is a private progress record, not the live execution ledger (`docs/integration/execution/execution-ledger.json`).

| Item | Value |
| --- | --- |
| live ledger sha256 | `6d4449d3997b437fd3ea3a1fe7925fc78a7c0adbe0a5d3b793d6a8063101b4ba` |
| live ledger byte-unchanged | `True` |
| all gates closed | `True` |
| new staging scripts | 6 |
| new candidate module sources | 2 |
| new operations files added by B07 | 12 |
| edited candidate module sources | 2 |
| candidates | 1 |
| candidate tree files | 221 |
| candidate files on disk | 222 |
| files copied from the parent | 209 |
| files carried verbatim | 207 |
| original project files written | 0 |
| frozen evidence files rewritten | 0 |
| probe check executions | 522 (0 failed) |
| cross-stack driver checks | 18 (0 failed) |
| candidate Node tests | 41/41 |
| smoke import observations | 7 (structural_ok `True`) |
| isolated staged suite | 887 passed, 1 warning in 43.72s |
| probe verdict | `b07_rehearsal_valid_private_only` |

## Count explanations

- **new_staging_scripts**: 6 new B07 scripts: b07_build_candidate.py, b07_route_probe.py, b07_smoke_import.py, b07_validate.py, b07_build_proposals.py, b07_build_report.py (plus the rewritten module sources and fixtures authored under tools/, which count as candidate inputs, not as scripts)
- **new_candidate_module_source_files**: 2 = the new operations package modules against the parent: jobs.py (916ae7b1…) and published.py (54522b9e…), authored under tools/ and written byte-identical into src/examdata/integration/operations/ (source_sha256 == written_sha256 in the manifest)
- **new_operations_files_added_by_b07**: 12 = 2 new module sources (operations/jobs.py, operations/published.py) + 10 labelled synthetic operations fixture files under fixtures/synthetic/operations/operations-root/ (PROVENANCE.json, README.md, expected-manifest.json and seven batch checkpoint files: run-ok, run-ok-stale, run-partial, unsupported, cie-batch-8888, cie-batch-8888-stale, cie-location-batch); the fixtures are explicitly labelled synthetic control data, never real records
- **edited_candidate_module_source_files**: 2 rewritten module sources under tools/: app.py (0edb0911… → 81f9c3c9…) and dataset.py (d0edabc7… → c0d0d06c…), each byte-identical to the candidate's copy; evidence/source_edits.diff records both rewrites plus the two new modules and the ten fixtures against the B06 bytes (14 sections)
- **candidates**: 1 new private candidate: b07-operations-v1, a child of the B06 frontend candidate
- **candidate_files_copied_from_parent**: 209 = the B06 on-disk non-cache files (208 digest files + B06_CANDIDATE_MANIFEST.json) carried byte-for-byte; 207 of them stay verbatim and 2 are rewritten by B07
- **candidate_files_carried_verbatim**: 207 = 209 copied minus the 2 rewritten modules; the recorded carried-verbatim tree digest is fc59639b…
- **candidate_tree_files**: 221 digest files = 207 carried verbatim + 2 rewritten + 12 new (2 modules + 10 fixtures); B07's digest rule excludes its own manifest and skips __pycache__/.pytest_cache
- **candidate_files_on_disk**: 222 = 221 digest files + B07_CANDIDATE_MANIFEST.json; the rehearsal ran with PYTHONDONTWRITEBYTECODE=1 so the candidate carries no __pycache__ files and on-disk equals digest + manifest exactly
- **parent_tree_files**: 208 = B06's digest count, which excluded B06's own manifest (B06 on-disk non-cache was 209); the two numbers describe different file sets by rule
- **original_project_files_written**: 0: nothing was written outside integration-staging/ and docs/integration/execution/
- **frozen_evidence_files_rewritten**: 0 existing frozen files rewritten: evidence/A00–B06/**, evidence/R0104/** and the B02–B06 runtime trees were read-only; B07's own evidence under evidence/B07/b07-rehearsal-2026-10-07/ was created new and nothing there was overwritten; the failed probe capture is a new file kept at evidence/probe_run1.json and the clean rerun wrote evidence/probe_run2.json, not over it

## Not run

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

## Remaining blockers

- original-project merge of the B07 entries — gate original_paths_released is closed; an explicit human release with an explicit scope is required. The merge proposal has 14 release-required entries of 15: the two rewritten modules (app.py, dataset.py; add_file semantics because the whole integration package is new relative to the original project) and the twelve new files (operations/jobs.py, operations/published.py and the ten labelled synthetic operations fixtures); the candidate tree digest must be re-verified immediately before any original write.
- release decision spans both proposals — the B06 merge proposal's 18 release-required entries and B07's 14 should be decided together or stay deferred; the B07 proposal re-verifies the cross-reference against the B06 proposal (b06_merge_crossref_matches, supersession_chains_match) rather than re-proposing B06's entries
- real Node component execution (ielts-api / toefl-api) — gate original_paths_released is closed; the cross-stack rehearsal ran only against the private candidate and its staged frontend, on ephemeral loopback ports
- real database schema / data-root migration — gate real_data_write_authorized is closed; schema and data roots are deliberately unchanged by B07
- real operations enablement and source fetching/recovery — gates existing_service_cutover_authorized, upstream_requests_authorized and cie_resume_authorized are closed; the only operations root is the labelled synthetic fixture, and the stopped cie 9191 batch stays stopped - nothing is resumed, fetched or written back
- deployment to any target — gate remote_deployment_authorized is closed; the candidate is private-only
