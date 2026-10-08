# B07R2 independent review

Date: 2026-10-07. Verdict: **reviewed, changes requested; F3 remains incomplete**. Private proposal only; no original release, merge, deployment, or gate change.

## Independently verified

- Re-ran the supplied candidate-specific suite: **28 passed, 1 warning**, exit 0. Candidate import-origin assertions were enabled. Test output and the exact subprocess command/cwd are in the independent evidence directory below.
- Recomputed B07 v1: 221 files, `5df259843b26792910de697b2c646fc413c5b936edf3d95d04baf7afa482c179`.
- Recomputed B07R2 v2: 222 files, `8171cf1c67c7891fc4c3354a482fb65600886aa0b5b88f9a1a546333c738fa48`.
- Rehashed all 232 file-hash records found in the evidence index: zero mismatches.
- Formal execution ledger: `6d4449d3997b437fd3ea3a1fe7925fc78a7c0adbe0a5d3b793d6a8063101b4ba`.
- Freeze file: `005fc0c6958b881f566e30fa0d0d08e4474f43e295551219f4e65fbbcfcc5e23`.

Independent evidence root:
`C:/Users/weo/Desktop/api/integration-staging/runtime/b07r2-independent-ytfq9g26`.
Read `results.json`, `additional-results.json`, and `pytest.txt` together. The first result used POSIX string ordering for the tree digest; the supplementary result applies the producer's `sorted(WindowsPath)` ordering and matches the frozen digest. This ordering difference is not candidate drift. The candidate remained unchanged before and after the test run.

Only private candidate code, private evidence, and documentation were inspected. The existing Python environment executable/dependencies were used. No original application source or real data was imported or inspected, no service was started, and no upstream request was made. Synthetic fixtures were created only in the new independent evidence root.

F1/F2/F4 changes address the prior concrete reproductions and their 28-test regression suite passes independently. This is not an exhaustive correctness claim. The base 887-test suite and full route validator were not rerun in this review; their results remain inherited evidence.

## R2-F3a — Medium: directory discovery remains unbounded

File in v2: `src/examdata/integration/operations/checkpoints.py`, `_CheckpointPathWalk.__init__`, `_read_dir`, and `__next__` (approximately lines 315–390).

`_read_dir` consumes the entire `os.scandir` iterator into a list and sorts it. It runs in the walker constructor before `__next__` checks `max_entries`, and again when each subdirectory is entered. There is no per-directory cap. Parent iterators also retain their directory lists while child directories are visited.

Independent reproduction: create one private directory containing 40 irrelevant files, wrap the real `os.scandir` iterator to count actual enumeration, then exhaust `iter_checkpoint_paths(root, max_entries=1)`.

Actual: **40 directory entries consumed, `entries_seen=1`, `exhausted=true`**. The exposed counter bounds processing after materialization, not discovery. Thus the report's statement that an individual directory listing is bounded is unsupported by the implementation.

Required repair: place an explicit budget on actual directory-entry consumption before appending to a list. Bound retained entries across active traversal levels. A globally lexicographically ordered prefix cannot be obtained from an arbitrary directory without first inspecting its contents: document the tradeoff. One safe option is to refuse an over-budget directory with a clear truncation signal, returning no supposedly complete deterministic prefix from that directory. Do not retain unlimited sorting while claiming bounded discovery. If one extra entry is used to detect overflow, declare and test that allowance explicitly.

## R2-F3b — Medium: cumulative read budget can be exceeded after stat

File in v2: `src/examdata/integration/operations/jobs.py`, `scan_checkpoint_root` (approximately lines 190–228), and `checkpoints.py`, `read_checkpoint_bounded` (approximately lines 202–227).

The cumulative budget is checked using `stat().st_size`. The actual reader receives only the per-file `max_bytes`, not the remaining cumulative budget. A changing file can therefore bypass the cumulative cap.

Independent synthetic reproduction: start with a two-byte checkpoint `{}`. Set `max_read_bytes=8`, `max_bytes=32`. Wrap the actual reader to grow the synthetic file to 16 bytes immediately after the scanner's stat check, then invoke the unchanged real reader. This deterministically simulates the stat/read race without touching real data.

Actual: **`bytes_read=16`, `truncated=false`, `exhausted=[]`** with a cumulative budget of 8. The reproduction did not mock the returned observation or byte count.

