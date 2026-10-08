# B04 rollback proposal (private rehearsal only)

Generated: 2026-10-07T01:40:30+08:00  
Status: `proposal_only_nothing_merged_not_deployed`  
Entries: 3 (staging level: 1 tree delete, 1 file delete; original level: 1 delete, 1 restore base, 1 no original action)

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
- never touch the frozen B03 candidate under b03-rehearsal-2026-10-07/candidates/**
- never restore the live execution ledger from a private copy

## Entries

| id | staged path | kind | sha256 at proposal | reversal |
| --- | --- | --- | --- | --- |
| BP-0001 | `integration-staging/runtime/b04-rehearsal-2026-10-07/candidates/b04-routes-v1` | staging_candidate_tree | fd806f4c6116 | delete the candidate tree, and only if its current tree digest still equals staged_sha256_after |
| BP-0002 | `integration-staging/runtime/b04-rehearsal-2026-10-07/candidates/b04-routes-v1/src/examdata/integration/api/compose.py` | new_file | e220c007dba8 | delete_file at the proposed target, and only if the target's current sha256 still equals staged_sha256_after |
| BP-0003 | `(no staged file)` | planned_edit | (no staged bytes) | restore the recorded base bytes (hash above) |
