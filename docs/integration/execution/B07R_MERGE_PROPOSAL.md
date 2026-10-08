# B07R — merge proposal (private, unmerged, undeployed)

Status: **proposal only — nothing merged, nothing deployed, all seven gates
closed.** Additive to the B07 records; no previous proposal or completion
record is changed.

## What would be merged

The review-fix candidate `b07-operations-v2` vs frozen `b07-operations-v1`:

| File | Finding | parent sha256 | candidate sha256 |
|------|---------|---------------|------------------|
| `src/examdata/integration/operations/published.py` | F1, F2 | `54522b9e…f82a925a` | `af32610d…21af2574` |
| `src/examdata/integration/operations/jobs.py` | F3, F4 | `916ae7b1…34427839` | `d0405b8b…af55cd15` |
| `src/examdata/integration/operations/checkpoints.py` | F3 | `1f49dde5…b580805b` | `0a439d26…ecdcb6b4` |
| `B07R_CANDIDATE_MANIFEST.json` | (added) | — | `0a0052cd…1662ea54` |

Everything else (218 files + the parent's own manifest
`3e7d2a77…061784`) is carried byte-for-byte. Candidate tree digest
(excluding the new manifest): 222 files / `f0f9a3c4…a022c`. Parent tree
digest: 221 files / `5df25984…2c179`.

## Preconditions (abort on any mismatch)

1. Live candidate digest = `f0f9a3c49db995ad5934907763a4664576ee07f3280c3586d9a8670c991a022c`
   and manifest sha256 = `0a0052cd…1662ea54`.
2. Frozen parent digest = 221 / `5df25984…2c179`; parent manifest = `3e7d2a77…061784`.
3. `execution-ledger.json` sha256 = `6d4449d3…3101b4ba`.
4. Release authority has opened the required gates (listed below). This run
   holds none of them and requests none.

## Steps (only when authorized)

Copy the three files and verify every written sha256; add the B07R manifest
without altering the parent's; recompute the target tree digest; run the
26-test candidate regression (expect 26 passed); run the frozen route probe
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
`reports/B07R_ROLLBACK_PROPOSAL.md`. Never removes later unrelated edits.

Evidence: `reports/B07R_DIFF_FROM_V1.md` (+ patch and stat),
`reports/B07R_FINDINGS_TO_TESTS_MATRIX.md`,
`reports/B07R_EVIDENCE_INDEX.json`.
