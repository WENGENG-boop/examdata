# B03 rollback proposal (private rehearsal only)

Generated: 2026-10-07T00:35:39+08:00  
Status: `proposal_only_nothing_merged_not_deployed`  
Entries: 1 (staging level: 1 tree delete, 0 file delete; original level: 0 delete, 1 no original action)

Nothing has been merged, so nothing is currently pending rollback. This file states how each change would be reversed.

## Guards

- verify the resolved absolute path and its sha256 (or tree digest) before any delete
- no delete ever targets a protected original in Phase B private rehearsal
- planned original edits are reversible only after the human release
- all seven gates remain closed during rollback

## Never

- never touch docs/integration/execution/evidence/**
- never touch integration-staging/runtime/phase-b/** sealed transcripts
- never touch the frozen R04 candidate under r0104-repair-20261006/candidates/**
- never touch the frozen B02 candidate under b02-rehearsal-20261006/candidates/**
- never restore the live execution ledger from a private copy

## Entries

| id | staged path | kind | sha256 at proposal | reversal |
| --- | --- | --- | --- | --- |
| BP-0001 | `integration-staging/runtime/b03-rehearsal-2026-10-07/candidates/b03-contracts-catalog-v1` | staging_candidate_tree | bb7454363186 | delete the candidate tree, and only if its current tree digest still equals staged_sha256_after |
