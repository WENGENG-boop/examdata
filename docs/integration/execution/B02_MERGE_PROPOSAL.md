# B02 merge proposal (private rehearsal only)

Generated: 2026-10-06T23:50:55+08:00  
Status: `proposal_only_nothing_merged_not_deployed`  
Entries: 4 (2 require the human release, 2 are staging-only)

Nothing in this proposal has been applied. All seven gates are closed.

## Candidate lineage

- parent: `integration-staging/runtime/r0104-repair-20261006/candidates/r04-target-layout-v2/R04_CANDIDATE_MANIFEST.json` (sha256 `923e7a298179`)
- parent tree: 182 files, sha256 `c84973e0072f`
- candidate tree: 185 files, sha256 `463628cff11e`
- A14 merge map byte-unchanged: `True`

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
| BP-0001 | candidate_container | `integration-staging/runtime/b02-rehearsal-20261006/candidates/b02-shared-config-v1` | `(staging only)` | 463628cff11e | none |
| BP-0002 | shared_config_packaging | `integration-staging/config/README.md` | `(staging only)` | 2beeb31ed252 | none |
| BP-0003 | shared_config_packaging | `integration-staging/config/staging-config.example.json` | `examdata/config.example.json` | 0c6786641664 | original_paths_released |
| BP-0004 | shared_config_packaging | `integration-staging/config/staging.env.example` | `examdata/.env.example` | d16bdbfb14f6 | original_paths_released |

## Requirements before merge

- explicit human release opening original_paths_released with an explicit scope
- re-run the isolated staged suite against the frozen B02 candidate
- verify each proposed target's sha256 before and after the add_file
