# B07 merge proposal (private rehearsal only)

Generated: 2026-10-07T07:15:00+08:00  
Status: `proposal_only_nothing_merged_not_deployed`  
Entries: 15 (14 require the human release, 1 are staging-only)

Nothing in this proposal has been applied. All seven gates are closed.

## Candidate lineage

- parent: `integration-staging/runtime/b06-rehearsal-2026-10-07/candidates/b06-frontend-v1/B06_CANDIDATE_MANIFEST.json` (sha256 `9af2e8495730`)
- parent tree: 208 files, sha256 `ffe774db608f`
- candidate tree: 221 files, sha256 `5df259843b26`
- B07 adds 12 operations files and rewrites 2 carried modules relative to the parent (the operations payload plus the coverage/jobs wiring; everything else is a byte-identical carry of B06)
- A14 merge map byte-unchanged: `True`; B01 merge map sha256 (observation): `1f20f89ce403`

## Digest and cross-reference checks

| Check | Result |
| --- | --- |
| candidate tree re-verified from disk | `True` |
| parent tree re-verified from disk | `True` |
| matches B06 merge proposal's derived_from | `True` |
| edited files match the tooling sources | `True` |
| new files vs parent exactly the twelve operations files | `True` |
| only the two edited files changed vs parent | `True` |
| new operations modules match sources (2) | `True` |
| operations fixture files match sources (10) | `True` |
| operations provenance records match (9) | `True` |
| operations target conventions match the B01 records | `True` |
| A14/B05/B06 supersession chains | `True` |

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
| BP-0001 | candidate_container | `integration-staging/runtime/b07-rehearsal-2026-10-07/candidates/b07-operations-v1` | `(staging only)` | 5df259843b26 | none |
| BP-0002 | rewrite_integration_app_for_operations_routes_and_diagnostics | `integration-staging/runtime/b07-rehearsal-2026-10-07/candidates/b07-operations-v1/src/examdata/integration/api/app.py` | `examdata/src/examdata/integration/api/app.py` | 81f9c3c9700b | original_paths_released |
| BP-0003 | rewrite_integration_dataset_for_operations_projections | `integration-staging/runtime/b07-rehearsal-2026-10-07/candidates/b07-operations-v1/src/examdata/integration/api/dataset.py` | `examdata/src/examdata/integration/api/dataset.py` | c0d0d06cdcb2 | original_paths_released |
| BP-0004 | add_operations_jobs_module_read_only_views | `integration-staging/runtime/b07-rehearsal-2026-10-07/candidates/b07-operations-v1/src/examdata/integration/operations/jobs.py` | `examdata/src/examdata/integration/operations/jobs.py` | 916ae7b19590 | original_paths_released |
| BP-0005 | add_operations_published_module_sanitized_projections | `integration-staging/runtime/b07-rehearsal-2026-10-07/candidates/b07-operations-v1/src/examdata/integration/operations/published.py` | `examdata/src/examdata/integration/operations/published.py` | 54522b9e669c | original_paths_released |
| BP-0006 | install_operations_root_fixture_provenance | `integration-staging/runtime/b07-rehearsal-2026-10-07/candidates/b07-operations-v1/fixtures/synthetic/operations/operations-root/PROVENANCE.json` | `examdata/tests/integration/fixtures/synthetic/operations/operations-root/PROVENANCE.json` | f83617cc0a30 | original_paths_released |
| BP-0007 | install_operations_root_readme | `integration-staging/runtime/b07-rehearsal-2026-10-07/candidates/b07-operations-v1/fixtures/synthetic/operations/operations-root/README.md` | `examdata/tests/integration/fixtures/synthetic/operations/operations-root/README.md` | 247eec4e48ff | original_paths_released |
| BP-0008 | install_operations_root_checkpoint_cie_batch_8888_stale | `integration-staging/runtime/b07-rehearsal-2026-10-07/candidates/b07-operations-v1/fixtures/synthetic/operations/operations-root/cie-batch-8888-stale/checkpoint.json` | `examdata/tests/integration/fixtures/synthetic/operations/operations-root/cie-batch-8888-stale/checkpoint.json` | 76559fb8ca48 | original_paths_released |
| BP-0009 | install_operations_root_checkpoint_cie_batch_8888 | `integration-staging/runtime/b07-rehearsal-2026-10-07/candidates/b07-operations-v1/fixtures/synthetic/operations/operations-root/cie-batch-8888/checkpoint.json` | `examdata/tests/integration/fixtures/synthetic/operations/operations-root/cie-batch-8888/checkpoint.json` | c31696a05ce9 | original_paths_released |
| BP-0010 | install_operations_root_checkpoint_cie_location_batch | `integration-staging/runtime/b07-rehearsal-2026-10-07/candidates/b07-operations-v1/fixtures/synthetic/operations/operations-root/cie-location-batch/checkpoint.json` | `examdata/tests/integration/fixtures/synthetic/operations/operations-root/cie-location-batch/checkpoint.json` | 9eb281a2a56d | original_paths_released |
| BP-0011 | install_operations_root_expected_manifest | `integration-staging/runtime/b07-rehearsal-2026-10-07/candidates/b07-operations-v1/fixtures/synthetic/operations/operations-root/expected-manifest.json` | `examdata/tests/integration/fixtures/synthetic/operations/operations-root/expected-manifest.json` | 6f86b0211c5b | original_paths_released |
| BP-0012 | install_operations_root_checkpoint_run_ok_stale | `integration-staging/runtime/b07-rehearsal-2026-10-07/candidates/b07-operations-v1/fixtures/synthetic/operations/operations-root/run-ok-stale/checkpoint.json` | `examdata/tests/integration/fixtures/synthetic/operations/operations-root/run-ok-stale/checkpoint.json` | 3519a84fd24f | original_paths_released |
| BP-0013 | install_operations_root_checkpoint_run_ok | `integration-staging/runtime/b07-rehearsal-2026-10-07/candidates/b07-operations-v1/fixtures/synthetic/operations/operations-root/run-ok/checkpoint.json` | `examdata/tests/integration/fixtures/synthetic/operations/operations-root/run-ok/checkpoint.json` | fa0a85c5c2df | original_paths_released |
| BP-0014 | install_operations_root_checkpoint_run_partial | `integration-staging/runtime/b07-rehearsal-2026-10-07/candidates/b07-operations-v1/fixtures/synthetic/operations/operations-root/run-partial/checkpoint.json` | `examdata/tests/integration/fixtures/synthetic/operations/operations-root/run-partial/checkpoint.json` | 017274373100 | original_paths_released |
| BP-0015 | install_operations_root_checkpoint_unsupported | `integration-staging/runtime/b07-rehearsal-2026-10-07/candidates/b07-operations-v1/fixtures/synthetic/operations/operations-root/unsupported/checkpoint.json` | `examdata/tests/integration/fixtures/synthetic/operations/operations-root/unsupported/checkpoint.json` | 410b6ac73370 | original_paths_released |

