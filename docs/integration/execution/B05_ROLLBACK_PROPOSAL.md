# B05 rollback proposal (private rehearsal only)

Generated: 2026-10-07T02:44:33+08:00  
Status: `proposal_only_nothing_merged_not_deployed`  
Entries: 4 (staging level: 1 tree delete, 3 removed with the tree; original level: 3 target delete, 0 restore base, 1 no original action)

Nothing has been merged, so nothing is currently pending rollback. This file states how each change would be reversed.

## Guards

- verify the resolved absolute path and its sha256 (or tree digest) before any delete
- no delete ever targets a protected original in Phase B private rehearsal
- planned original writes are reversible only after the human release
- the two rewritten targets never existed in the original project; their original-level reversal is a delete, never a restore of the superseded staged versions
- all seven gates remain closed during rollback

## Never

- never touch docs/integration/execution/evidence/**
- never touch integration-staging/runtime/phase-b/** sealed transcripts
- never touch the frozen R04 candidate under r0104-repair-20261006/candidates/**
- never touch the frozen B02 candidate under b02-rehearsal-20261006/candidates/**
- never touch the frozen B03 candidate under b03-rehearsal-2026-10-07/candidates/**
- never touch the frozen B04 candidate under b04-rehearsal-2026-10-07/candidates/**
- never restore the live execution ledger from a private copy

## Entries

| id | staged path | kind | sha256 at proposal | reversal |
| --- | --- | --- | --- | --- |
| BP-0001 | `integration-staging/runtime/b05-rehearsal-2026-10-07/candidates/b05-adapters-v1` | staging_candidate_tree | d38a124e8595 | delete the candidate tree, and only if its current tree digest still equals sha256_at_proposal |
| BP-0002 | `integration-staging/runtime/b05-rehearsal-2026-10-07/candidates/b05-adapters-v1/src/examdata/integration/adapters/active_owner.py` | new_file | 0d8116f0f962 | remove the staged file; the candidate then differs from its recorded digest and is rebuilt from the parent if needed |
| BP-0003 | `integration-staging/runtime/b05-rehearsal-2026-10-07/candidates/b05-adapters-v1/src/examdata/integration/api/dataset.py` | staged_file_rewrite | a9a72a7a56f8 | restore the parent's staged bytes (sha256_to_restore) inside the candidate; the candidate itself stays private |
| BP-0004 | `integration-staging/runtime/b05-rehearsal-2026-10-07/candidates/b05-adapters-v1/src/examdata/integration/api/app.py` | staged_file_rewrite | aa3ba9c5e7da | restore the parent's staged bytes (sha256_to_restore) inside the candidate; the candidate itself stays private |
