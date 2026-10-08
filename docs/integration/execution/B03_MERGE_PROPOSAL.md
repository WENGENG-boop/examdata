# B03 merge proposal (private rehearsal only)

Generated: 2026-10-07T00:35:39+08:00  
Status: `proposal_only_nothing_merged_not_deployed`  
Entries: 1 (0 require the human release, 1 are staging-only)

Nothing in this proposal has been applied. All seven gates are closed.

## Candidate lineage

- parent: `integration-staging/runtime/b02-rehearsal-20261006/candidates/b02-shared-config-v1/B02_CANDIDATE_MANIFEST.json` (sha256 `59dfc8c79b59`)
- parent tree: 185 files, sha256 `463628cff11e`
- candidate tree: 186 files, sha256 `bb7454363186`
- B03 adds 0 new files relative to the parent (byte-identical carry; the candidate digest covers the carried B02 manifest, which B02's own digest excluded)
- A14 merge map byte-unchanged: `True`

## Digest and cross-reference checks

| Check | Result |
| --- | --- |
| candidate tree re-verified from disk | `True` |
| parent tree re-verified from disk | `True` |
| matches B02 merge proposal's derived_from | `True` |

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
| BP-0001 | candidate_container | `integration-staging/runtime/b03-rehearsal-2026-10-07/candidates/b03-contracts-catalog-v1` | `(staging only)` | bb7454363186 | none |

## Requirements before merge

- explicit human release opening original_paths_released with an explicit scope
- no B03-specific original action: B03 adds zero files, so the original-facing payload remains R0104_MERGE_PROPOSAL.json (R04 payload) plus B02_MERGE_PROPOSAL.json (shared-config packaging)
- re-run the isolated staged suite against the frozen B03 candidate before any original write
- verify the candidate tree digest (staged_sha256_after, recomputed with the recorded rule) immediately before any original write
