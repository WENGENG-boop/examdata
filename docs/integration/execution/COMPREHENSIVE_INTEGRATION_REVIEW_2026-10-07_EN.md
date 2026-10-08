# Comprehensive integration review and closure requirements

Date: 2026-10-07. Workspace: `C:/Users/weo/Desktop/api`.

**Decision: changes required. The private candidate is reproducibly frozen, but neither the B07 fixes nor the full integration are ready for final acceptance.**

This report expands the earlier B07 reviews into one closure backlog. Use it with `FINAL_INTEGRATION_EXECUTOR_PROMPT_EN.md` and `FINAL_ACCEPTANCE_MATRIX_2026-10-07.json` in this directory. The new prompt supersedes the narrow B07R2 repair handoff for future work; historical reports and frozen evidence remain unchanged.

## 1. What was reviewed, and what was not

Reviewed current private candidate:

`integration-staging/runtime/b07-reviewfix-20261007-774e4dad/candidates/b07-operations-v2`

Reviewed planning and evidence include the master execution plan, R0104 repair report, B06/B07/B07R2 reports, B07R2 merge/rollback proposals, formal execution ledger, and earlier independent results. Inspected candidate implementation includes published coverage, checkpoint discovery/reading, sanitization, operations projection, API construction/handlers, route registry/composition, catalog validation, quality/completeness contracts, runtime path helpers, and frontend entry/server code. This is a targeted cross-component review, not a claim that every line of every inherited module was audited.

This review did not read original application source or live data, start existing services, contact upstreams, perform a real merge, or deploy. Existing Python interpreter/dependencies were used to execute candidate-only imports. No real-world correctness or deployment acceptance is inferred from synthetic tests.

The active-owner boundary remains in force. The user asked for a thorough review and complete handoff; that request does not supply the previously required explicit release of Kimi-owned original paths. All seven formal gates are still closed.

### Current independent evidence

Reproducible audit script:
`integration-staging/runtime/comprehensive-review-20261007/review.py`

Successful evidence directory:
`integration-staging/runtime/comprehensive-review-20261007/evidence-8kvuct3k/`

Important files: `results.json`, `pytest.txt`. Run with:

```powershell
Set-Location 'C:/Users/weo/Desktop/api'
& './examdata/.venv/Scripts/python.exe' -I -B 'integration-staging/runtime/comprehensive-review-20261007/review.py'
```

Every execution creates a new private evidence directory. It imports the frozen candidate, checks import origins, creates only synthetic files, and rechecks the candidate digest. It is an audit recorder, not an all-green acceptance suite: inspect the recorded assertions/results; an exit code of zero means the recorder completed.

The initial reviewer harness execution failed because it omitted the API route prefix. That harness error is preserved in `first-run-error.txt`; the initial fixture directory remains. The corrected run uses `links.PREFIX` and completed successfully. This is not a product defect.

### Verified results

| Verification | Result | Evidence status |
| --- | --- | --- |
| Supplied B07R2 candidate-specific suite | 28 passed, 1 Starlette deprecation warning, exit 0 | Re-run during this review |
| Candidate before/after audit | 222 files, identical SHA256 | Recomputed during this review |
| B07R2 tree digest | `8171cf1c67c7891fc4c3354a482fb65600886aa0b5b88f9a1a546333c738fa48` | Matches frozen manifest |
| Formal ledger digest | `6d4449d3997b437fd3ea3a1fe7925fc78a7c0adbe0a5d3b793d6a8063101b4ba` | Recomputed during this review |
| 232 evidence-index file hashes | All matched; zero unresolved paths | Rechecked during this review; see `comprehensive-review-20261007/final-verification.json` |
| Base staging suite | Producer reports 887 passed | Not rerun here; not candidate-specific evidence |
| Full inherited probe / validator | Producer reports 173/174; validator exit 1 | Not rerun here; unresolved contract pin |
| Synthetic Node checks | Producer reports 18/18 + 41/41 | Not rerun here; does not prove real components |
| File symlink containment experiment | Not run: Windows error 1314 prevented creating link | Must not be reported as passed |

The producer's digest algorithm sorts Windows `Path` objects, which differs from sorting POSIX relative-path strings. Use the documented historical algorithm when verifying frozen hashes; introduce any portable canonical algorithm as a separately versioned format with both digests, never as unexplained drift.

## 2. Confirmed findings and precise repair requirements

### C01 — High: verification still trusts unsupported or contradictory quality claims

