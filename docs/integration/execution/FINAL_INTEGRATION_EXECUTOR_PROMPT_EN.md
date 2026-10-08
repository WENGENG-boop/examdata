# Full integration closure — executor prompt

Copy this entire document to the execution agent. This is a complete continuation task, not a request to produce another plan. Execute the permitted work, investigate and repair related failures, and finish with evidence. Do not stop after a small B07 patch or another two-function milestone.

## 1. Objective and authoritative inputs

Workspace: `C:/Users/weo/Desktop/api` on Windows/PowerShell.

The human wants all existing APIs and the project integrated into one coherent, maintainable product. Your task is to close all known private defects, complete every release-independent preparation and acceptance task, and then complete real integration only when the human has explicitly released the necessary original paths/actions. Preserve existing behavior, source provenance, manual decisions, and Kimi's final work. Do not invent a successful completion claim to satisfy the user's desire to finish.

Read these files in this order:

1. `docs/integration/execution/COMPREHENSIVE_INTEGRATION_REVIEW_2026-10-07_EN.md`
2. `docs/integration/execution/FINAL_ACCEPTANCE_MATRIX_2026-10-07.json`
3. `docs/integration/MASTER_EXECUTION_PLAN_EN.md`
4. `docs/integration/execution/R0104_REPAIR_REPORT.md`
5. `docs/integration/execution/B07R2_FINAL_REPORT.md`
6. `docs/integration/execution/B07R2_INDEPENDENT_REVIEW_2026-10-07.md`
7. `integration-staging/runtime/comprehensive-review-20261007/evidence-8kvuct3k/results.json`
8. `integration-staging/runtime/comprehensive-review-20261007/review.py`
9. B00–B07 reports/proposals and the existing staged module/route inventories, as needed for lineage and exact merge targets.

The comprehensive review expands the earlier narrow repair prompts. The master plan still supplies architecture, API scope, identity, quality, compatibility, and acceptance requirements. Old “complete” labels describe their historical evidence scope; do not use them to bypass new findings. Do not rewrite frozen historical reports to make them agree with a new result.

## 2. Non-negotiable ownership and authorization rules

Current permitted write roots:

```text
C:/Users/weo/Desktop/api/integration-staging/**
C:/Users/weo/Desktop/api/docs/integration/execution/**
```

Current private source candidate:

```text
C:/Users/weo/Desktop/api/integration-staging/runtime/b07-reviewfix-20261007-774e4dad/candidates/b07-operations-v2
```

The expected 222-file digest, excluding its own manifest and caches, is:

```text
8171cf1c67c7891fc4c3354a482fb65600886aa0b5b88f9a1a546333c738fa48
```

Its manifest SHA256 is:

```text
920f41c1b98199b087a4a8c7dea918c23d0f8144afdfebb87bfb2b2e9bcec9ce
```

The frozen formal execution-ledger SHA256 is:

```text
6d4449d3997b437fd3ea3a1fe7925fc78a7c0adbe0a5d3b793d6a8063101b4ba
```

Until explicit release:

- Do not read, import, modify, freshly copy from, run tests in, or execute original application source/data trees. Existing private copies and immutable private evidence are the inputs.
- The known Python executable may be used as an interpreter: `C:/Users/weo/Desktop/api/examdata/.venv/Scripts/python.exe`. Do not alter that environment or import the original application from it. Prove candidate import origins.
- Do not stop, restart, signal, reconfigure, or occupy the ports of existing services or Kimi. Private synthetic loopback services may bind port 0, with logs/PIDs/temporary data under your new run root. Stop only processes you started.
- No real credentials, upstream source requests, live database reads/writes, remote deployment, original cleanup, or CIE resumption. No global environment changes, package installs into existing environments, or broad formatting/deletion.
- Do not mutate B07 v1, B07R2 v2, their tests/tools/evidence, earlier private roots, or the formal ledger. Make a new descendant, new tools, and a new closure ledger.
- A quiet Kimi session, a completion report, this prompt, or a passing test does not release original paths. A tool approval is not evidence that the human released an active owner's project.
- Apply action-level gates. Private repair/testing requires no original release. Code merge requires released paths. Real-data write/pointer change, service cutover, upstream requests, deployment, cleanup, and CIE resumption require their own applicable authorization. Never demand/open all seven merely to copy private code or prepare a rollback.

