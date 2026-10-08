# B06 merge proposal (private rehearsal only)

Generated: 2026-10-07T05:02:05+08:00  
Status: `proposal_only_nothing_merged_not_deployed`  
Entries: 21 (18 require the human release, 3 are staging-only)

Nothing in this proposal has been applied. All seven gates are closed.

## Candidate lineage

- parent: `integration-staging/runtime/b05-rehearsal-2026-10-07/candidates/b05-adapters-v1/B05_CANDIDATE_MANIFEST.json` (sha256 `c4341576bf1a`)
- parent tree: 190 files, sha256 `d38a124e8595`
- candidate tree: 208 files, sha256 `ffe774db608f`
- B06 adds 17 frontend files and rewrites 3 carried modules relative to the parent (the frontend payload plus the discovery/view rewrites; everything else is a byte-identical carry of B05)
- A14 merge map byte-unchanged: `True`; B01 merge map sha256 (observation): `1f20f89ce403`

## Digest and cross-reference checks

| Check | Result |
| --- | --- |
| candidate tree re-verified from disk | `True` |
| parent tree re-verified from disk | `True` |
| matches B05 merge proposal's derived_from | `True` |
| edited files match the tooling sources | `True` |
| new files vs parent exactly the seventeen frontend files | `True` |
| only the three edited files changed vs parent | `True` |
| frontend staged bytes match sources (15) | `True` |
| frontend provenance records match (13) | `True` |
| new frontend files match sources (2) | `True` |
| frontend entries match the frozen B01 records | `True` |
| B05/R0104/A14 supersession chains | `True` |

## Action-level gate model

A gate is required only for the action that performs that effect.
A private-preparation pass never satisfies an original-action prerequisite.

| Action | Gate required |
| --- | --- |
| private preparation (read, stage, copy, offline validate) | none |
| write into the original project | `original_paths_released` |
| real data write | `real_data_write_authorized` |
| existing service cutover | `existing_service_cutover_authorized` |
| upstream request | `upstream_requests_authorized` |
| CIE resume | `cie_resume_authorized` |
| remote deployment | `remote_deployment_authorized` |
| original cleanup | `original_cleanup_authorized` |

## Entries

