# B07 rollback proposal (private rehearsal only)

Generated: 2026-10-07T07:15:00+08:00  
Status: `proposal_only_nothing_merged_not_deployed`  
Entries: 15 (staging level: 1 tree delete, 14 removed with the tree, 2 restorable to parent bytes; original level: 14 target delete, 0 restore base, 0 reconciliation cases, 1 no original action)

Nothing has been merged, so nothing is currently pending rollback. This file states how each change would be reversed.

## Guards

- verify the resolved absolute path and its sha256 (or tree digest) before any delete
- no delete ever targets a protected original in Phase B private rehearsal
- planned original writes are reversible only after the human release
- the two rewritten integration modules never existed in the original project; their original-level reversal is a delete, never a restore of the superseded staged versions
- no B07 entry restores base bytes or reconciles: every release-required B07 change is an add whose reversal is a guarded delete_file
- the eighteen release-required B06 entries keep the reversal semantics recorded in B06_ROLLBACK_PROPOSAL.json
- all seven gates remain closed during rollback

## Never

- never touch docs/integration/execution/evidence/**
- never touch integration-staging/runtime/phase-b/** sealed transcripts
- never touch the frozen R04 candidate under r0104-repair-20261006/candidates/**
- never touch the frozen B02 candidate under b02-rehearsal-20261006/candidates/**
- never touch the frozen B03 candidate under b03-rehearsal-2026-10-07/candidates/b03-contracts-catalog-v1/**
- never touch the frozen B04 candidate under b04-rehearsal-2026-10-07/candidates/b04-routes-v1/**
- never touch the frozen B05 candidate under b05-rehearsal-2026-10-07/candidates/b05-adapters-v1/**
- never touch the frozen B06 candidate under b06-rehearsal-2026-10-07/candidates/b06-frontend-v1/**
- never restore the live execution ledger from a private copy

## Entries

| id | staged path | kind | sha256 at proposal | reversal |
| --- | --- | --- | --- | --- |
| BP-0001 | `integration-staging/runtime/b07-rehearsal-2026-10-07/candidates/b07-operations-v1` | staging_candidate_tree | 5df259843b26 | delete the candidate tree, and only if its current tree digest still equals sha256_at_proposal |
| BP-0002 | `integration-staging/runtime/b07-rehearsal-2026-10-07/candidates/b07-operations-v1/src/examdata/integration/api/app.py` | staged_file_rewrite | 81f9c3c9700b | restore the parent's staged bytes (staging_sha256_to_restore) inside the candidate; the candidate itself stays private |
| BP-0003 | `integration-staging/runtime/b07-rehearsal-2026-10-07/candidates/b07-operations-v1/src/examdata/integration/api/dataset.py` | staged_file_rewrite | c0d0d06cdcb2 | restore the parent's staged bytes (staging_sha256_to_restore) inside the candidate; the candidate itself stays private |
| BP-0004 | `integration-staging/runtime/b07-rehearsal-2026-10-07/candidates/b07-operations-v1/src/examdata/integration/operations/jobs.py` | new_file | 916ae7b19590 | remove the staged file; it does not exist in the parent candidate, so the candidate then differs from its recorded digest and is rebuilt from the parent if needed |
| BP-0005 | `integration-staging/runtime/b07-rehearsal-2026-10-07/candidates/b07-operations-v1/src/examdata/integration/operations/published.py` | new_file | 54522b9e669c | remove the staged file; it does not exist in the parent candidate, so the candidate then differs from its recorded digest and is rebuilt from the parent if needed |
| BP-0006 | `integration-staging/runtime/b07-rehearsal-2026-10-07/candidates/b07-operations-v1/fixtures/synthetic/operations/operations-root/PROVENANCE.json` | new_file | f83617cc0a30 | remove the staged file; it does not exist in the parent candidate, so the candidate then differs from its recorded digest and is rebuilt from the parent if needed |
| BP-0007 | `integration-staging/runtime/b07-rehearsal-2026-10-07/candidates/b07-operations-v1/fixtures/synthetic/operations/operations-root/README.md` | new_file | 247eec4e48ff | remove the staged file; it does not exist in the parent candidate, so the candidate then differs from its recorded digest and is rebuilt from the parent if needed |
| BP-0008 | `integration-staging/runtime/b07-rehearsal-2026-10-07/candidates/b07-operations-v1/fixtures/synthetic/operations/operations-root/cie-batch-8888-stale/checkpoint.json` | new_file | 76559fb8ca48 | remove the staged file; it does not exist in the parent candidate, so the candidate then differs from its recorded digest and is rebuilt from the parent if needed |
| BP-0009 | `integration-staging/runtime/b07-rehearsal-2026-10-07/candidates/b07-operations-v1/fixtures/synthetic/operations/operations-root/cie-batch-8888/checkpoint.json` | new_file | c31696a05ce9 | remove the staged file; it does not exist in the parent candidate, so the candidate then differs from its recorded digest and is rebuilt from the parent if needed |
| BP-0010 | `integration-staging/runtime/b07-rehearsal-2026-10-07/candidates/b07-operations-v1/fixtures/synthetic/operations/operations-root/cie-location-batch/checkpoint.json` | new_file | 9eb281a2a56d | remove the staged file; it does not exist in the parent candidate, so the candidate then differs from its recorded digest and is rebuilt from the parent if needed |
| BP-0011 | `integration-staging/runtime/b07-rehearsal-2026-10-07/candidates/b07-operations-v1/fixtures/synthetic/operations/operations-root/expected-manifest.json` | new_file | 6f86b0211c5b | remove the staged file; it does not exist in the parent candidate, so the candidate then differs from its recorded digest and is rebuilt from the parent if needed |
| BP-0012 | `integration-staging/runtime/b07-rehearsal-2026-10-07/candidates/b07-operations-v1/fixtures/synthetic/operations/operations-root/run-ok-stale/checkpoint.json` | new_file | 3519a84fd24f | remove the staged file; it does not exist in the parent candidate, so the candidate then differs from its recorded digest and is rebuilt from the parent if needed |
| BP-0013 | `integration-staging/runtime/b07-rehearsal-2026-10-07/candidates/b07-operations-v1/fixtures/synthetic/operations/operations-root/run-ok/checkpoint.json` | new_file | fa0a85c5c2df | remove the staged file; it does not exist in the parent candidate, so the candidate then differs from its recorded digest and is rebuilt from the parent if needed |
| BP-0014 | `integration-staging/runtime/b07-rehearsal-2026-10-07/candidates/b07-operations-v1/fixtures/synthetic/operations/operations-root/run-partial/checkpoint.json` | new_file | 017274373100 | remove the staged file; it does not exist in the parent candidate, so the candidate then differs from its recorded digest and is rebuilt from the parent if needed |
| BP-0015 | `integration-staging/runtime/b07-rehearsal-2026-10-07/candidates/b07-operations-v1/fixtures/synthetic/operations/operations-root/unsupported/checkpoint.json` | new_file | 410b6ac73370 | remove the staged file; it does not exist in the parent candidate, so the candidate then differs from its recorded digest and is rebuilt from the parent if needed |