Do all permitted work before presenting a consolidated missing-release request. If permission arrives during execution, record its exact text, timestamp, paths, and constraints and continue only with actions it covers. Authorization is not inferred from elapsed time or silence.

## 3. Establish a new run and evidence discipline

1. Create a unique child root under `integration-staging/runtime/`, named for final integration closure. Never reuse a frozen root for output.
2. Create `candidates/`, `tests/`, `tools/`, `evidence/`, `reports/`, `release/`, `migration/`, and `tmp/` under it. Record the resolved absolute paths and ensure all outputs stay inside permitted roots.
3. Recompute parent manifest/tree and ledger hashes BEFORE copying. Use the existing documented `sorted(WindowsPath)` digest algorithm for historical hashes. If you add a portable POSIX-string ordering digest, version it and retain both. On mismatch, preserve an additive discrepancy report and stop only work dependent on that untrusted baseline.
4. Copy solely from verified private parents. Record one provenance row per source file; earlier carried manifests are historical inputs, not evidence of current production configuration.
5. Set `PYTHONDONTWRITEBYTECODE=1`, use isolated basetemps, and disable pytest cache output into frozen paths. Clear only process-local environment variables that would redirect imports/data to originals; do not print secrets.
6. Maintain `CLOSURE_LEDGER.json`: task/action, dependencies, status, input hashes, output hashes, exact command/cwd/exit/timestamp, evidence classification, required authorization, and remaining blockers. Keep the old execution ledger frozen. Private success never satisfies a real-effect dependency.
7. Copy the supplied acceptance matrix into the run. Add rows for newly discovered related issues; do not remove mandatory rows. Every pass needs fresh evidence for the final tested revision. Allowed row outcomes: pass, fail, blocked_authorization, blocked_environment, not_applicable_with_reason, pending. A mandatory not-applicable decision requires a documented scope basis; it is not a convenience escape.
8. Preserve red tests, harness errors, warnings, failed commands, and superseded evidence. Do not overwrite a failed run with the green run's filename. Keep logs of actual command execution, not reconstructed success summaries alone.

## 4. Work package W1 — repair coverage and trust boundaries

Address comprehensive findings C01 and C02 together with all affected producers, schemas, projections, and tests.

### Required behavior

- Define coverage per system, scope, entity type, and dataset revision. Do not average unrelated systems into one completion percentage.
- Separate published presence, valid identity, complete required content, answer presence, answer verification, assets, audio integrity/alignment, and region verification.
- Establish a validated entry boundary. Identity requires the entity-specific fields; empty mappings, nulls, unresolved sentinels, and persisted unknown markers cannot imply identity complete. Preserve known-not-applicable identity fields.
- `source_verified` must trace to suitable source evidence; `manual_adjudicated` must trace to an actual preserved decision. Validate provenance consistency, not merely an enum string or presence of a generic evidence label.
- Reject or downgrade contradictory states such as missing answers plus source-verified answers. Use type-specific requirements so documents, assets, and questions without applicable answers are handled correctly.
- Synthetic internally consistent content may pass fixture structure checks but may not become verified real content. Preserve evidence classifications in public and private outputs.
- Define expected, observed, excluded, unknown, missing, partial, verified, unmet, and every percentage denominator in a versioned contract note. The existing `missing` bucket and new `unmet` field are not interchangeable. Retaining field names while changing meaning is a semantic contract change that consumers must handle.
- Count unique validated logical entries. Reject duplicate IDs with conflicting content. Prove normal ingestion and all alternate construction/deserialization paths enforce the same rule.
- Validate manifest scope IDs, referenced entity IDs, duplicates, exclusion/partial overlap, wrong-system references, and absent references. Any unresolved contradiction affecting the declared scope prevents complete status.
- Keep unknown denominators unknown; define zero expected, all-excluded, overfilled, and underfilled behavior explicitly. Never inflate the denominator silently.
- Preserve generators by consuming them once where multiple passes are required.

### Tests and outputs

Reproduce C01/C02 red on the parent. Add positive controls with valid evidence and type-specific not-applicable cases. Test contradictory answer/asset/identity states, duplicate IDs, mixed scopes, missing references, unknown/zero denominators, exclusions, and generator inputs. Assert the public API projection and model validation, not only helper return values. Generate `COVERAGE_CONTRACT_DECISION.md`, test results, and any schema/consumer diffs.

