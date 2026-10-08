# B07 independent review and constrained executor handoff

Review date: 2026-10-07. This is an additive review, not a release or a replacement for frozen B07 evidence.

## Verdict

B07 has a frozen private rehearsal and useful evidence. It has not been merged or deployed. However, the statement that no further work can be performed without releasing original projects is too broad: the defects below can be repaired and tested in a new private candidate without opening any gate.

Do not release or modify original projects to fix these findings. Preserve B07 v1 and all historical evidence. This review does not authorize service cutover, upstream requests, real-data access or writes, deployment, cleanup, or CIE batch resumption.

## Evidence and limits

Workspace: `C:/Users/weo/Desktop/api`.

Reviewed candidate: `integration-staging/runtime/b07-rehearsal-2026-10-07/candidates/b07-operations-v1`.

Independent synthetic reproductions: `integration-staging/runtime/b07-independent-review-20261007-hf7_6xwr/results.json`.

The reviewer imported the candidate's actual `examdata.integration` modules and checked that loaded `examdata` module files were inside the candidate. The reproductions are function-level synthetic checks, not HTTP end-to-end tests. No original source was imported or inspected. The existing Python executable was used to execute private code. No real credentials, upstream calls, services, or real data were used.

Candidate digest before and after the reproductions: 221 files, SHA256 `5df259843b26792910de697b2c646fc413c5b936edf3d95d04baf7afa482c179`. This digest excludes the candidate manifest and cache directories, using sorted relative paths and file hashes. Both measurements matched.

Also checked against the supplied report:

| File | SHA256 |
| --- | --- |
| B07_REHEARSAL_REPORT.md | ee6a9ece99016b64ce0dd6d7d6c8dee511fd11ce11d76c06026dfe05eec08b91 |
| B07_PROGRESS_LEDGER.json | b20fc5708cceb52137c229df5aa430b858a2cbdedc855f5cd190813bb95db1f7 |
| execution-ledger.json | 6d4449d3997b437fd3ea3a1fe7925fc78a7c0adbe0a5d3b793d6a8063101b4ba |

The reported 887-test run was not rerun in this review. The staged test runner and conftest target the base `examdata_integration` staging package. That result must remain labelled base staging regression; it does not establish regression coverage for every new B07 candidate implementation. The 522 probe executions represent 174 checks repeated from three working directories, not 522 distinct scenarios.

## Findings

### F1 — High: identity-known entries become verified without quality evidence

Candidate file: `src/examdata/integration/operations/published.py`, `build_published`, especially the classification around line 277.

Entries not explicitly excluded or marked partial in the manifest are classified as verified when their identity is not unknown. This classification does not inspect their quality summary or evidence labels.

Reproduction: construct a real `CatalogEntry` with known identity, `quality_summary={"content":"partial","answer_verification":"unverified"}`, and `evidence_labels=[]`. Supply an expected scope of one matching entry. Actual result: `verified=1`, `partial=0`, `derived_status="complete"`, `percentage=100.0`, with no problems.

This conflates published identity availability with verification. Define the coverage dimension explicitly. If the intended metric is publication presence, expose it as publication presence and do not imply content or answer verification. If the metric is verified coverage, require evidence appropriate to that dimension and preserve partial/unknown quality states. Missing evidence cannot become verification by default.

### F2 — High: contradictory expected counts can still produce complete coverage

Candidate file: `src/examdata/integration/operations/published.py`, `_coverage_row`, around lines 198–215.

Reproduction: expected count is one, but two matching catalog entries are supplied. Actual result: a problem named `expected_below_published`, while the same row reports `observed=2`, `derived_status="complete"`, and `percentage=100.0`; its denominator text still says expected=1.

Recording a problem does not make the completion claim valid. Keep expected and observed counts distinct. Treat unresolved manifest/count conflicts as incomplete or inconsistent using the supported contract. Do not silently increase the effective denominator and emit successful completion. Cover the opposite case too: the current implementation assigns `observed=expected` when entries are missing.

### F3 — Medium: scan limits do not bound attempted work

Candidate files: `operations/jobs.py`, `scan_checkpoint_root`, around lines 95–130; `operations/checkpoints.py`, `iter_checkpoint_paths`, around lines 272–286.

The file cap counts successful observations only. Oversized/unreadable files do not consume it. In addition, checkpoint discovery builds and sorts the entire recursive result before the cap is checked.

Reproduction: three synthetic checkpoint files containing `{}`, with `max_files=1` and `max_bytes=1`. Actual result: zero observations, three skipped files, `truncated=false`.

Budget attempted files, directory enumeration, retained skip records, and bytes read. A cap applied after an unbounded recursive listing is insufficient. Preserve a documented deterministic traversal rule within those bounds. Add an actual bounded-read mechanism if claiming strict byte bounds; the current pre-read size check alone does not establish that property under file changes.

### F4 — Medium: public sanitization leaves sensitive mapping keys unchanged

Candidate file: `operations/jobs.py`, `sanitize_tree`, around lines 68–77. The public dataset projection uses this sanitizer.

Reproduction: a synthetic secret is a mapping key, and a synthetic absolute Windows path is a nested key. Pass the synthetic secret through `secrets`. The value is redacted to `<secret>`, but both keys remain unchanged in the returned mapping.

