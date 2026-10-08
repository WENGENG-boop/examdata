# B04 merge proposal (private rehearsal only)

Generated: 2026-10-07T01:40:30+08:00  
Status: `proposal_only_nothing_merged_not_deployed`  
Entries: 3 (2 require the human release, 1 are staging-only)

Nothing in this proposal has been applied. All seven gates are closed.

## Candidate lineage

- parent: `integration-staging/runtime/b03-rehearsal-2026-10-07/candidates/b03-contracts-catalog-v1/B03_CANDIDATE_MANIFEST.json` (sha256 `9cf639e53fa4`)
- parent tree: 186 files, sha256 `bb7454363186`
- candidate tree: 188 files, sha256 `fd806f4c6116`
- B04 adds 1 new file relative to the parent (the composition hook; everything else is a byte-identical carry of B03)
- A14 merge map byte-unchanged: `True`

## Digest and cross-reference checks

| Check | Result |
| --- | --- |
| candidate tree re-verified from disk | `True` |
| parent tree re-verified from disk | `True` |
| matches B03 merge proposal's derived_from | `True` |
| new module matches the tooling source | `True` |

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
| BP-0001 | candidate_container | `integration-staging/runtime/b04-rehearsal-2026-10-07/candidates/b04-routes-v1` | `(staging only)` | fd806f4c6116 | none |
| BP-0002 | new_module_composition_hook | `integration-staging/runtime/b04-rehearsal-2026-10-07/candidates/b04-routes-v1/src/examdata/integration/api/compose.py` | `examdata/src/examdata/integration/api/compose.py` | e220c007dba8 | original_paths_released |
| BP-0003 | register_v2_routes_in_shared_app | `(no staged file)` | `examdata/src/examdata/api/app.py` | (deferred; base 753749fac136) | original_paths_released |

## Requirements before merge

- explicit human release opening original_paths_released with an explicit scope
- apply the two release-required entries: add examdata/src/examdata/integration/api/compose.py and edit examdata/src/examdata/api/app.py per the A14 record (register the staged v2 routes without removing or shadowing any legacy route; keep path ordering and operation IDs)
- re-verify the app.py base sha256 against the A14-recorded value immediately before the edit (Phase B never read the original file)
- verify the candidate tree digest (staged_sha256_after, recomputed with the recorded rule) immediately before any original write
- re-run the isolated staged suite against the frozen B04 candidate before any original write, and re-run the B04 route probe plus the suite against the merged tree afterwards