## 5. Work package W2 — truly bounded operations IO

Address C03, C04, C07 and containment robustness as one design.

1. Set explicit budgets for actual directory entries enumerated, attempted files, retained path records across traversal levels, retained skip records, per-file bytes, total bytes, manifest bytes, scope/reference counts, nesting/depth, and public diagnostic output. Validate negative/bool/invalid configuration rather than allowing surprising behavior.
2. Instrument actual `os.scandir` consumption and actual file reads. Budget checks must occur before consuming unbounded resources. A constructor/list comprehension/sort may not hide work outside the counters.
3. Resolve deterministic ordering versus bounded discovery honestly. If obtaining a sorted full directory requires more input than permitted, mark that directory incomplete or refuse it. Document any one-entry overflow-detection allowance and include it in resource assertions.
4. Enforce the remaining total byte allowance at the actual read, independent of stat. Include probe bytes and failed/partial reads in accounting. Handle file growth/shrinkage/replacement races without overstating the guarantee.
5. Bound expected-manifest loading and structure before expensive scope-by-entry processing. Return structured invalid/oversized outcomes; never crash a public route with raw parse details or absolute paths.
6. Constrain reads to the configured root. Test symlink/reparse-point files and directories, traversal, special files, unreadable entries, root disappearance, and changing entries. Do not follow arbitrary checkpoint links outside the authorized root. Test links only between synthetic paths inside your private run. If native link creation is unavailable, use a safe unit seam plus record the native case as blocked; do not report it passed.
7. Expose useful sanitized budget diagnostics through the operations projection, including the reason for truncation and snapshot incompleteness. Do not lose new scan fields when converting into `OperationsDataset`.

Durable tests must cover a wide single directory, deep trees, irrelevant files, exact/zero/over limits, many skipped files, growth after stat, multiple-file cumulative budgets, malformed input, bounded manifest parsing, and partially readable trees. Avoid flaky wall-clock thresholds. Keep the 28 inherited tests but expand them; do not stop at their current pass count.

## 6. Work package W3 — sanitization and fresh operations state

Address C05 and C06.

### Sanitization

Normalize/materialize the supplied secret iterable once at the top-level projection boundary and reuse it. Cover keys and values, lists, nested mappings, Unicode/path forms, configured text limits, overlapping secrets, and deterministic collision handling without record loss. Preserve fixed schema keys. Inspect full serialized JSON/HTTP output and logs with synthetic markers; do not read or display actual credentials for testing. Verify tuple and generator inputs produce equally sanitized outputs. Preserve public errors and avoid returning internal exception traces.

### Freshness

Implement an explicit bounded observation model: a short documented TTL/refresh service, or versioned immutable observations with honest age/staleness and an explicit refresh path. Ordinary diagnostic reads must never enqueue, resume, cancel, fetch upstream content, or write a checkpoint.

The same running app must observe a later stopped checkpoint within the declared freshness bound, or clearly report stale/unknown observations rather than “current.” Keep dataset revision and observation revision distinct. Resolve conflicts without guessing authority from filename or read order. Test timestamp ties, invalid/absent timestamps, same-process updates, concurrent readers, scan failures, stale cache fallback, and running-to-stopped transitions. Do not solve freshness by restarting the existing service.

## 7. Work package W4 — complete the private product, not only operations

Make a capability-to-implementation map for all master-plan endpoint families and original legacy families. Distinguish route registration, fixture implementation, installed local implementation, and real source acceptance. The 34 staged GET specifications and 71 historical legacy routes are baselines, not final immutable totals.

### Production assembly seam

Provide separate explicit fixture and production assembly paths. Production configuration must not silently fall back to `fixture_providers`, fixture feature sources, sample content, fake Node components, or static mock jobs. A missing real component/configuration must fail clearly or expose a truthful unavailable capability. Keep private fixture mode conspicuously labelled. In the current private phase test the production seam with injected synthetic components; defer actual original providers until release.

### API and compatibility

Validate every planned endpoint family, response envelope, typed error, filter allowlist, stable cursor, revision mismatch, binary MIME/bytes, range/ETag, capability link, auth configuration boundary, and resource budget. Test partial-source versus all-source failure; no arbitrary URL proxy; no crop/download/network side effects from ordinary catalog search; no subprocess per list item. Test route composition against a synthetic host, handler scoping, duplicate operation IDs, static/parameter route ordering, and unchanged legacy error behavior.

