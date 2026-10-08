# B07R2 — merge proposal (private, unmerged, undeployed)

Run: `b07-reviewfix-20261007-774e4dad` (second private review-fix run).

Status: **proposal only — nothing merged, nothing deployed, all seven gates
closed.** Additive to the B07 and B07R records; no previous proposal or
completion record is changed.

## What would be merged

The review-fix candidate `b07-operations-v2` vs frozen `b07-operations-v1`:

| File | Finding | parent sha256 | candidate sha256 |
|------|---------|---------------|------------------|
| `src/examdata/integration/operations/published.py` | F1, F2 | `54522b9e…f82a925a` | `7fbb4f5d…a84468ff` |
| `src/examdata/integration/operations/jobs.py` | F3, F4 | `916ae7b1…34427839` | `3b1935c2…5032e2eb` |
| `src/examdata/integration/operations/checkpoints.py` | F3 | `1f49dde5…b580805b` | `2e888c6f…1dd9d279` |
| `B07R2_CANDIDATE_MANIFEST.json` | (added) | — | `920f41c1…9bcec9ce` |

Everything else (218 files + the parent's own manifest
`3e7d2a77…061784`) is carried byte-for-byte. Candidate tree digest
(excluding the new manifest): 222 files / `8171cf1c…38fa48`. Parent tree
digest: 221 files / `5df25984…82c179`.

## Preconditions (abort on any mismatch)

1. Live candidate digest = `8171cf1c67c7891fc4c3354a482fb65600886aa0b5b88f9a1a546333c738fa48`
   and manifest sha256 = `920f41c1…9bcec9ce`.
2. Frozen parent digest = 221 / `5df25984…82c179`; parent manifest = `3e7d2a77…061784`.
3. `execution-ledger.json` sha256 = `6d4449d3…3101b4ba`.
4. Release authority has opened the required gates (listed below). This run
   holds none of them and requests none.

## Steps (only when authorized)

Copy the three files and verify every written sha256; add the B07R2 manifest
without altering the parent's; recompute the target tree digest; run the
28-test candidate regression (expect 28 passed); run the frozen route probe
(`J_published_statuses_pinned` expected red by design — re-pin only via an
explicitly authorized review change, never silently); re-run the validator
across three working directories with fresh evidence paths.

## Required authorizations

`original_paths_released`, `real_data_write_authorized`,
`upstream_requests_authorized`, `existing_service_cutover_authorized`,
`remote_deployment_authorized`, `original_cleanup_authorized`,
`cie_resume_authorized` — as named in the execution ledger. Not requested
here; listed for the release authority.

## Rollback

Conditional on matching candidate hashes only — see
`reports/B07R2_ROLLBACK_PROPOSAL.md`. Never removes later unrelated edits.

Evidence: `reports/B07R2_DIFF_FROM_V1.md` (+ patch and stat),
`reports/B07R2_FINDINGS_TO_TESTS_MATRIX.md`,
`reports/B07R2_EVIDENCE_INDEX.json`.
