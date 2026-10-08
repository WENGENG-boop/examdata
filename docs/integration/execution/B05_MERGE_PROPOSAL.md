# B05 merge proposal (private rehearsal only)

Generated: 2026-10-07T02:44:33+08:00  
Status: `proposal_only_nothing_merged_not_deployed`  
Entries: 4 (3 require the human release, 1 are staging-only)

Nothing in this proposal has been applied. All seven gates are closed.

## Candidate lineage

- parent: `integration-staging/runtime/b04-rehearsal-2026-10-07/candidates/b04-routes-v1/B04_CANDIDATE_MANIFEST.json` (sha256 `99177c1239c6`)
- parent tree: 188 files, sha256 `fd806f4c6116`
- candidate tree: 190 files, sha256 `d38a124e8595`
- B05 adds 1 new file and rewrites 2 carried modules relative to the parent (the active-owner seam; everything else is a byte-identical carry of B04)
- A14 merge map byte-unchanged: `True`

## Digest and cross-reference checks

| Check | Result |
| --- | --- |
| candidate tree re-verified from disk | `True` |
| parent tree re-verified from disk | `True` |
| matches B04 merge proposal's derived_from | `True` |
| new module matches the tooling source | `True` |
| edited files match the tooling sources | `True` |
| new files vs parent exactly the seam module | `True` |
| only the two edited files changed vs parent | `True` |
| A14/R0104 supersession chains | `True` |

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
| BP-0001 | candidate_container | `integration-staging/runtime/b05-rehearsal-2026-10-07/candidates/b05-adapters-v1` | `(staging only)` | d38a124e8595 | none |
| BP-0002 | new_module_active_owner_seam | `integration-staging/runtime/b05-rehearsal-2026-10-07/candidates/b05-adapters-v1/src/examdata/integration/adapters/active_owner.py` | `examdata/src/examdata/integration/adapters/active_owner.py` | 0d8116f0f962 | original_paths_released |
| BP-0003 | rewrite_integration_dataset_for_the_seam | `integration-staging/runtime/b05-rehearsal-2026-10-07/candidates/b05-adapters-v1/src/examdata/integration/api/dataset.py` | `examdata/src/examdata/integration/api/dataset.py` | a9a72a7a56f8 | original_paths_released |
| BP-0004 | rewrite_integration_app_for_the_seam | `integration-staging/runtime/b05-rehearsal-2026-10-07/candidates/b05-adapters-v1/src/examdata/integration/api/app.py` | `examdata/src/examdata/integration/api/app.py` | aa3ba9c5e7da | original_paths_released |

## Requirements before merge

- explicit human release opening original_paths_released with an explicit scope
- apply the three release-required entries: add examdata/src/examdata/integration/adapters/active_owner.py, install the B05 bytes at examdata/src/examdata/integration/api/dataset.py (superseding R0104 RP-0005) and at examdata/src/examdata/integration/api/app.py (superseding A14 MM-0015); every entry is add_file semantics because the integration package is new relative to the original project
- verify the candidate tree digest (the container entry's staged_sha256_after, recomputed with the recorded rule) immediately before any original write
- apply the B04-proposed composition hook and the shared-application registration of the staged v2 routes per B04_MERGE_PROPOSAL.json (not re-proposed here)
- re-run the isolated staged suite against the frozen B05 candidate before any original write, and re-run the B05 route probe plus the suite against the merged tree afterwards