Files: `operations/published.py` (`_answers_verified`, `_quality_bucket`); `catalog/model.py` (`CatalogEntry.validate`); `contracts/quality.py`.

Independent cases:

1. A real `CatalogEntry` with `content=complete`, `answer_verification=source_verified`, and **empty evidence labels** passes `CatalogEntry.validate()` and produces `verified=1`, `complete`, 100%.
2. With `answer_presence=missing` and `answer_verification=source_verified`, it still produces the same complete/verified result.
3. With an empty identity mapping it still reports `identity_complete=1` and complete coverage.

The earlier partial/unverified case is repaired. These broader cases show that the claimed evidence-aware semantics are not yet enforced at the accepted entry boundary. They were demonstrated with injected synthetic catalog entries; this review does not claim an attacker can inject such entries through a deployed endpoint.

Repair the trusted-data contract end to end. Define required identity by entity/system. Establish provenance-backed quality states at ingestion and reject or downgrade contradictions. A bare string label is not sufficient proof of a source/manual decision. Preserve provenance references and manual decisions. Coverage may consume a validated summary only if validation is mandatory on every entry path and its evidence can be traced. Otherwise enforce the constraints at coverage derivation too. Do not require answers for entities where answers are not applicable; use entity-specific criteria.

Tests must include empty/missing identity, `UNKNOWN`, persisted unknown encodings, missing evidence, unsupported evidence labels, absent answers, conflicting answers, missing required assets, manual decisions, and legitimate not-applicable cases. Include positive evidence-backed controls and verify public output.

### C02 — High: manifest inconsistency can coexist with complete coverage

File: `operations/published.py`, `build_published` and `_coverage_row`.

With expected count one and one accepted entry, a manifest partial reference to a nonexistent ID produces `manifest_id_not_published` **and** a complete/100% row. The count-overflow case is repaired, but not all manifest contradictions invalidate completion.

A related helper-level check supplied the same public ID twice with expected=2; it counted two verified entries and returned complete. The catalog store already has duplicate protections in its normal mapping path; this duplicate check identifies a coverage boundary assumption that must be enforced or explicitly validated, not proof that all normal catalog builds duplicate entries.

Require unique logical membership, validate duplicate/conflicting exclusions and partial declarations, validate referenced IDs against scope, and define the effect of each problem on status. Unresolved authoritative scope contradictions must not report complete. Count unique validated entries; surface collisions instead of silently choosing one. Define all-excluded and zero-expected behavior explicitly. Preserve unknown denominators and distinguish expected, observed, excluded, unmet, and verified.

### C03 — Medium: discovery budget applies after unbounded directory enumeration

File: `operations/checkpoints.py`, `_CheckpointPathWalk._read_dir` and constructor.

Reproduced: `max_entries=1`, one directory with 40 irrelevant files. Actual `os.scandir` entries consumed: **40**. Reported `entries_seen`: **1**. The entire directory is read/sorted before budget checks. Parent lists remain retained while walking children, so the implementation is not bounded to one active directory list either.

Budget actual enumeration before materializing entries, and bound retained entries across traversal depth. Specify how overflow detection works. If globally sorted output cannot be produced within the budget, fail/truncate the directory explicitly rather than presenting an arbitrary prefix as complete. Instrument the resource operation in tests, not only the implementation's counters. Include large flat directories, deep trees, many non-checkpoint files, exact limits, zero limits, and invalid budgets.

### C04 — Medium: stat/read growth bypasses cumulative byte budget

Files: `operations/jobs.py`, `scan_checkpoint_root`; `operations/checkpoints.py`, `read_checkpoint_bounded`.

Reproduced: file size at stat is two bytes; it grows to 16 bytes before the real read. `max_read_bytes=8`, `max_bytes=32`. Result: **16 bytes read, `truncated=false`, no exhaustion reason**.

Enforce the remaining cumulative allowance at the actual read, including detection bytes and error paths. The current `max_bytes+1` probe must be included in the budget design. Do not claim a strict maximum while intentionally reading beyond it. Include a deterministic growth test, partial read/error tests, multiple-file exhaustion, malformed payloads, and exact/zero limits.

### C05 — Medium: iterator-valued secrets are consumed before sensitive values

File: `operations/jobs.py`, `sanitize_tree`.

Reproduced with `secrets=iter([synthetic_secret])`: sanitizing a harmless key consumes the iterator, so the secret survives in the value and nested list. A tuple-valued control redacts correctly. The current HTTP helper supplies a tuple; this is a supported-helper-contract defect, not evidence of a current production secret leak.