### Frontend and CLI

Complete the master-plan supported user journeys in the PRIVATE frontend copy:

- CIE/Edexcel: course → syllabus → resources → question → answers → supported crops.
- IELTS: book/variant/skill/test → question → grouped answers → accurate audio availability/alignment state.
- TOEFL: set → structured/table question → answers → restricted-source state.
- Materials, syllabuses and timetables: source/layout/version-specific results, null/unknown dates preserved, truthful unavailable cases.
- Coverage, gaps and read-only job diagnostics: scope/denominator/evidence/freshness visible; no generic misleading “all complete”.

If a source does not support a step, present the declared unavailable behavior and preserve the reason; do not manufacture content. Preserve all-season partial failures and distinct syllabus links. Keep source fetching and credentials out of the browser. Support loading/error/empty/partial states, keyboard navigation, links, refresh/back behavior, and narrow screens. Preserve useful current UI rather than replacing it with a generic dashboard.

Run actual browser interactions against private loopback services with synthetic fixtures. Node fetch tests alone are not browser acceptance. Capture screenshots and network/request evidence. Use available browser tooling; if unavailable, record the concrete environment limitation and continue other work. Do not invent screenshots or human acceptance.

Exercise CLI commands for status, configuration, diagnostics, catalog operations and migration planning as required by the master plan. Preserve the real entry-point target `examdata.cli:app`; final original path is `examdata/src/examdata/cli.py`, subject to release-time verification.

## 8. Work package W5 — B08 synthetic migration and restore

Complete a full migration rehearsal with synthetic source stores NOW; real data remains blocked.

1. Inventory the staged storage shapes: raw source ownership, aggregate index, revisions/current pointer, assets, caches, manual decisions and provenance. Do not merge unrelated authorities into one mutable file.
2. Build a copy manifest with exact source/destination paths, hashes, counts, relationships, IDs, evidence labels, and conflict dispositions. Destination must be a new private root. No deletion of originals.
3. Demonstrate repeatable migration, interruption recovery, idempotent retry, collision refusal, and a failed publication leaving the current revision unchanged.
4. Test concurrent publication/pointer swaps, lost-update protection, reader consistency, and restore of the previous pointer. Preserve manual overrides, native ID round trips, answers/assets/regions references and source lineage.
5. Use supported consistent SQLite backup/export methods in synthetic tests. Never extrapolate that copying a live `.db` alone is a safe real backup.
6. Reconcile by system/entity/scope, including missing and rejected records. Matching total row counts alone does not prove correctness.
7. Execute restore and verify restored queries/content/hash identity. A written rollback plan without a restore test is not sufficient.
8. Produce a conditional real-data migration procedure and exact required release/snapshot scope; do not access a real database to fill the gap.

## 9. Work package W6 — B09 actual package/build/install acceptance

Assemble a private release tree from existing staged sources and explicit private packaging configuration. Do not call source hashing “build equivalence.” If the frozen builder writes v1, copy/adapt it to accept a new output root and run the adapted build.

Build an actual wheel/distribution or the repository-appropriate release artifact. Record the command, dependencies, logs, artifact hash, and file inventory. Install into a new private environment; do not modify the existing interpreter environment. Prefer already available/offline dependencies. If a required dependency/tool is unavailable, document the exact missing prerequisite and continue independent work; do not silently replace clean installation with PYTHONPATH imports.

Verify:

- Python package discovery, console entry points, version metadata, schemas/JSON assets, frontend files and declared Node components are present.
- Runtime imports do not depend on the development checkout, `integration-staging` directory name, or test-only guard modules.
- Data/log/temp roots are writable private locations; code can remain read-only where the target platform supports a meaningful test.
- Installed CLI, health, API composition and Node discovery run from three working directories, including a space/non-ASCII path. `PYTHONPATH` must not mask missing package contents.
- Missing component/runtime, timeout, cancellation, child cleanup, queue/output/concurrency limits and error mapping have candidate/installed tests. Use synthetic components honestly until real components are released.
- Binary and frontend assets resolve from the installed layout, not from the source candidate by accident.
- Fixture mode remains explicit; production mode refuses missing real configuration rather than returning synthetic data.

