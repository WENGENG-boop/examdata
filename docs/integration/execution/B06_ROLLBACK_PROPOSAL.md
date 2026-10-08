# B06 rollback proposal (private rehearsal only)

Generated: 2026-10-07T05:02:05+08:00  
Status: `proposal_only_nothing_merged_not_deployed`  
Entries: 21 (staging level: 1 tree delete, 20 removed with the tree, 3 restorable to parent bytes; original level: 11 target delete, 6 restore base, 1 reconciliation cases, 3 no original action)

Nothing has been merged, so nothing is currently pending rollback. This file states how each change would be reversed.

## Guards

- verify the resolved absolute path and its sha256 (or tree digest) before any delete
- no delete ever targets a protected original in Phase B private rehearsal
- planned original writes are reversible only after the human release
- the three rewritten integration modules never existed in the original project; their original-level reversal is a delete, never a restore of the superseded staged versions
- the base restores (app.js, index.html, README.md, search.mjs, styles.css, server.mjs) restore only the sha256 recorded by B01 (frozen records) and abort if the target drifted from sha256_at_proposal
- all seven gates remain closed during rollback

## Never

- never touch docs/integration/execution/evidence/**
- never touch integration-staging/runtime/phase-b/** sealed transcripts
- never touch the frozen R04 candidate under r0104-repair-20261006/candidates/**
- never touch the frozen B02 candidate under b02-rehearsal-20261006/candidates/**
- never touch the frozen B03 candidate under b03-rehearsal-2026-10-07/candidates/b03-contracts-catalog-v1/**
- never touch the frozen B04 candidate under b04-rehearsal-2026-10-07/candidates/b04-routes-v1/**
- never touch the frozen B05 candidate under b05-rehearsal-2026-10-07/candidates/b05-adapters-v1/**
- never restore the live execution ledger from a private copy

## Entries

| id | staged path | kind | sha256 at proposal | reversal |
| --- | --- | --- | --- | --- |
| BP-0001 | `integration-staging/runtime/b06-rehearsal-2026-10-07/candidates/b06-frontend-v1` | staging_candidate_tree | ffe774db608f | delete the candidate tree, and only if its current tree digest still equals sha256_at_proposal |
| BP-0002 | `integration-staging/runtime/b06-rehearsal-2026-10-07/candidates/b06-frontend-v1/src/examdata/integration/api/app.py` | staged_file_rewrite | 0edb0911aee8 | restore the parent's staged bytes (staging_sha256_to_restore) inside the candidate; the candidate itself stays private |
| BP-0003 | `integration-staging/runtime/b06-rehearsal-2026-10-07/candidates/b06-frontend-v1/src/examdata/integration/api/dataset.py` | staged_file_rewrite | d0edabc7a258 | restore the parent's staged bytes (staging_sha256_to_restore) inside the candidate; the candidate itself stays private |
| BP-0004 | `integration-staging/runtime/b06-rehearsal-2026-10-07/candidates/b06-frontend-v1/src/examdata/integration/api/view.py` | staged_file_rewrite | f03e549f5be4 | restore the parent's staged bytes (staging_sha256_to_restore) inside the candidate; the candidate itself stays private |
| BP-0005 | `integration-staging/runtime/b06-rehearsal-2026-10-07/candidates/b06-frontend-v1/frontend/PROVENANCE.json` | staging_only_artifact | bc7d167bc141 | removed only with the candidate tree; the file has no separate staging reversal |
| BP-0006 | `integration-staging/runtime/b06-rehearsal-2026-10-07/candidates/b06-frontend-v1/frontend/README.md` | modified_copy | 53764be9870a | remove the staged file; it does not exist in the parent candidate, so the candidate then differs from its recorded digest and is rebuilt from the parent if needed |
| BP-0007 | `integration-staging/runtime/b06-rehearsal-2026-10-07/candidates/b06-frontend-v1/frontend/app.js` | modified_copy | 66f698449334 | remove the staged file; it does not exist in the parent candidate, so the candidate then differs from its recorded digest and is rebuilt from the parent if needed |
| BP-0008 | `integration-staging/runtime/b06-rehearsal-2026-10-07/candidates/b06-frontend-v1/frontend/client.mjs` | new_file | 57c55e43da46 | remove the staged file; it does not exist in the parent candidate, so the candidate then differs from its recorded digest and is rebuilt from the parent if needed |
| BP-0009 | `integration-staging/runtime/b06-rehearsal-2026-10-07/candidates/b06-frontend-v1/frontend/fixture-server.mjs` | new_file | 424b404d25b4 | remove the staged file; it does not exist in the parent candidate, so the candidate then differs from its recorded digest and is rebuilt from the parent if needed |
| BP-0010 | `integration-staging/runtime/b06-rehearsal-2026-10-07/candidates/b06-frontend-v1/frontend/fixtures/PROVENANCE.json` | staging_only_artifact | 2a42aa1f095e | removed only with the candidate tree; the file has no separate staging reversal |
| BP-0011 | `integration-staging/runtime/b06-rehearsal-2026-10-07/candidates/b06-frontend-v1/frontend/fixtures/catalog.json` | new_file | 6344f4f2ef64 | remove the staged file; it does not exist in the parent candidate, so the candidate then differs from its recorded digest and is rebuilt from the parent if needed |
| BP-0012 | `integration-staging/runtime/b06-rehearsal-2026-10-07/candidates/b06-frontend-v1/frontend/fixtures/resources.json` | new_file | 12277f5ff5ef | remove the staged file; it does not exist in the parent candidate, so the candidate then differs from its recorded digest and is rebuilt from the parent if needed |
| BP-0013 | `integration-staging/runtime/b06-rehearsal-2026-10-07/candidates/b06-frontend-v1/frontend/fixtures/syllabi.json` | new_file | 080d0de3838a | remove the staged file; it does not exist in the parent candidate, so the candidate then differs from its recorded digest and is rebuilt from the parent if needed |
| BP-0014 | `integration-staging/runtime/b06-rehearsal-2026-10-07/candidates/b06-frontend-v1/frontend/index.html` | modified_copy | c2bf9f4e32ad | remove the staged file; it does not exist in the parent candidate, so the candidate then differs from its recorded digest and is rebuilt from the parent if needed |
| BP-0015 | `integration-staging/runtime/b06-rehearsal-2026-10-07/candidates/b06-frontend-v1/frontend/search.mjs` | copied_snapshot | 6d45a67f794d | remove the staged file; it does not exist in the parent candidate, so the candidate then differs from its recorded digest and is rebuilt from the parent if needed |
| BP-0016 | `integration-staging/runtime/b06-rehearsal-2026-10-07/candidates/b06-frontend-v1/frontend/styles.css` | copied_snapshot | 0d33007e8bea | remove the staged file; it does not exist in the parent candidate, so the candidate then differs from its recorded digest and is rebuilt from the parent if needed |
| BP-0017 | `integration-staging/runtime/b06-rehearsal-2026-10-07/candidates/b06-frontend-v1/frontend/tests/client.test.mjs` | new_file | 6c23e46e86af | remove the staged file; it does not exist in the parent candidate, so the candidate then differs from its recorded digest and is rebuilt from the parent if needed |
| BP-0018 | `integration-staging/runtime/b06-rehearsal-2026-10-07/candidates/b06-frontend-v1/frontend/tests/flow.test.mjs` | new_file | c10ad67c8aca | remove the staged file; it does not exist in the parent candidate, so the candidate then differs from its recorded digest and is rebuilt from the parent if needed |
| BP-0019 | `integration-staging/runtime/b06-rehearsal-2026-10-07/candidates/b06-frontend-v1/frontend/tests/search.test.mjs` | modified_copy | 7fd00040fe00 | remove the staged file; it does not exist in the parent candidate, so the candidate then differs from its recorded digest and is rebuilt from the parent if needed |
| BP-0020 | `integration-staging/runtime/b06-rehearsal-2026-10-07/candidates/b06-frontend-v1/frontend/server.mjs` | staged_file_rewrite | 3b34f04c9192 | remove the staged file; it does not exist in the parent candidate, so the candidate then differs from its recorded digest and is rebuilt from the parent if needed |
| BP-0021 | `integration-staging/runtime/b06-rehearsal-2026-10-07/candidates/b06-frontend-v1/frontend/tests/server.test.mjs` | new_file | 75e3c7a145ec | remove the staged file; it does not exist in the parent candidate, so the candidate then differs from its recorded digest and is rebuilt from the parent if needed |