Required repair: pass the remaining cumulative allowance to the actual read operation and enforce it there. Account for all consumed bytes on success and failure. Define how oversized-file detection probes fit within the cumulative limit; the current per-file reader requests `max_bytes + 1`, so passing the remaining allowance unchanged is insufficient if that extra byte would exceed the strict total. Report budget exhaustion accurately, including when only one file exists. Test growth after stat, several files, exact and zero budgets, parse failures, and oversized-file detection.

An additional malformed-JSON check in `results.json` did NOT reproduce a failure: one eight-byte payload was accounted for, and the scanner stopped before reading the next one. Keep this negative finding; do not cite it as a defect.

## Contract validation still needs closure

The producer openly records the inherited route probe as 173/174 and the validator as exit 1, `b07_rehearsal_not_valid`. F1/F2 intentionally change the old pinned outputs, so this is plausibly an obsolete expectation, but it remains an unresolved acceptance check.

In a new private validation-tool copy, replace the obsolete pin with explicit reviewed assertions for the new coverage semantics. Preserve the old failed output. Derive expected values from the documented contract and fixtures, not by blindly snapshotting current output. Assert expected/observed/unmet counts, verification axes, status, percentage, exclusions, and unknown-denominator behavior. Then rerun the complete probe and three-cwd validator. Updating a private test to reflect the intended repair does not require releasing original source paths. Do not delete, skip, xfail, or invert the failing assertion merely to turn the suite green.

Also distinguish structural tree/digest equivalence from executing a build. The frozen builder need not be run if it would overwrite v1. Record the build as not executed unless an adapted private builder is actually exercised.

## Copyable executor prompt

```text
Continue PRIVATE API integration review fixes in C:/Users/weo/Desktop/api.
Read docs/integration/execution/B07R2_INDEPENDENT_REVIEW_2026-10-07.md,
the referenced independent JSON evidence, B07R2_FINAL_REPORT.md, and the
existing master execution plan before changing anything.

Objective: repair R2-F3a and R2-F3b and close the obsolete coverage contract
pin in a new private candidate and new validation-tool copies. F3 is not yet
complete. No original release is required or granted for this work.

1. Preserve B07 v1, B07R2 v2, all existing evidence/reports, and the execution
   ledger byte-for-byte. All seven gates stay closed. Read/write only private
   staged inputs and authorized documentation; do not inspect original source,
   import original applications, use real data/credentials, call upstreams,
   restart services, resume CIE, merge, deploy, or clean original paths.
2. Create a unique new private run root. Recompute v2's documented digest and
   require 222 files / 8171cf1c67c7891fc4c3354a482fb65600886aa0b5b88f9a1a546333c738fa48.
   Use the producer's Windows Path sorting rule. Stop on mismatch. Copy solely
   from this frozen private candidate and record parent provenance.
3. Add durable red-on-v2 tests that instrument actual scandir consumption and
   deterministically grow a synthetic file between stat and the real read.
   Assert module origins. Preserve failing results in new evidence files.
4. Repair actual enumeration and cumulative byte enforcement as specified in
   the review. Document ordering, retained-memory bounds, overflow probes,
   exact-limit semantics, and counters. Test the resource operation itself,
   not only counters maintained by the implementation. Do not hide work in
   a constructor or directory sorting before budget checks.
5. Re-run all 28 inherited candidate tests plus the new adversarial cases.
   Preserve F1/F2/F4 behavior and validate full serialized public output.
6. Adapt a COPY of the private probe to the documented new coverage contract.
   Provide an assertion diff with a reason for each changed expectation.
   Preserve the old 173/174 evidence. Run the complete revised probe and
   three-cwd validator to successful completion; report any remaining failure.
   Keep synthetic Node evidence and base staging regression separately labelled.
7. Rehash frozen inputs and produce a new candidate manifest, precise parent
   diff, findings-to-tests matrix, merge/rollback proposals, command transcripts,
   and evidence index. Use new filenames; never rewrite historical conclusions.
   Retain failures and warnings. A digest check is not an executed build.
8. Stop with a private, unmerged, undeployed proposal ready for review. Report
   remaining defects and all real-world not_run items. Do not claim full API
   integration completion or request original-path release to bypass these fixes.
```
