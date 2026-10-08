# B02 rollback proposal (private rehearsal only)

Generated: 2026-10-06T23:50:55+08:00  
Status: `proposal_only_nothing_merged_not_deployed`  
Entries: 4 (staging level: 1 tree delete, 3 file delete; original level: 2 delete, 2 no original action)

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
- never restore the live execution ledger from a private copy

## Entries

| id | staged path | kind | sha256 at proposal | reversal |
| --- | --- | --- | --- | --- |
| BP-0001 | `integration-staging/runtime/b02-rehearsal-20261006/candidates/b02-shared-config-v1` | staging_candidate_tree | 463628cff11e | delete the candidate tree, and only if its current tree digest still equals staged_sha256_after |
| BP-0002 | `integration-staging/config/README.md` | new_file | 2beeb31ed252 | no reversal needed: the file never leaves integration-staging/ |
| BP-0003 | `integration-staging/config/staging-config.example.json` | new_file | 0c6786641664 | delete_file at examdata/config.example.json, and only if the target's current sha256 still equals staged_sha256_after |
| BP-0004 | `integration-staging/config/staging.env.example` | new_file | d16bdbfb14f6 | delete_file at examdata/.env.example, and only if the target's current sha256 still equals staged_sha256_after |