Re-run relevant inherited regressions against the actual new package. If the 887-test suite still targets base `examdata_integration`, label it base staging regression and adapt/copy appropriate tests to exercise the final candidate/installed `examdata.integration`. Never count unrelated base passes as proof of the installed package.

## 10. Work package W7 — close validation and create a private release candidate

Repair C08/C09 without editing frozen artifacts.

1. Copy the full probe/validator to the new run. Update the obsolete coverage pin from a reviewed contract decision and independently computed fixture expectations. Preserve assertions unrelated to the change.
2. Keep an assertion diff. No deleting checks, blanket xfail, expected-red permanent acceptance, catch-and-ignore failures, or manufactured exit zero.
3. Run complete candidate probes, cross-stack checks, Node checks, three-cwd validation, private browser flows, migration/restore and installed-artifact checks. Report distinct scenarios separately from repeated executions.
4. Inspect failures beyond the original review list and repair their root causes. Continue the permitted integration work until all mandatory private rows pass or a concrete environment blocker prevents them. Do not defer a repair merely because it was not one of the original four findings.
5. Freeze one final candidate and one built artifact. Recompute hashes and run required final checks against those exact revisions. Any subsequent implementation change invalidates affected results and requires rerun.
6. Produce explicit current status and consolidated reconciliation maps. Include all earlier B00–B07 changes plus this run, resolving supersession chains; do not deliver only a three-file operations patch as the whole integration.
7. Create separate private rollback, original code-merge, data migration, service cutover, deployment and optional cleanup plans. Each has concrete targets, latest available bases, per-action gates, verify-before-write conditions, fail-on-drift behavior and recovery evidence.
8. Private rollback must be rehearsed on a disposable copy, preserving frozen v1/v2. Restoring v1's expected failing tests demonstrates undoing a private delta; it is not proof of a healthy production rollback.
9. Keep historical docs immutable. Write a new current-status index and staged patches for protected top-level documentation. Apply those patches only if their paths are released later.

At this point, if no original release exists, finish every independent task and provide one concrete release request listing exact remaining paths/actions and already prepared artifacts. Report `private_integration_candidate_ready` only if applicable private mandatory rows pass. Do not repeatedly ask for the same permission, and do not claim full integration complete.

## 11. Conditional real integration — only after explicit release

This section specifies the remaining work; it grants no new permission. Verify each action against the human's actual instruction. Do not fill a release record with inferred or fabricated approval text.

### R0 — Release and refreshed baseline (real B00)

Record instruction text, received timestamp, absolute path scope, constraints, current owner handoff and authorizing actions. Read only released original paths. Rebuild route inventory, source hashes, dependency/entry-point/configuration inventory, data-root mapping and supported features. Preserve Kimi's final work as the baseline. If a path remains owned or ambiguous, keep it protected and continue independent released work.

### R1 — Three-way reconciliation (real B01)

For every intended change compare old private base, current released original, and proposed candidate. Resolve semantically in a private integration copy first. The whole real tree must NOT be forced to equal a synthetic candidate digest. Record add/modify/carry/defer/conflict per file, preserving concurrent unrelated changes. Validate all actual targets, including CLI source layout.

Do not replay stale whole-file replacements or blindly copy the private tree. Before each eventual original write, require the target still matches the newly recorded released baseline; on drift stop that write and reconcile again. Backup current bytes and verify rollback hashes. Preserve source-owned data and Kimi tests/features.

### R2 — Real adapters, configuration, routes and content (real B02–B05)

Wire shared runtime/configuration, actual packaged Node components, real released feature adapters, catalog and routes incrementally. Validate defaults and old aliases. Use approved consistent snapshots for catalog/content tests. Any source request needs upstream authorization; local existing data access needs the agreed data scope. Do not substitute fixtures for real adapter acceptance.

Rebuild the final route compatibility matrix: every current legacy method/path/default/content type/error behavior must be accounted for, including newly added Kimi routes. Validate OpenAPI, operation IDs, static/parameter conflicts and all binary handlers. Check authoritative source layout/version samples for materials/syllabuses/timetables. Visually verify current crop/region examples where required. Preserve unknown dates and unavailable-season evidence.