No real secret leak was observed. The reproduced gap is that arbitrary dynamic keys are not covered by the sanitization guarantee. Prefer a public schema with allowlisted keys and explicit sanitized fields for dynamic content. If keys are transformed, handle collisions explicitly; silently overwriting records is unacceptable. Assertions must inspect full serialized output, including object keys, rather than string values alone.

## Copyable executor prompt

```text
Continue the API integration PRIVATE rehearsal from the frozen B07 checkpoint.

Workspace: C:/Users/weo/Desktop/api
Read these existing planning/review documents first:
1. docs/integration/MASTER_EXECUTION_PLAN_EN.md
2. docs/integration/EXECUTOR_PROMPT_EN.md
3. docs/integration/execution/B07_REHEARSAL_REPORT.md
4. docs/integration/execution/B07_INDEPENDENT_REVIEW_2026-10-07.md
5. integration-staging/runtime/b07-independent-review-20261007-hf7_6xwr/results.json

Your objective is to repair F1–F4 in a NEW private candidate and produce a
reviewable proposal with regression evidence. You are not authorized to merge,
deploy, reconcile original projects, or open any gate.

BOUNDARY
- Write only inside integration-staging/** and docs/integration/execution/**.
- Do not read, import, modify, copy fresh content from, or run original project
  source/data/services. Use existing private candidates and synthetic fixtures.
- Do not contact upstreams, use real credentials, restart services, resume CIE,
  write real data, deploy, or clean up original files.
- Preserve B07 v1, all existing evidence, all previous reports/proposals, and
  execution-ledger.json byte-for-byte. Do not overwrite failed-run evidence.
- All seven gates remain closed. A stopped or completed Kimi session does not
  release its paths. Do not request original release as a shortcut for these fixes.

STEP 1 — Establish provenance
Create a new unique private review-fix root and a new candidate copied solely
from B07 v1. Before copying, recompute the frozen B07 digest using its documented
algorithm and require the recorded 221-file digest. If it differs, save an
additive discrepancy report and stop candidate-dependent work. Record hashes
of the formal ledger and frozen B07 evidence. Do not edit those inputs.
Record every command's cwd, exact command, exit code, output, and timestamp.

STEP 2 — Reproduce before changing behavior
Create durable candidate-specific tests for the four reproductions in the
review. Execute them against the frozen implementation from the new test root,
without writing caches into frozen paths. Preserve the failing results. Assert
that imported examdata modules originate from the intended candidate. Use only
synthetic CatalogEntry objects, expected manifests, checkpoints, and secrets.

STEP 3 — Repair coverage semantics
Read the private coverage schema and consumers. State exactly what each metric
verifies. Separate publication presence, identity completeness, content quality,
and answer verification. Do not invent evidence or promote unverified quality.
Do not break an existing response contract silently: record any proposed schema
change and adjust private consumers/tests together. Keep expected and observed
counts distinct. Expected/observed conflicts must not report successful complete
coverage. Test missing entries, extra entries, unknown denominator, zero expected,
partial quality, absent evidence, exclusions, and explicit manifest partials.
Also verify multi-scope processing with the supported iterable input types.

STEP 4 — Repair scan budgets
Bound discovery as well as reading. Count unsuccessful attempts against the
applicable budget. Specify directory-entry, attempted-file, retained-result,
and byte budgets and their exhaustion signals. Keep ordering deterministic by
a documented bounded traversal rule. Avoid fully materializing an unlimited
tree before applying limits. Test oversized and unreadable checkpoints, many
irrelevant files/directories, exact limits, over-limit cases, and bounded reads.
Use portable synthetic tests; do not depend on real protected directories or
flaky wall-clock thresholds to establish boundedness.

STEP 5 — Repair public sanitization
Handle dynamic mapping keys safely, preferably by explicit public projection.
Test secret-bearing keys, absolute path keys, nested mappings/lists, and key
collisions. Inspect the entire serialized public output including keys. Confirm
that legitimate fixed schema keys and record counts remain intact. Exercise the
real candidate public projection and HTTP handler with synthetic local fixtures,
where supported; do not claim HTTP validation from helper-only tests.

STEP 6 — Validate the actual revised candidate
Run the new regressions against the new candidate. Rerun applicable B07 probe,
layout/build, cross-stack, Node, and smoke checks using separate evidence paths.
Repeat the working-directory checks. Adapt private validation tools only when
needed to accept the new candidate path; preserve their assertions and document
changes. Label synthetic Node checks as synthetic. If running the 887-test base
staging suite, label it base staging regression and do not substitute it for
candidate-specific coverage. Record warnings, skipped checks, and failures.
Never claim deployment, live cutover, or real-data acceptance from these tests.

STEP 7 — Freeze an additive proposal
Recheck that the original B07 candidate, frozen evidence, and formal ledger
hashes have not changed. Produce a new candidate manifest, a precise diff from
B07 v1, new merge/rollback proposals, an evidence index, and a findings-to-tests
matrix. Rollback must be conditional on matching candidate hashes and must
never remove later unrelated edits. Keep proposal status explicitly private,
unmerged, and undeployed. Do not change previous completion records.

FINAL REPORT
Report each finding as fixed/remaining with exact test evidence and module
origins. List candidate versus base-suite results separately. List every not_run
real-world acceptance item and its required authorization. Provide full artifact
paths and hashes. Acknowledge any residual defect instead of declaring the full
integration complete. Stop after the private proposal is ready for review.
```
