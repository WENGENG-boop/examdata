# B07R2 — rollback proposal (private, not executed)

Run: `b07-reviewfix-20261007-774e4dad`.

Status: **proposal only — nothing reverted, merged or deployed.** Reverses
exactly the review-fix delta if the review-fix is rejected.

## Condition

Rollback starts only when **all** recorded hashes still match the live tree:

| File (in `b07-operations-v2`) | required live sha256 |
|-------------------------------|----------------------|
| `src/examdata/integration/operations/published.py` | `7fbb4f5d…a84468ff` |
| `src/examdata/integration/operations/jobs.py` | `3b1935c2…5032e2eb` |
| `src/examdata/integration/operations/checkpoints.py` | `2e888c6f…1dd9d279` |
| `B07R2_CANDIDATE_MANIFEST.json` | `920f41c1…9bcec9ce` |

If any value diverges, **stop and report** — a later edit exists and must not
be removed. The rollback never touches `B07_CANDIDATE_MANIFEST.json` or any
file outside these four.

## Steps (only when authorized)

1. Verify every precondition.
2. Restore the three files from the frozen v1 candidate
   (`…/b07-rehearsal-2026-10-07/candidates/b07-operations-v1`), verifying each
   restored sha256 (`54522b9e…`, `916ae7b1…`, `1f49dde5…`).
3. Delete `B07R2_CANDIDATE_MANIFEST.json` only against its recorded sha256.
4. Recompute the tree digest: expected 222 files /
   `8dad753d0697dc708b54658aa4492e45954200c51a3cebd58c4ef3161dbf80bf`
   (the frozen v1 tree including its own manifest).
5. Re-run the 28-test suite; the recorded pre-fix split (20 failed / 8 passed,
   1 warning, `evidence/step2_frozen_red_run1.log`) is the expected outcome.
6. Record the rollback in a new additive report; never edit this proposal or
   earlier records in place.

## Authorizations

Same gate list as the merge proposal; none requested or held here.