| id | change | staged path | proposed target | after | gates |
| --- | --- | --- | --- | --- | --- |
| BP-0001 | candidate_container | `integration-staging/runtime/b06-rehearsal-2026-10-07/candidates/b06-frontend-v1` | `(staging only)` | ffe774db608f | none |
| BP-0002 | rewrite_integration_app_for_frontend_discovery | `integration-staging/runtime/b06-rehearsal-2026-10-07/candidates/b06-frontend-v1/src/examdata/integration/api/app.py` | `examdata/src/examdata/integration/api/app.py` | 0edb0911aee8 | original_paths_released |
| BP-0003 | rewrite_integration_dataset_for_frontend_query_semantics | `integration-staging/runtime/b06-rehearsal-2026-10-07/candidates/b06-frontend-v1/src/examdata/integration/api/dataset.py` | `examdata/src/examdata/integration/api/dataset.py` | d0edabc7a258 | original_paths_released |
| BP-0004 | rewrite_integration_view_for_the_resources_wiring | `integration-staging/runtime/b06-rehearsal-2026-10-07/candidates/b06-frontend-v1/src/examdata/integration/api/view.py` | `examdata/src/examdata/integration/api/view.py` | f03e549f5be4 | original_paths_released |
| BP-0005 | keep_frontend_provenance_staging_only | `integration-staging/runtime/b06-rehearsal-2026-10-07/candidates/b06-frontend-v1/frontend/PROVENANCE.json` | `(staging only)` | bc7d167bc141 | none |
| BP-0006 | reconcile_frontend_readme | `integration-staging/runtime/b06-rehearsal-2026-10-07/candidates/b06-frontend-v1/frontend/README.md` | `frontend/README.md` | 53764be9870a | original_paths_released |
| BP-0007 | reconcile_frontend_app_js | `integration-staging/runtime/b06-rehearsal-2026-10-07/candidates/b06-frontend-v1/frontend/app.js` | `frontend/app.js` | 66f698449334 | original_paths_released |
| BP-0008 | install_frontend_client_mjs | `integration-staging/runtime/b06-rehearsal-2026-10-07/candidates/b06-frontend-v1/frontend/client.mjs` | `frontend/client.mjs` | 57c55e43da46 | original_paths_released |
| BP-0009 | install_frontend_fixture_server | `integration-staging/runtime/b06-rehearsal-2026-10-07/candidates/b06-frontend-v1/frontend/fixture-server.mjs` | `frontend/fixture-server.mjs` | 424b404d25b4 | original_paths_released |
| BP-0010 | keep_frontend_fixtures_provenance_staging_only | `integration-staging/runtime/b06-rehearsal-2026-10-07/candidates/b06-frontend-v1/frontend/fixtures/PROVENANCE.json` | `(staging only)` | 2a42aa1f095e | none |
| BP-0011 | install_frontend_fixtures_catalog | `integration-staging/runtime/b06-rehearsal-2026-10-07/candidates/b06-frontend-v1/frontend/fixtures/catalog.json` | `frontend/fixtures/catalog.json` | 6344f4f2ef64 | original_paths_released |
| BP-0012 | install_frontend_fixtures_resources | `integration-staging/runtime/b06-rehearsal-2026-10-07/candidates/b06-frontend-v1/frontend/fixtures/resources.json` | `frontend/fixtures/resources.json` | 12277f5ff5ef | original_paths_released |
| BP-0013 | install_frontend_fixtures_syllabi | `integration-staging/runtime/b06-rehearsal-2026-10-07/candidates/b06-frontend-v1/frontend/fixtures/syllabi.json` | `frontend/fixtures/syllabi.json` | 080d0de3838a | original_paths_released |
| BP-0014 | reconcile_frontend_index_html | `integration-staging/runtime/b06-rehearsal-2026-10-07/candidates/b06-frontend-v1/frontend/index.html` | `frontend/index.html` | c2bf9f4e32ad | original_paths_released |
| BP-0015 | verify_frontend_search_mjs | `integration-staging/runtime/b06-rehearsal-2026-10-07/candidates/b06-frontend-v1/frontend/search.mjs` | `frontend/search.mjs` | 6d45a67f794d | original_paths_released |
| BP-0016 | verify_frontend_styles_css | `integration-staging/runtime/b06-rehearsal-2026-10-07/candidates/b06-frontend-v1/frontend/styles.css` | `frontend/styles.css` | 0d33007e8bea | original_paths_released |
| BP-0017 | install_frontend_tests_client | `integration-staging/runtime/b06-rehearsal-2026-10-07/candidates/b06-frontend-v1/frontend/tests/client.test.mjs` | `frontend/tests/client.test.mjs` | 6c23e46e86af | original_paths_released |
| BP-0018 | install_frontend_tests_flow | `integration-staging/runtime/b06-rehearsal-2026-10-07/candidates/b06-frontend-v1/frontend/tests/flow.test.mjs` | `frontend/tests/flow.test.mjs` | c10ad67c8aca | original_paths_released |
| BP-0019 | reconcile_frontend_tests_search | `integration-staging/runtime/b06-rehearsal-2026-10-07/candidates/b06-frontend-v1/frontend/tests/search.test.mjs` | `frontend/tests/search.test.mjs` | 7fd00040fe00 | original_paths_released |
| BP-0020 | rewrite_frontend_server_for_the_v2_switch | `integration-staging/runtime/b06-rehearsal-2026-10-07/candidates/b06-frontend-v1/frontend/server.mjs` | `frontend/server.mjs` | 3b34f04c9192 | original_paths_released |
| BP-0021 | install_frontend_tests_server | `integration-staging/runtime/b06-rehearsal-2026-10-07/candidates/b06-frontend-v1/frontend/tests/server.test.mjs` | `frontend/tests/server.test.mjs` | 75e3c7a145ec | original_paths_released |

## Requirements before merge

- explicit human release opening original_paths_released with an explicit scope; the records carried from B01 (deferred_pending_release / carried_pending_release) become actionable only under that release
- apply the three release-required module entries (add_file semantics; the whole integration package is new relative to the original project): install the B06 bytes at examdata/src/examdata/integration/api/app.py (superseding the unapplied B05 proposal BP-0004), examdata/src/examdata/integration/api/dataset.py (superseding R0104 RP-0005 and the unapplied B05 BP-0003) and examdata/src/examdata/integration/api/view.py (superseding A14 MM-0022, whose bytes the B06 parent carried unchanged)
- install the fifteen release-required frontend entries with the B06 candidate bytes: thirteen from B01_MERGE_MAP.json (MM-0229..MM-0241; reconcile_modify for app.js, index.html, README.md and tests/search.test.mjs; verify_copy for search.mjs and styles.css - write nothing if the bytes already match), frontend/server.mjs (the B01 planned original edit) and frontend/tests/server.test.mjs (new); the two PROVENANCE entries stay staging-only and are never installed
- re-verify every recorded base before writing (B01 base sha256_recorded for the frontend entries, observed 2026-10-06T10:17:44+08:00; server.mjs base_sha256 observed 2026-10-06T11:43:31+08:00); abort the affected entry if any base drifted
- for the reconcile_modify entries, perform the three-way semantic reconciliation against the released original tree that B01 deferred (three_way=false, gate was closed) before writing
- the merged static server must keep tests/ and fixtures/ out of the static surface (B01 MM-0232 note; covered by frontend/tests/server.test.mjs) and its production port strategy needs an explicit human decision (the staged server defaults to an ephemeral port and refuses 5188/8000 as a staging safety measure)
- verify the candidate tree digest (the container entry's staged_sha256_after, recomputed with the recorded rule) immediately before any original write
- re-run the isolated staged suite against the frozen B06 candidate before any original write, and re-run the B06 route probe plus the suite against the merged tree afterwards
