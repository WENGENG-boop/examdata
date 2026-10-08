# B06 private progress ledger

Generated: 2026-10-07T05:13:50+08:00  
Status: `b06_private_rehearsal_complete_pending_human_release`

This is a private progress record, not the live execution ledger (`docs/integration/execution/execution-ledger.json`).

| Item | Value |
| --- | --- |
| live ledger sha256 | `6d4449d3997b437fd3ea3a1fe7925fc78a7c0adbe0a5d3b793d6a8063101b4ba` |
| live ledger byte-unchanged | `True` |
| all gates closed | `True` |
| new staging scripts | 5 |
| new candidate module sources | 0 |
| new frontend files added by B06 | 17 |
| edited candidate module sources | 3 |
| candidates | 1 |
| candidate tree files | 208 |
| candidate files on disk | 209 |
| files copied from the parent | 191 |
| files carried verbatim | 188 |
| original project files written | 0 |
| frozen evidence files rewritten | 0 |
| probe check executions | 414 (0 failed) |
| cross-stack driver checks | 18 (0 failed) |
| candidate Node tests | 41/41 |
| isolated staged suite | 887 passed, 1 warning in 40.93s |
| probe verdict | `b06_rehearsal_valid_private_only` |

## Count explanations

- **new_staging_scripts**: 5 new B06 scripts: b06_build_candidate.py, b06_route_probe.py, b06_validate.py, b06_build_proposals.py, b06_build_report.py
- **new_candidate_module_source_files**: 0: B06 adds no new Python module; every Python module in the candidate is carried from B05 or one of the three rewritten files
- **new_frontend_files_added_by_b06**: 17 = the fifteen staged frontend files copied byte-for-byte from integration-staging/frontend/ (thirteen carried from the B01/A14 records MM-0229..MM-0241 plus the two staging PROVENANCE records B01 excluded from the merge) plus the rewritten frontend/server.mjs (the B01 planned original edit, packet B06) and the new frontend/tests/server.test.mjs
- **edited_candidate_module_source_files**: 3 rewritten module sources under tools/: app.py (aa3ba9c5… → 0edb0911…), dataset.py (a9a72a7a… → d0edabc7…) and view.py (441c1da3… → f03e549f…), each byte-identical to the candidate's copy; evidence/source_edits.diff records all three rewrites plus the two new frontend files against the B05 bytes
- **candidates**: 1 new private candidate: b06-frontend-v1, a child of the B05 adapters candidate
- **candidate_files_copied_from_parent**: 191 = the B05 on-disk non-cache files (190 digest files + B05_CANDIDATE_MANIFEST.json) carried byte-for-byte; 188 of them stay verbatim and 3 are rewritten by B06
- **candidate_files_carried_verbatim**: 188 = 191 copied minus the 3 rewritten modules; the recorded carried-verbatim tree digest is b9605c15…
- **candidate_tree_files**: 208 digest files = 188 carried verbatim + 3 rewritten + 17 new frontend files; B06's digest rule excludes its own manifest and skips __pycache__/.pytest_cache
- **candidate_files_on_disk**: 209 = 208 digest files + B06_CANDIDATE_MANIFEST.json; the rehearsal ran with PYTHONDONTWRITEBYTECODE=1 so the candidate carries no __pycache__ files and on-disk equals digest + manifest exactly
- **parent_tree_files**: 190 = B05's digest count, which excluded B05's own manifest (B05 on-disk non-cache was 191); the two numbers describe different file sets by rule
- **original_project_files_written**: 0: nothing was written outside integration-staging/ and docs/integration/execution/
- **frozen_evidence_files_rewritten**: 0 existing frozen files rewritten: evidence/A00–B05/**, evidence/R0104/** and the B02/B03/B04/B05 runtime trees were read-only; B06's own evidence under evidence/B06/b06-rehearsal-2026-10-07/ was created new and nothing there was overwritten

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
- credential usage of any kind — no credential gate exists in the seven-gate model and none is needed: no credential is used, read, fabricated or staged; the routing controls are synthetic request parameters with no secret values
- real frontend cutover (the staged page and server on the live service) — gate existing_service_cutover_authorized is closed; the staged frontend ran only on an ephemeral 127.0.0.1 port against the private read API
- real source-provider fetching from the frontend process — gate upstream_requests_authorized is closed; the candidate frontend carries no source-discovery logic and only proxies the private read API

## Remaining blockers

- original-project merge of the B06 entries — gate original_paths_released is closed; an explicit human release with an explicit scope is required. The merge proposal has 18 release-required entries of 21: the three rewritten modules (app.py, dataset.py, view.py; add_file semantics because the whole integration package is new relative to the original project) and the fifteen frontend entries (thirteen B01 records plus frontend/server.mjs and frontend/tests/server.test.mjs); the candidate tree digest must be re-verified immediately before any original write.
- frontend reconcile_modify reconciliation and the production port decision — four frontend entries are reconcile_modify (app.js, index.html, README.md, tests/search.test.mjs) and need the three-way semantic reconciliation against the released original tree that B01 deferred (three_way=false, gate was closed); the merged static server's production port strategy additionally needs an explicit human decision - the staged server defaults to an ephemeral port and refuses to bind 5188/8000 as a staging safety measure.
- real Node component execution (ielts-api / toefl-api) — gate original_paths_released is closed; the cross-stack rehearsal ran only against the private candidate and its staged frontend, on ephemeral loopback ports
- real database schema / data-root migration — gate real_data_write_authorized is closed; schema and data roots are deliberately unchanged by B06
- real frontend cutover and source-provider fetching — gates existing_service_cutover_authorized and upstream_requests_authorized are closed; the candidate frontend carries no source-discovery logic and only proxies the private read API
- deployment to any target — gate remote_deployment_authorized is closed; the candidate is private-only