## Requirements before merge

- explicit human release opening original_paths_released with an explicit scope; the records carried from B01 (deferred_pending_release) become actionable only under that release; B07 does not re-propose the eighteen release-required B06 entries - the human release decision covers B06_MERGE_PROPOSAL.json and this B07 delta together, or the affected entries stay deferred
- apply the two release-required module rewrites (add_file semantics; the whole integration package is new relative to the original project): install the B07 bytes at examdata/src/examdata/integration/api/app.py (superseding the unapplied B06 proposal BP-0002) and examdata/src/examdata/integration/api/dataset.py (superseding the unapplied B06 proposal BP-0003)
- install the two new operations modules at examdata/src/examdata/integration/operations/jobs.py and examdata/src/examdata/integration/operations/published.py (the B01 MM-0043..MM-0045 target convention)
- install the ten release-required operations fixtures under examdata/tests/integration/fixtures/synthetic/operations/operations-root/ (the B01 MM-0221..MM-0228 directory mapping extended under the new subtree); the sibling flat fixture files filed by B01 are untouched by this proposal
- re-verify every recorded base before writing and re-verify the candidate tree digest (the container entry's staged_sha256_after, recomputed with the recorded rule) immediately before any original write
- keep the merged operations views read-only (no resume, no restart, no write-back to any operations root) and the public diagnostics sanitized (no raw paths, keys or secrets) after merge
- re-run the isolated staged suite and the B07 route probe against the frozen B07 candidate before any original write, and re-run both against the merged tree afterwards
- the operations-root fixtures are labelled synthetic controls: the merged product must never point a default configuration at a real operations root without the applicable release, and no real credential may be staged or fabricated