Materialize normalized secrets once at the public boundary and reuse the immutable sequence recursively. Check callers that loop over records or project several sections. Test generators, tuples, empty values, overlapping secrets, dynamic keys, nested values, collision preservation, and full serialized output. Keep schema keys stable where possible and never lose records after collisions.

### C06 — High integration-readiness gap: operations state remains stale for app lifetime

Files: `api/dataset.py`, `operations_view` / `default_dataset`; `api/app.py`, `create_app`, coverage and job handlers.

Actual HTTP reproduction: create an app from a private running checkpoint; change that checkpoint to stopped with a later timestamp; request coverage again from the **same app instance**. The operations response is byte-equivalent as structured data, still shows the earlier time and `freshness=current`, and still shows the old queued job state.

No job was resumed and no checkpoint was overwritten. This is a freshness/display issue: the view is computed at app construction and no refresh occurs on subsequent requests. It is acceptable for an explicitly identified immutable rehearsal snapshot, but insufficient as current live diagnostics.

Choose and document a bounded refresh/TTL or immutable observation-revision model. Expose observation age and stale/incomplete state, and do not equate newest-in-a-snapshot with current-on-disk. Test same-process updates, running-to-stopped transitions, conflicting timestamps, scan failures, concurrent requests, and safe cache behavior. Preserve source authority and never mutate jobs as a side effect of reading.

### C07 — Medium: expected-manifest parsing bypasses operations budgets

File: `operations/published.py`, `load_expected_manifest` / `parse_manifest`.

Static inspection and instrumented small-file execution confirm `Path.read_text` loads the whole manifest without a size cap. The parser has no explicit scope/reference-count limits. Bounding checkpoint reads alone does not bound operations initialization; large manifests can dominate memory and scope-by-entry work.

Use a bounded manifest reader, explicit structural limits, and a clear invalid/oversized result. Validate depth, scope count, ID/reason lengths and declaration counts before expensive processing. Index validated catalog membership where appropriate. Exercise small budget boundaries using synthetic files rather than allocating enormous test inputs.

### C08 — Medium: revised contract has no green whole-candidate validator

The old coverage pin explains the remaining failed check, but the proposal's postcondition still expects 173/174 and a failing validator. This cannot be the final acceptance criterion.

Update a new private probe copy from the documented intended contract, with an assertion diff and independently calculated expected values. Preserve historical red evidence. Require the complete new probe and three-cwd validator to pass without xfail, suppression, skipped assertions, or success-code rewriting.

The 28 tests pass but miss C01–C07. This demonstrates why regression counts alone are not closure evidence.

### C09 — High release-plan defect: merge proposal is not an executable final-tree reconciliation

Files: `B07R2_MERGE_PROPOSAL.json`, `B07R2_ROLLBACK_PROPOSAL.json`.

The merge instructions refer to “the target” without a concrete resolved target mapping, copy three files directly, and require a target digest equal to the private candidate. They do not encode the released original file's current hash and three-way reconciliation. This may describe copying the private delta into an exact parent clone; it is not sufficient to merge into a changed real project.

Both proposals list all seven gates as required, including CIE resumption and original cleanup. A code-only merge does not require or authorize those actions. The rollback points at the private v2 tree and restores defective v1 bytes, which is a private delta rollback, not a production rollback. Its all-seven-gate list also conflicts with action-level authorization established by R0104.

Keep these historical proposals frozen. Produce distinct proposals for private candidate rollback, released-original code merge, data-pointer change, service cutover, deployment, and optional cleanup. Each row needs exact source/target paths, scope owner, latest target hash, expected result hash or semantic reconciliation record, required action gates, preconditions, conflict behavior, and rollback source. Never deploy private fixture trees wholesale over originals. No unspecified target is executable.

## 3. Project completion gaps beyond B07

These are expected deferred work under the isolation policy, not accusations that the private executor secretly performed a bad deployment.