### R3 — Real frontend/operations and data rehearsal (real B06–B08)

Run complete supported browser journeys against the released local stack and approved data. Validate read-only diagnostics against current real checkpoint semantics without resuming jobs. Rehearse real migration only from approved consistent backups into private destinations; verify per-scope counts, references, quality/provenance and restore. Never delete originals. A real data-root pointer change needs its own authorization.

### R4 — Final freeze and package (real B09)

Freeze reconciled source and approved data revisions. Build a new final artifact from that tree; the private synthetic build cannot stand in for this one. Run full applicable regressions, installed-artifact checks, route compatibility, browser/content acceptance and restore on that exact revision. List every skip and blocker. No mandatory acceptance row may remain unaccounted for.

### R5 — Delivery and optional authorized operation (real B10)

Publish local handoff artifacts and update released documentation. If service/deployment/data cutover was explicitly authorized, execute the named runbook on the named target, verify running version/hash, health and user flows, and retain an operable rollback. Otherwise report `integration_ready_cutover_not_run` and keep the existing service unchanged.

Do not use “all done” to justify source deletion, broad cleanup, CIE resumption or extra upstream crawling. Those are separate optional actions. A cleanup operation needs explicit paths, current acceptance evidence, retention policy and its own authorization.

## 12. Acceptance, stop conditions and final deliverables

### Stop only the affected unsafe/dependent work when

- A frozen hash or fresh target precondition mismatches.
- A protected path/action lacks authorization.
- A live/upstream failure reaches a documented stop condition, including the existing CIE stop/resume policy. Preserve the first failure and do not evade it by retries/source switching.
- A necessary environment capability is unavailable.
- A rollback precondition fails or concurrent edits would be overwritten.

Continue unrelated permitted work. Do not open gates, weaken guards, fabricate data, suppress failures, or overwrite evidence to proceed.

### Required final files under the new run's reports directory

1. `CURRENT_INTEGRATION_STATUS.md`: current state, evidence scope, known gaps, exact next action.
2. `FINDINGS_CLOSURE.md`: C01–C09 plus newly found issues; fix, rationale, tests, residual limitations.
3. `ACCEPTANCE_RESULTS.json` and readable `.md`: every supplied/new criterion, final revision, status, evidence path/hash, and authorization basis.
4. `FINAL_ROUTE_COMPATIBILITY.json` and `.md`: private historical matrix until release; refreshed real matrix after release, explicitly labelled.
5. `CAPABILITY_AND_USER_FLOW_MATRIX.md`: all systems, routes, UI journeys, source/evidence classes and unavailable behavior.
6. `COVERAGE_CONTRACT_DECISION.md`, OpenAPI/schema output and consumer migration note.
7. `BUILD_AND_INSTALL_REPORT.md`, built artifact hashes, component/package inventory, commands and installed import origins.
8. `MIGRATION_AND_RESTORE_REPORT.md`: synthetic and real rows separate.
9. `CONSOLIDATED_MERGE_MAP.json`, `ROLLBACK_PLAN.json`, and action-specific cutover/deployment plans.
10. `AUTHORIZATION_REQUIREMENTS.json`: only actual remaining actions, concrete scopes, dependencies and current permission evidence; no blanket seven-gate requirement.
11. `FINAL_CHANGE_MANIFEST.json`, precise diffs, provenance, commands/transcripts, evidence index, and frozen-input recheck.
12. `FINAL_REPORT.md`: source/artifact/data revisions; new versus inherited tests; distinct versus repeated checks; failures/warnings/skips; original effects actually performed; remaining authorization/environment blockers.

Place readable report/prompt/status links additively under `docs/integration/execution/`. Do not rewrite historical reports or a frozen manifest. Verify all reported paths/hashes resolve and the evidence index matches actual bytes.

### Completion language

- Private-only success: `private_integration_candidate_ready`; real integration remains pending release.
- Released code/package/real acceptance complete but no cutover: `integration_ready_cutover_not_run`.
- Authorized operational target verified: state precisely which target/version is integrated/deployed and what optional actions remain unrun.

Do not conclude with an offer to do the remaining already-authorized work. Do it. Do not stop at a new proposal if real release and required actions have already been explicitly authorized. Conversely, never describe synthetic/private evidence as real integration or deployment. The final report must stand alone and be understandable without reading chat history.