| Area | Current evidence | Required closure |
| --- | --- | --- |
| Real baseline and active Kimi changes | Original tree remains protected; 71-route historical inventory | Human path release, fresh route/source baseline, three-way reconciliation preserving Kimi work |
| B02–B07 | Private rehearsal lineage only | Real package/source integration after release; every original change reviewed and tested |
| Runtime dataset | `create_app()` defaults to `default_dataset()`, fixture registry/snapshot/features | Explicit production dataset assembly; missing production config fails closed rather than serving fixtures |
| v2 capabilities | Registry has 34 GET route specifications, including fixture/deferred semantics | Per-system capability/evidence matrix and real supported behavior; route existence is not feature completion |
| Frontend | Candidate entry UI exposes CIE/Edexcel paper search; staged banner and fixture server remain | Planned IELTS/TOEFL/question/answer/audio/materials/timetable/operations journeys, plus real browser acceptance |
| Packaging | Current candidate is a source/fixture tree, with no standalone root `pyproject.toml` | An actual assembled build, wheel/install test, packaged assets/components, installed CLI/service from arbitrary cwd |
| B08 | No B08 completion artifact found in searched execution/staging filenames | Synthetic copy/restore rehearsal now; approved consistent real snapshots and reconciliation later |
| B09 | Base tests and candidate tests differ; whole validator remains red | One final tested revision, actual installed-artifact tests, source/runtime/contract/browser acceptance |
| B10 | Private delta proposals and reports | Complete final merge/deploy/rollback manifest with action-specific gates, version identity, runbook, and handoff |
| Current project documentation | Master header still says implementation has not started; status snapshots are historical | New current-status index now; proposed updates to protected top-level docs, applied only after path release |
| Deployment and cleanup | Not authorized, not run | Separate decisions; cleanup and CIE resumption are not mandatory prerequisites for code integration |

The existing CLI entry point must remain `examdata = "examdata.cli:app"`, with source target `examdata/src/examdata/cli.py`; do not regress to the nonexistent `examdata/cli.py` target from the older merge-map defect. Reverify against the released baseline when permitted.

The companion acceptance template has **81 criteria**. Its initial `pending` values are requirements, not claims that 81 tests ran. It covers private acceptance, released-original acceptance, and separately selected operational actions. Every new execution must copy it into its own results ledger and attach actual evidence.

## 4. What can be completed before original-path release

1. Repair C01–C08 in a new private descendant; preserve every frozen input.
2. Add adversarial cross-component tests, public-response tests, resource instrumentation, and real browser tests against synthetic local services.
3. Assemble a coherent private release tree from existing staged sources and explicit manifests; no fresh copying from originals.
4. Complete synthetic migration and restore, private packaging/build/clean-install, frontend scope, and operations freshness rehearsals.
5. Replace ambiguous release proposals with concrete private proposals and a fully specified conditional final merge plan.
6. Build one acceptance matrix covering all master-plan sections and B00–B10, with actionable evidence and no blanket “done”.

The absence of release is not a reason to stop after fixing two functions. Conversely, passing these private checks is not permission to cross into originals.

## 5. Required final completion levels

**Private closure:** all applicable private acceptance rows pass on one final candidate/artifact revision; no known in-scope private defect remains; real-only rows explicitly blocked by named missing authorization. Report `private_integration_candidate_ready`, not full integration complete.

**Real integration closure:** explicit original-path release; current owner work reconciled; real component/data adapters validated using authorized snapshots/samples; final released-tree routes and installed bundle pass; required user journeys work; rollback and docs are current. If service cutover is not authorized, report `integration_ready_cutover_not_run`.

**Operational closure:** separately authorized target/service/data actions are executed and observed; running version/hash, health, user flows, and rollback evidence match the release. Only then claim the particular runtime/deployment is complete. Source cleanup and resuming a stopped CIE job remain optional separately scoped actions.

There is no honest guarantee that one more round will discover zero new defects. The executable handoff is designed to finish all currently known work and to keep going when related failures appear, rather than stopping at another local milestone. Original access and real-world acceptance remain factual limits until released.

## 6. Reviewer acceptance rule

Reject a closure claim if any of the following holds:

- A confirmed C01–C09 item lacks a fix, precise counter-evidence, or an explicit scope decision supported by the user.
- A required test is red, skipped, stale, run against the wrong package, or replaced by a mock while claiming real behavior.
- A build is asserted solely from source hashes or copy equivalence.
- Synthetic data is exposed as real data or quality is promoted without evidence.
- A protected path was accessed without release, a gate was inferred, or cleanup/CIE permission is bundled into unrelated work.
- The final file hashes differ from the tested revision without affected checks being rerun.
- A real-only acceptance row is hidden by marking an entire packet complete.
- A copy-over merge lacks fresh target hashes, conflict handling, and rollback.

Use the companion prompt and machine-readable matrix for the next full closure run.
