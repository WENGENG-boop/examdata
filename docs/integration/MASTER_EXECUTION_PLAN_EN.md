# Complete API and Project Integration: Execution Plan

**Version:** 2.0, English executor edition  
**Date:** 2026-10-05, Asia/Shanghai  
**Workspace:** `C:/Users/weo/Desktop/api`  
**Document status:** Plan only. Implementation has not started.  
**Current execution mode:** `PHASE_A_ISOLATED_ONLY`  
**Primary constraint:** Kimi Code is still working in this workspace. Leave its project and running processes alone.

This document supersedes the earlier Chinese integration plan. Follow this document and its companion [executor prompt](EXECUTOR_PROMPT_EN.md). The [project status](../PROJECT_STATUS.md) is historical evidence about the current implementation; it is not permission to modify it.

The instructions below deliberately specify decisions, file boundaries, prerequisites, implementation order, tests, evidence, and stopping conditions. Do not replace them with a different architecture, a shorter pilot, or a generic proposal. If a required fact is unavailable, record it as unknown and continue only with tasks that do not depend on it.

## 0. Read this before executing any command

### 0.1 What the user requested

Integrate the existing APIs and the overall project into a coherent, maintainable system. Preserve existing behavior, expose a consistent new API, unify project configuration and delivery, and accurately report data quality and missing content.

The user also explicitly said that Kimi Code is still modifying one project and that this project must be left alone until Kimi finishes. This restriction has priority over every implementation instruction later in this document.

### 0.2 Evidence about the active work

At the last inspection, the most recently active Kimi session was:

```text
C:/Users/weo/.kimi-code/sessions/wd_api_8f9bde7994a5/
  session_de1b801c-5d3c-454f-bc4f-dc6382e0afca/
```

Its task concerns examination materials and timetables. Recent activity concerned Edexcel historical timetable parsing. The main wire log and files under `tmp_edexcel_tt_probe/` were still changing around 17:27–17:28 on 2026-10-05.

This is evidence of activity at that time, not a permanent statement about which process is running now. Do not infer that the work has finished because a file stops changing or because the process disappears.

### 0.3 Two execution phases

**Phase A: isolated preparation and implementation.** You may work only in the new integration-owned directories below. Existing project files are read-only. Use private fixtures and private copied code. Do not run the existing application or its tests in place.

**Phase B: integration into the real project.** Start only after the human user explicitly says Kimi has finished and the relevant original paths may be integrated. A Kimi log saying “done,” inactivity, a passed test, or your own judgment is insufficient. Human authorization must specify, or clearly include, the paths you will modify.

The release of the Kimi ownership boundary does not automatically authorize live data migration, restarting port 8000, new upstream crawling, deployment, deleting source files, or publishing changes. Those actions have separate gates in this plan.

### 0.4 Phase A write allowlist

Only these newly created paths may be written by the implementation executor:

```text
C:/Users/weo/Desktop/api/integration-staging/
C:/Users/weo/Desktop/api/docs/integration/execution/
```

If either directory already exists, inspect its contents and ownership before using it. Reuse it only if it belongs to this integration task. Otherwise create a unique child directory and record its absolute path. Never erase an existing directory to make the commands work.

The plan, prompt, route baseline, project status, README files, and all existing source and data are read-only inputs during Phase A. Put proposed edits to them in the staging tree, not in their original locations.

### 0.5 Protected existing paths

Everything outside the allowlist is protected. In particular:

```text
examdata/**
frontend/**
ielts-api/**
ielts-data/**
toefl-api/**
cie-location-batch/**
cie-index-batch-2026-10-01/**
cie-question-crops/**
gaokao-feasibility/**
tmp_edexcel_tt_probe/**
tmp_materials_probe/**
.data/**
docs/ielts/**
docs/toefl/**
SESSION_CONTINUATION_PLAN.md
```

The active feature especially includes materials, timetable, research evidence, and related tests. Shared files such as `examdata/src/examdata/api/app.py`, `cli.py`, `pyproject.toml`, configuration, README, API documentation, deployment documentation, and frontend files are protected too. “I am only adding an import” is still a modification.

### 0.6 Actions forbidden during Phase A

1. Do not edit, format, rename, move, delete, restore, reset, stash, stage, commit, or overwrite original project files.
2. Do not kill, pause, restart, signal, reconfigure, or attach a debugger to Kimi or existing services.
3. Do not send instructions to the active Kimi session.
4. Do not change port 8000, port 5188, shared environment files, user-level environment variables, proxy settings, installed packages, or the existing virtual environment.
5. Do not run pytest from the original repository. Its `conftest.py` creates a directory under the original `.pytest_cache` even before ordinary tests execute.
6. Do not import the original application to inspect routes. Configuration and imports can create directories or initialize data.
7. Do not call existing service routes that can fetch upstream data, write caches, or launch subprocesses.
8. Do not execute `build-syllabi.mjs`, refresh tools, batch crawlers, or source verification commands against the live workspace.
9. Do not copy a live SQLite database by copying only its `.db` file. Do not access a live database during Phase A; use synthetic fixtures or already exported immutable evidence.
10. Do not run `git clean`, `git reset --hard`, broad recursive deletion, a blanket formatter, a dependency upgrade, or a lock-file regeneration in the original project.
11. Do not interpret this plan as authorization to resume the stopped CIE batch.
12. Do not automatically promote staging changes after tests pass.

### 0.7 Safe work that can proceed now

- Read source as text and parse it statically.
- Read existing reports and the saved route inventory.
- Build contracts, fixtures, pure mapping functions, provider interfaces, an isolated API application, and test helpers in staging.
- Copy specifically selected inactive source files to staging after checking their before/after hashes. Do not copy or execute the active materials/timetable implementation while it is owned by Kimi.
- Test staged code against synthetic fixtures and copied immutable snapshots.
- Prepare proposed patches and merge instructions without applying them to original files.
- Document all deferred work and continue independent tasks.

### 0.8 Gates must be tracked separately

Create these gate fields in the execution ledger. All start as `false`. Do not change a gate based on your own output or a tool result that merely reports success.

| Gate | What opens it | What it permits |
| --- | --- | --- |
| `original_paths_released` | Explicit human release of Kimi-owned paths after its work is finished | Phase B edits only within the released path scope |
| `real_data_write_authorized` | Explicit instruction permitting a named data migration/write | The specified migration after backup and rehearsal |
| `existing_service_cutover_authorized` | Explicit instruction permitting a named service restart/switch | The specified service operation after a reviewable release is prepared |
| `upstream_requests_authorized` | Explicit scope for live source validation or collection | Only the named sources, identities, and request budget |
| `cie_resume_authorized` | Explicit continuation of the stopped CIE workflow | Resume from its current checkpoint under its original stop rules |
| `remote_deployment_authorized` | Explicit target and deployment instruction | Deployment to that target after release and rollback readiness |
| `original_cleanup_authorized` | Explicitly named original paths and retention decision | Only that cleanup after reference/hash and rollback checks |

For each opened gate, record the human instruction, timestamp, scope, and constraints. `original_paths_released` alone opens none of the other gates. Ordinary staged coding and private tests require no new permission once this executor prompt has been assigned.

### 0.9 Attribute concurrent changes honestly

Kimi may legitimately change original files while you work. A before/after hash difference does not prove that you changed the file, and a matching hash alone does not prove every action was safe. Keep a complete ledger of your own write commands and changed paths. Report unexpected original-file changes as concurrent observations, not as damage to repair. Never restore the earlier hash to make a protection check pass.

If your own command accidentally writes outside the allowlist, stop further dependent actions, record the exact affected path and operation, and tell the user. Do not automatically restore the file: Kimi may have changed it in the meantime. Continue only independent work that cannot worsen the collision.

## 1. Objective and definition of completion

### 1.1 Required user experience

A client should be able to discover an examination system, select a qualification or course, find a paper or test, retrieve questions and answers, obtain necessary images or audio, inspect the syllabus and examination materials, and query a timetable through one coherent service.

Every result must say what it represents, where it came from, which revision it belongs to, whether it is complete, and which aspects have actually been verified. A client must be able to distinguish absent source data, unsupported capability, unprocessed content, restricted access, a temporary failure, and a verified empty result.

### 1.2 Required engineering outcome

- One Python/FastAPI public service, with existing interfaces preserved.
- A new top-level `/api/v2` contract shared by all supported examination systems.
- Existing Node parsers retained behind a controlled runtime interface.
- Central capability and course discovery.
- Explicit component locations, data roots, versions, and configuration precedence.
- A common read model and stable ID mapping without destroying source-specific information.
- One source of truth for frontend resource discovery.
- Reproducible installation, testing, release, backup, and rollback.
- Accurate status and coverage reports generated from evidence.

### 1.3 Separate completion claims

| Claim | Required proof |
| --- | --- |
| Phase A prepared | Staged code, fixtures, contracts, proposed changes, and isolated test evidence exist; original project remains untouched by this executor |
| Engineering integration complete | Phase B merged, all compatibility tests pass, the installed bundle works, frontend flows pass, rollback works |
| Dataset complete | A defined expected manifest has no unexplained content gaps for the stated scope |
| Answers verified | Verification evidence exists at the claimed level for the stated questions |
| Audio aligned | Real alignment evidence exists for the stated question/time windows |
| Deployed | The intended target is running the recorded release and revision, and deployment checks pass |

Never use one claim as evidence for another. In particular, do not call staged work “integrated,” a local service “deployed,” a cache hit “online verified,” or an answer link “officially correct.”

### 1.4 Scope

Include CIE, Edexcel, IELTS, TOEFL, all existing HTTP routes, source-specific CLI functions, paper and question retrieval, answers, crops, assets, audio, syllabuses, tags, examination materials, timetables, coverage, frontend integration, configuration, runtime bridging, packaging, testing, operations, and documentation.

Gaokao remains an experimental source/capability entry until a separate real ingestion and validation workflow exists. AP, SAT, IB, user accounts, paid content acquisition, full OCR remediation, full ASR alignment, and new AI-generated solutions are outside the engineering integration scope.

## 2. Verified baseline and required rechecks

### 2.1 Static route baseline

The saved [route inventory](ROUTE_INVENTORY_CURRENT.json) contains 71 explicit method/path routes read from Python decorators. It is not a live OpenAPI snapshot.

| Module | Prefix | Count |
| --- | --- | ---: |
| `examdata/src/examdata/api/app.py` | root paths | 20 |
| `examdata/src/examdata/api/unified.py` | `/api/v1` | 8 |
| `examdata/src/examdata/api/ielts.py` | `/api/v1/ielts` | 28 |
| `examdata/src/examdata/api/toefl.py` | `/api/v1/toefl` | 8 |
| `examdata/src/examdata/materials/router.py` | `/api/v1` | 4 |
| `examdata/src/examdata/timetable/router.py` | `/api/v1` | 3 |

The list excludes automatic documentation routes and any future dynamically registered routes. The 71-route baseline is a minimum preservation requirement. After Kimi releases the project, compare it with the final source and preserve newly added routes too. Do not force the final project back to 71 routes.

### 2.2 Current implementation facts

1. The main Git repository is `examdata/`; several required components sit beside it.
2. IELTS and TOEFL each spawn a short-lived Node CLI process from their Python gateway.
3. Each gateway has its own semaphore, queue timeout, component discovery, subprocess timeout, and JSON handling.
4. Main configuration is in `core/config.py`, while gateway and security settings also read process environment variables directly.
5. IELTS intentionally has a separate `EXAMDATA_IELTS_DATA_DIR`.
6. TOEFL currently derives its cache directory from its code directory.
7. CIE service indexes have been stored under `.pytest_cache/callable-api`; this must not become a production layout by accident.
8. The frontend has independent source-fetching logic under `/resources` and a limited `/gateway` proxy.
9. Syllabus snapshots exist in the frontend, while specification/tagging capabilities also exist in Python/CLI modules.
10. Current `/api/v1/boards` describes CIE and Edexcel; it is not an exhaustive directory of the entire service.
11. Existing data and document reports have different timestamps. Some older reports contain failures later fixed by another workstream.

### 2.3 Historical data snapshot

These figures guide fixture selection. Recompute before final acceptance; never hardcode them as application logic.

| Area | Recorded state | Important limitation |
| --- | --- | --- |
| Edexcel IAL | 43,856 questions tagged; answer association 88.5% | Tag coverage is not full manual correctness; Arabic scans and new computer-science papers remain gaps |
| CIE | 13,877 discovered papers; 63 service indexes; 19 current visual gates passed | 42 historically cleaned papers need reverification; one index conflict remains |
| IELTS | 6,724 questions; 6,717 answers attached; coverage complete=0 | Missing content/assets/options and incomplete official verification remain |
| IELTS audio | 336 files passed hash checks; 66 verified alignment windows | File integrity and question alignment are different claims |
| TOEFL | 4,417 cached pages; 971 entries reparsed | Online checking and audio checking were samples |
| Timetable | CIE Zone 5 snapshots documented | Edexcel historical timetable work is actively owned by Kimi |
| Gaokao | Downloadable samples found across 31 provinces | This is feasibility evidence, not a complete production question bank |

The recorded CIE stop is `8238/2025/Jun/32`, QP download HTTP 502, with `needs_user_resume=true`. Do not clear this flag or retry upstream as part of integration.

The saved complete pytest log reports 1,179 passed and 6 skipped. This is a historical baseline, not a result for any new code you write.

## 3. Fixed architecture decisions

### 3.1 Keep the current languages

Keep FastAPI/Python as the public HTTP service. Keep working IELTS and TOEFL Node parsers. Do not rewrite all Node parsing in Python. Do not introduce a new frontend framework, microservice platform, message broker, or database engine merely to make the repository look uniform.

Use a modular monolith with controlled Node execution. Introduce a persistent Node worker only if measurements show that short-lived processes are a significant bottleneck after local snapshot reads and batching are implemented.

### 3.2 Keep legacy APIs and add a new version

Preserve root routes and `/api/v1`. Add `/api/v2` for consistent models and errors. Existing `/api/v1/ielts/v2` remains a legacy namespace with its own existing schema; it is not automatically equivalent to top-level `/api/v2`.

Do not change old defaults, status codes, pagination, file formats, or parameter semantics just because the new version is cleaner. Translate through compatibility adapters.

### 3.3 Separate layers

```text
HTTP routes and CLI commands
    -> application services
        -> provider registry and capability dispatch
            -> source-specific repositories / existing parsers
                -> controlled source access and storage

Published catalog and search index
    -> common metadata and stable IDs
    -> references to source-owned content

Batch operations
    -> discovery / download / parse / verify / publish
    -> checkpoints and coverage evidence
```

Routes validate and serialize. Services implement use cases. Providers adapt examination-system differences. Repositories read their own storage. Fetching code owns upstream policy. No frontend component performs its own source scraping after integration.

### 3.4 Preserve source ownership

Do not migrate every source record into one universal table. Keep existing raw data, manual decisions, source evidence, and parser outputs in their source-owned stores. The unified catalog stores identity mappings, searchable metadata, revision references, and quality summaries.

CIE may retain only immutable locations and hashes while downloading originals on demand. IELTS may retain local audio and PDF assets. These are different retention policies and must remain different.

### 3.5 Staged and final module layout

During Phase A, create these modules only inside `integration-staging/src/examdata_integration/`:

```text
contracts/       # models, schemas, identifiers, quality rules
providers/       # protocol, registry, fixture-backed wrappers
services/        # catalog, resources, questions, answers, coverage
runtime/         # configuration, component manifest, Node runner
catalog/         # stable mappings and published read index
api/             # isolated v2 application factory
operations/      # read-only checkpoint adapters and coverage
observability/   # request context and structured events
```

In Phase B, choose exact final module names after checking Kimi's final tree. Prefer equivalent modules under `examdata/src/examdata/`. Keep the existing `adapters/` contract for discovery/download. Do not overload `BoardAdapter` with every new query operation.

## 4. Identity and model specification

### 4.1 Examination system, provider, and source

Use three separate fields:

- `exam_system`: `cie`, `edexcel`, `ielts`, `toefl`, or `gaokao`.
- `provider_id`: a concrete implementation, such as `edexcel_db` or `ielts_aggregate`.
- `source_id`: the original publisher/site/resource source.

Also retain `qualification`, `course_id`, `native_subject_code`, and specification revision where applicable. Never identify a provider solely by a hostname or call all IELTS content CIE because an IELTS native ID begins with `cambridge:`.

### 4.2 Stable ID rules

Implement an explicit mapping registry. Public IDs must contain URL-safe characters. Use a fixed type prefix and a deterministic digest of a canonical native identity, for example `q_<digest>` or `container_<digest>`. Record the full canonical identity and enforce uniqueness. Specify the canonicalization algorithm and digest length in a decision record before use.

Rules:

1. Never generate a new random ID on every rebuild.
2. Never use a database row number alone as a cross-system public ID.
3. Never include mutable question text in the logical identity.
4. Normalize aliases before computing the ID.
5. Preserve native question IDs and old integer IDs as aliases.
6. Store content revision separately from logical identity.
7. When a parser splits or merges a question, use explicit lineage and new identities where necessary.
8. Detect hash collisions by comparing canonical identities; do not assume they are impossible.
9. Round-trip mappings must recover the exact native locator needed by the provider.
10. Do not make title similarity or semantic similarity an identity-matching rule.

### 4.3 Native identity requirements

| System | Required native identity |
| --- | --- |
| CIE | qualification, subject, year, season, component/paper, variant if distinct, exact QP/MS hashes for a location revision |
| Edexcel | qualification, specification generation, unit/component, series, native paper/document revision |
| IELTS | collection/book, edition when known, variant, skill, test, section, native question key |
| TOEFL | source collection, Official/TPO/free-jj identity, set, section, native hash/qid |
| Gaokao | paper family, year, subject, applicable provinces, source/revision; shared papers must not be duplicated per province |

Unknown values remain null or explicitly unknown. A TOEFL set number or IELTS book number must never be converted into a fictional examination date.

### 4.4 Required entity models

| Entity | Required content |
| --- | --- |
| ExaminationSystem | identifier, names, aliases, qualifications, capabilities, availability, links |
| Course | stable ID, native code, qualification, names/aliases, specification version, applicable years, source references |
| Syllabus | course reference, title, version, applicability, document resources, official/source classification |
| Container | kind=paper/test/set/book, native identity, sections, resources, question references, revision and coverage |
| Question | stable/native IDs, container, number path, parent/group, type, stem, options/table, marks, required assets, answers, quality |
| Answer | original value, normalized value, alternatives, ordering/group rule, matching method, verification, source, conflicts |
| Region | document role/hash, page, bbox, coordinate system, rotation transform, evidence status |
| Asset | media type, byte size, hash, storage mode, availability, content link, Range capability, revision |
| Tag | scheme/version, code, parent, label, specification reference, assignment method/confidence/review |
| Material | kind, applicability, candidate-facing status, standalone/embedded/in-paper access mode, resources |
| TimetableEvent | system, qualification, zone, course/component, date, session, timezone if known, duration, source/revision |
| TimetableWindow | original text, parsed start/end if supported, parsing status, components, source/revision |
| Coverage | explicit scope/denominator, observed/excluded/unknown/missing/partial/verified counts, computed_at, evidence |
| JobStatus | scope, input revision, stage, counters, stop reason, resume requirement, output/evidence references |

### 4.5 Question types and answers

Support the native structures for single choice, multiple choice, table choice, matching, fill-in, short answer, essay, speaking, diagram labels, and unknown types. Use a discriminated type-specific payload where needed. Do not flatten a TOEFL table into an empty `options` array and then claim completeness.

IELTS rules:

- Preserve question 41 where it exists.
- Preserve missing answer slots; do not call `filter(Boolean)` before assigning numbers.
- Preserve “in any order” and grouped answer semantics.
- Preserve Academic/General/shared distinctions.
- Preserve unresolved identity and edition conflicts.

Edexcel/CIE rules:

- Preserve parent/child numbering and multiple regions per question.
- Report answer resolution as exact, ancestor, or descendants where applicable.
- Keep mark-scheme evidence separate from an inferred concise answer.
- Preserve official/manual/generated content as different classes.

For all systems, conflicts must return candidate values and evidence. A manual adjudication may select a preferred answer without deleting the original source answer.

### 4.6 Quality dimensions

Do not create one misleading `verified=true` field. Use independent dimensions:

```json
{
  "content": "partial",
  "answer_presence": "present",
  "answer_verification": "source_verified",
  "assets": "external_only",
  "audio_integrity": "hash_verified",
  "audio_alignment": "unverified",
  "region_verification": "not_applicable",
  "gaps": [{"code": "missing_options", "scope": "question"}]
}
```

Define allowed enum values per dimension. Define which evidence permits each transition. Do not infer an official verification state from agreement between two unofficial sources. A hash check proves file identity/integrity, not correct audio-question association. A source page returning 200 proves neither content validity nor completeness.

### 4.7 Completeness calculation

Implement type-specific completeness rules using required fields and the expected manifest. An essay may legitimately have no multiple-choice options. A diagram-label question requiring an image is incomplete if that image is missing. A table-choice question requires columns, rows, and the applicable answer structure.

Expose both raw dimension counts and a derived status. Unknown expected coverage cannot produce a percentage. Exclusions require reasons and remain visible. Do not average unrelated CIE, Edexcel, IELTS, and TOEFL percentages into a single project completion percentage.

## 5. API contract and complete endpoint migration

### 5.1 Common JSON envelope

Use this shape for new v2 JSON responses. It is a proposed contract, not an existing endpoint response:

```json
{
  "schema_version": "examdata.v2/1",
  "request_id": "opaque-request-id",
  "data": {"items": []},
  "meta": {
    "dataset_revision": "published-revision",
    "retrieved_at": "ISO-8601 timestamp",
    "pagination": {"limit": 50, "next_cursor": null},
    "completeness": "partial",
    "warnings": [],
    "providers": []
  },
  "error": null
}
```

On failure, use `data=null` and `error={code,message,retryable,details}`. Keep public details free of local absolute paths, credentials, raw stderr, and internal stack traces. Link request IDs to private logs.

### 5.2 Error mapping

| HTTP | v2 meaning | Example |
| --- | --- | --- |
| 200 | Successful result, including explicitly partial or genuinely empty lists | One season failed but other seasons returned resources |
| 400 | Malformed request syntax where framework-level parsing cannot apply | Invalid encoded cursor |
| 401/403 | Authentication/access policy | Missing API key; restricted resource |
| 404 | Known requested identity/resource absent | A specific uncollected native item |
| 409 | Identity/revision/hash conflict | PDF changed after location indexing; stale cursor revision |
| 410 | Previously recorded asset no longer available | Local artifact lost with no valid retrieval option |
| 413 | Resource/response budget exceeded | Too many or too-large crop outputs |
| 422 | Invalid/unsupported parameter combination | TOEFL filter requiring an unavailable exam season |
| 429 | Rate limit | Shared source quota exhausted |
| 502 | Invalid/failing upstream response | HTML maintenance page instead of expected content |
| 503 | Required component unavailable or queue full | Missing Node component; bounded queue exhausted |
| 504 | Operation timed out | Runner or source deadline expired |
| 500 | Unexpected internal error | Logged exception, public message sanitized |

For multi-provider requests, return provider-level results. If at least one provider succeeds, return partial data with warnings. If all requested providers fail, return an error, not an empty 200 response. Define deterministic precedence for mixed failures and retain every provider error in sanitized details.

Legacy routes keep their original behavior until a separately approved breaking change. For example, do not automatically change a legacy `200 + ok:false` into a different HTTP status without a compatibility decision.

### 5.3 Binary response rules

- Return actual bytes for PDF, PNG, audio, and ZIP content.
- Do not wrap bytes in the JSON envelope.
- Include content type, safe content disposition, request ID, revision, and validated ETag/hash metadata.
- Support Range only on implementations that actually satisfy 206/416 semantics.
- Define HEAD and conditional request behavior and test it before advertising support.
- Use streaming for large files; enforce total byte/time limits.
- Base64 JSON is optional compatibility behavior for bounded small outputs.
- Release temporary files and subprocesses on success, timeout, client disconnect, and cancellation.
- Never expose arbitrary filesystem paths or implement an unrestricted `?url=` proxy.

### 5.4 Proposed v2 routes

Implement routes in this order. A returned link must lead to an implemented route; omit unsupported links and expose the missing capability instead.

| Route | Required behavior |
| --- | --- |
| `GET /api/v2/info` | Service/schema/component versions and capability links |
| `GET /api/v2/exam-systems` | All supported/experimental systems and availability |
| `GET /api/v2/providers` | Public provider capabilities and limitations |
| `GET /api/v2/courses` | Filter by system/qualification/query/specification version |
| `GET /api/v2/courses/{id}` | Course identity, versions, availability, links |
| `GET /api/v2/syllabuses` | Course/version/exam-year filtering without invented applicability |
| `GET /api/v2/syllabuses/{id}` | Syllabus metadata and source evidence |
| `GET /api/v2/syllabuses/{id}/content` | Controlled original-document retrieval |
| `GET /api/v2/containers` | Papers, tests, sets, and books using their real identity kinds |
| `GET /api/v2/containers/{id}` | Sections, resources, quality, and revision |
| `GET /api/v2/containers/{id}/resources` | QP/MS/ER/GT/insert/audio resources with correct applicability |
| `GET /api/v2/containers/{id}/questions` | Native question order and hierarchy, stable pagination |
| `GET /api/v2/resources` | Unified discovery; snapshot/live mode only where supported |
| `GET /api/v2/resources/{id}` | Metadata, source, freshness, access state |
| `GET /api/v2/resources/{id}/content` | Validated binary content |
| `GET /api/v2/questions` | Cross-system search with capability-aware filters |
| `GET /api/v2/questions/{id}` | Complete available question structure and explicit gaps |
| `GET /api/v2/questions/{id}/answers` | Candidates, provenance, resolution method, verification |
| `GET /api/v2/questions/{id}/regions` | QP/MS locations tied to exact documents |
| `GET /api/v2/questions/{id}/crop` | Bounded ephemeral crop; hash conflict is 409 |
| `GET /api/v2/questions/{id}/audio` | Audio association and alignment evidence, not implied accuracy |
| `GET /api/v2/assets/{id}` | Asset metadata |
| `GET /api/v2/assets/{id}/content` | Safe content serving and declared Range support |
| `GET /api/v2/tags` | Scheme/version/course hierarchy |
| `GET /api/v2/tags/{id}/questions` | Tag lookup with question/answer links |
| `GET /api/v2/materials` | Examination materials with access mode and applicability |
| `GET /api/v2/materials/{id}` | Material details and versions |
| `GET /api/v2/materials/{id}/content` | Standalone content only when it actually exists |
| `GET /api/v2/timetables` | Available/unavailable seasons with evidence |
| `GET /api/v2/timetables/events` | System/qualification/zone/date/component/session filters |
| `GET /api/v2/timetables/windows` | Raw and parsed date windows, null for unknown boundaries |
| `GET /api/v2/coverage` | Published coverage snapshot; no automatic whole-source crawl |
| `GET /api/v2/gaps` | Searchable gap records with evidence and status |
| `GET /api/v2/jobs/{id}` | Authorized, sanitized read-only job status |

Root legacy similarity, sampling, taxonomy, provenance, review, generated-answer, monitoring, and sync-status routes also require explicit migration decisions. Keep them working. Add v2 equivalents only where the provider supports them. Do not claim IELTS/TOEFL similarity or generated solutions merely because a route exists for another system.

### 5.5 Exhaustive compatibility worksheet

Create one row for every route from `ROUTE_INVENTORY_CURRENT.json`, then add any routes discovered in Kimi's final tree. Required columns:

```text
method, legacy_path, source_file, handler, native_parameters,
legacy_defaults, legacy_success_shape, legacy_error_shape,
binary_behavior, side_effects, provider, v2_target,
compatibility_strategy, fixture_ids, test_ids,
status, evidence_path, deferred_reason
```

Allowed statuses are `not_started`, `fixture_ready`, `staged_pass`, `merged_pass`, `deferred_active_owner`, `blocked`, and `not_applicable_with_reason`. Every missing row fails acceptance. A family-level summary is not a substitute for this worksheet.

### 5.6 Legacy families that must not be forgotten

- All 20 routes defined in the original `app.py`, including governance and asset routes.
- All eight routes in `unified.py`, including CIE schema/index/indexed-crop routes.
- Every IELTS source route: cam21, ito, iprog, zhan, PDF/LFS, scripts, audio, enriched reading, aggregate, coverage, and the nested v2 routes.
- All eight TOEFL routes, including free/locked jj handling and URL-based detail validation.
- All materials and timetable routes, after the active owner releases them.
- Frontend `/resources`, `/gateway`, catalog and syllabus behavior.
- Existing Node CLI entry points and Python CLI commands used by documentation or automation.

### 5.7 Pagination and filtering

Default new v2 list limit is 50; initial maximum is 200 unless a route explicitly documents a justified different bound. Cross-system search uses a published aggregate index and deterministic sorting. Do not concatenate provider pages and call that stable global pagination.

Cursor payloads bind query, sort, revision, and last key. Validate cursor integrity and length. Keep a compatible published revision available for the expected cursor lifetime; if unavailable, return a conflict with restart instructions.

Reject filters a provider cannot interpret. Do not silently ignore a year filter for TOEFL. Preserve partial season aggregation: one failed season does not hide successful seasons, and all failed seasons do not become an empty success.

## 6. Runtime, configuration, and source access

### 6.1 Configuration precedence

Use a single resolved configuration object:

```text
explicit allowed command argument
  > process environment
  > explicitly selected configuration file
  > deployment component manifest defaults
```

Resolve paths once to absolute paths. Record each path's role. Preserve existing environment aliases with a documented deprecation warning. Conflicting aliases must produce a clear error or an explicitly documented precedence, not an accidental directory choice.

Do not mutate user-level environment variables. In tests, pass environment values to a private child process. Never point a test process at the original development database.

### 6.2 Existing settings to preserve

Include the current database/data root, Node executable, IELTS component/data directory, IELTS concurrency/queue/timeout, TOEFL component/concurrency/queue/timeout, API key, CORS, frontend upstream, and frontend port settings.

Proposed new settings include component manifest, CIE index root, TOEFL data root, catalog root, operations root, network mode, runner output budget, crop budget, and total response budget. Do not document these as usable until code reads them and tests prove their precedence.

Separate configuration parsing from directory creation. A read-only `doctor` or module import must not create production directories or silently initialize an empty database.

### 6.3 Component manifest

For each component record name, version, source revision/hash, code location, runtime, entry point, supported commands, input schema, output schema, environment allowlist, required data roots, read/write policy, and health probe.

Production component discovery must not depend on `parents[4]`, the current working directory, or unrelated developer folders. The installed bundle must contain every enabled runtime component.

### 6.4 Shared Node runner

Implement the runner in staging with fake child scripts first:

1. Validate component and command against a whitelist.
2. Invoke an argument array with no shell interpolation.
3. Set cwd to the private or installed component directory.
4. Pass only approved environment variables and explicit data roots.
5. Apply bounded queue time, process time, stdout bytes, stderr bytes, and concurrency.
6. Require a single valid JSON result on stdout; keep logs on stderr.
7. Classify missing component, missing runtime, startup failure, timeout, cancellation, nonzero exit, invalid JSON, and business failure separately.
8. On timeout/cancellation, terminate and wait for the process tree as supported by the platform; verify no orphan remains.
9. Redact stderr before public responses.
10. Avoid one subprocess per item in a list; use batch commands or published local snapshots.

A process-local semaphore is not a global limit across Uvicorn workers. Initial deployment uses one worker. Enable multiple workers only after shared source limiting and concurrent publication locks are implemented and tested.

### 6.5 Network policy

Phase A is offline. Use fake HTTP transports and localhost-only test servers on private ephemeral ports. A request budget of zero must actually prevent network calls; merely setting an unused environment variable is not sufficient.

Each real source later declares allowed hosts, protocols, redirects, access restrictions, proxy behavior, minimum interval, concurrency, timeout, maximum bytes, retries, stop conditions, and caching policy. Validate every redirect, not only the first URL.

Keep strict CIE batch stop rules workflow-specific. A normal query for a missing resource can return 404 without globally halting unrelated reads. A strict batch job receiving one of its stop conditions must persist state and stop new upstream requests.

Do not automatically switch sources, proxy nodes, credentials, or mirrors after a stop. Preserve the loopback proxy fix while testing public-source proxy behavior independently.

## 7. Storage, revision publication, and migration

### 7.1 Logical deployment layout

```text
<data-root>/
  examdata/       # primary database and source-owned artifacts
  cie-indexes/    # immutable locations and verification manifests
  ielts/         # existing IELTS layout and revisions
  toefl/         # externalized cache and manifests
  catalog/       # mapping registry, search index, published revisions
  operations/    # runs, checkpoints, errors, coverage snapshots
  tmp/           # bounded run-specific temporary files
```

This is a logical target. Do not move current directories during Phase A. Phase B initially points the manifest at approved current locations, then migrates one root at a time after a reversible rehearsal.

### 7.2 Aggregate read index

Default to a separate SQLite catalog database for mappings and search metadata, unless a measured fixture-scale implementation proves a simpler JSON snapshot sufficient for the full expected scope. Keep this decision in an architecture record. Do not modify the primary schema merely to experiment with the catalog.

Store provider/native locator, stable ID, course/container, searchable fields, source revision, quality summary, and lineage. Store references rather than duplicating every raw document and audio file.

### 7.3 Revision publication transaction

1. Select fixed input revisions.
2. Build into a run-owned staging directory.
3. Validate schema, identities, references, counts, and file hashes.
4. Generate a previous/new revision diff.
5. Reject unexplained removals or quality upgrades without evidence.
6. Publish a new immutable revision.
7. Atomically replace the current pointer using a tested Windows/Linux-safe method.
8. Keep the previous revision available for rollback and active cursors.
9. If any validation fails, leave the current pointer unchanged.

Do not require symbolic-link privileges on Windows. Use a small versioned pointer file with atomic replacement if appropriate. Test concurrent publishers with compare-and-swap semantics so a stale builder cannot overwrite a newer current revision.

### 7.4 Cache classes

Distinguish immutable raw evidence, parser-derived cache, published indexes, manual decisions, negative cache, and temporary files. Give each class an owner, retention policy, mutability rule, and cleanup rule.

Cache keys include provider, source, canonical identity, parser/schema version, and relevant input revision. Invalid hosts cannot share a cache key with a legitimate source merely because their URL paths match.

Write through temporary files and atomically publish only after validation. Never cache an HTML maintenance page as valid question content. Cache freshness and content verification are independent metadata.

### 7.5 Database migration gate

Database migration is Phase B only and requires an approved target and a separate explicit write/cutover authorization. Before migration:

- Determine the actual configured database path and whether WAL is active.
- Use SQLite's backup API or an approved consistent backup method.
- Never copy only a live `.db` file and ignore WAL.
- Rehearse on an isolated backup.
- Check integrity, foreign keys, row counts, source references, manual/official decisions, tags, regions, and provenance.
- Preserve old IDs or alias mappings.
- Record split/merge lineage and unresolved mapping conflicts.
- Freeze writes or capture/apply a proven delta before cutover.
- Do not restore an older database over new writes without a recovery plan.

PostgreSQL is a separate future gate. SQLite tests do not prove PostgreSQL savepoint, locking, ordering, or migration correctness. Mark PostgreSQL acceptance `not_run` if no suitable isolated database is available.

## 8. Source-specific implementation requirements

### 8.1 CIE provider

Read immutable external indexes without downloading PDFs. Expose discovered, indexed, imported, service-identical, and visually verified states separately. Historical `cleaned` does not imply a current visual gate passed.

For a real crop, retrieve the approved original, verify its exact hash, apply the recorded coordinate/rotation convention, render within the request budget, and dispose of temporary files. A changed original returns 409. Do not silently re-index or overwrite an index.

Keep `0472/2026/Jun/41` as a recorded conflict until an evidence-backed decision resolves it. Keep the stopped `8238/2025/Jun/32` job stopped. Fixture cases must include a known indexed paper, a non-mathematics paper, multiple pages, rotation, QP-only, MS-only, missing index, hash mismatch, and crop budget rejection.

Do not process all 13,877 papers as part of infrastructure integration. That remains a separate dataset workstream.

### 8.2 Edexcel provider

Reuse query, specification, tagging, and answer-resolution services. Do not duplicate SQL in route handlers. Preserve qualification and specification generation so IAL and IGCSE data do not become one indistinguishable subject.

Expose exact/ancestor/descendants answer resolution and source mark-scheme references. Differentiate no matching MS, empty MS, unparsed MS, and failed answer association. Keep provenance and protected manual/official records intact.

Represent unreadable Arabic scans and the new computer-science course without papers as gaps. Include a real tag-query fixture and a parent/child answer fixture.

### 8.3 IELTS provider

Prefer the existing published normalized revision and `ielts.v2/1` outputs. Translate into the new schema without changing native identities. Keep legacy source-specific APIs.

Retain special question numbering, answer alternatives, missing slots, raw source IDs, variant, and edition uncertainty. Keep the book-11 Q24 conflict and unresolved pte-4L provenance unresolved unless a separate evidence task actually resolves them.

Audio responses distinguish a linked full recording, an unverified time window, and a verified alignment. Do not provide a seemingly precise auto-seek offset when only identity association exists. Verify Range behavior against private assets before exposing it through v2.

### 8.4 TOEFL provider

Preserve strict KMF URL validation, per-hop redirects, content validation before cache publication, table-choice rows/columns, and multiple-selection information. Public v2 endpoints prefer resource IDs rather than caller-provided URLs.

Keep Official/TPO/free-jj identities distinct. Restricted jj entries remain metadata-only. Unknown exam dates remain null. Do not describe Official <=54 as complete modern TOEFL coverage or claim support for the complete 2026 format.

Externalize cache paths only in a staged implementation first. Reparse copied caches offline and compare semantic output. Do not use a full online refetch as a substitute for a migration test.

### 8.5 Materials, syllabuses, and timetables: active-owner rule

During Phase A, define only contracts, fixture examples, expected interfaces, and deferred integration rows. Do not copy, execute, patch, format, or refactor Kimi's active modules or probe files.

After human release:

1. Read Kimi's final report and final source.
2. Rebuild the route/component inventory.
3. Compare final code with the planning snapshot.
4. Discard staged assumptions that conflict with valid final behavior.
5. Adapt the final implementation without replacing it with an older copy.
6. Run its final tests in an isolated environment and preserve its source evidence.

Syllabuses preserve specification versions and examination-year applicability. Materials distinguish standalone, embedded, and in-paper resources. A periodic table embedded in a QP must not be advertised as an independent PDF. ER/GT resources may apply to a season or whole qualification, not one paper.

Timetables preserve zone, qualification, session, date windows, raw text, parser status, source hash, and revision. Unknown AM/PM remains null. Do not invent a local clock time from a session name. Snapshot-backed endpoints must say they are snapshots rather than live refetches.

### 8.6 Gaokao

Register as experimental with known sample evidence. Preserve province applicability and shared-paper identity. Do not count one national paper repeatedly as separate content for every province. Do not claim complete ingestion, question parsing, answers, or public API readiness based on the feasibility report.

## 9. Frontend, CLI, and documentation requirements

### 9.1 Frontend

Keep the existing visual design and Chinese subject matching. Do not introduce a framework migration. Add an API client layer in the staged copy; later move all source discovery into the backend service.

Preserve explicit course selection over ambiguous aliases, all-season aggregation, partial failures, source-not-provided states, source/snapshot labels, login-restricted filtering, and syllabus links.

Provide system-appropriate controls: subject/series for CIE and Edexcel, book/variant/skill/test for IELTS, collection/set/section for TOEFL. Show quality states relevant to the user without exposing internal runtime jargon.

API keys remain server-side. The gateway remains an allowlisted proxy, never an open proxy. Use a reversible feature flag for v2 client adoption.

### 9.2 CLI

Preserve existing Python and Node entry points. Add unified commands only after scanning for command-name conflicts. Keep query commands separate from refresh/write commands. `--json` writes machine-readable results to stdout; logs go to stderr.

A future `doctor` command is offline and read-only. A future catalog build or refresh command must explicitly say what it writes, which source policy it uses, and how resume/dry-run/request limits work. Do not run a command mentioned as a future target before implementing it.

### 9.3 Documentation

Update shared documentation only after Phase B release. During Phase A write proposed versions under staging.

Final documentation must include current status, v1 compatibility, v2 reference, configuration precedence, component installation, data layout, identity and quality definitions, source limitations, exact test commands, release/rollback steps, and runnable PowerShell/Python/Node examples.

Generate endpoint tables from OpenAPI and coverage summaries from published revisions. Preserve historical logs with timestamps. Do not rewrite historical output to look like a fresh test.

## 10. Operations, observability, and deployment

### 10.1 Job state model

```text
queued -> running -> succeeded
                 -> partial
                 -> stopped_requires_resume
                 -> failed
                 -> cancelled
```

Include run ID, scope, component, input revision, parser/schema/config versions, stage, counters, current identity, last successful step, stop details, resume requirement, authorization reference, output manifest, and evidence paths.

Initially adapt existing checkpoints read-only. Do not overwrite CIE and IELTS checkpoints with a generic format. Record observation time and source. Latest authoritative checkpoint/output revision outranks stale summaries and old plans.

### 10.2 Health and logs

Use request IDs across HTTP, provider, runner, and source events. Log status, duration, queue wait, cache behavior, byte counts, revisions, and sanitized error codes. Do not log full question content, credentials, private paths in public responses, or arbitrary stderr.

Liveness checks only the process. Readiness checks required enabled components and readable published data without crawling sources. Optional TOEFL unavailability must not automatically disable unrelated CIE reads; define required components in the deployment profile.

### 10.3 Limits

Enforce request time, source time, queue length, concurrency, stdout/stderr size, PDF size, crop count, aggregate response bytes, ZIP limits, and temporary disk limits. Test cancellation cleanup and repeated failures.

Treat candidate latency targets as test objectives, not current facts: local catalog p95 <=300 ms and local question metadata p95 <=500 ms at agreed hardware/revision/concurrency. Record hardware and workload before interpreting results. Upstream downloads use explicit deadlines rather than an invented guaranteed latency.

### 10.4 Release bundle

The release must contain the Python wheel, required Node components, frontend assets, contracts/schemas, component manifest, actual dependency versions, configuration example, migration tools, smoke checks, and rollback instructions. Keep business data and secrets out of the code package.

Test installation in a clean private directory, including execution from another cwd and a path containing spaces/non-ASCII characters. Editable installation success is insufficient.

No remote deployment is authorized by the planning task. Prepare the deployable bundle and report remote checks as `not_run` until a real target and authorization exist.

## 11. Phase A: exact ordered work packets

Do these in order. For each packet, produce the listed evidence and update the execution ledger before proceeding. Do not mark a packet passed based only on code review.

### A00 — Establish the protected boundary

**Read:** Sections 0–2 and the saved project status.  
**Write:** `docs/integration/execution/ownership.json`, `execution-ledger.json`, and an initial report.  
**Steps:** Record mode `PHASE_A_ISOLATED_ONLY`; record the two allowed output roots; record the active Kimi session as evidence; record all external gates as false; list prohibited operations.  
**Pass:** Every subsequent command has an allowed working directory and write destination.  
**Fail action:** If output-directory ownership is uncertain, create a unique child instead of overwriting it.

### A01 — Read-only inventory

**Read:** The 71-route JSON, route source as text, CLI registrations, frontend network call sites, package metadata, configuration definitions, and reports.  
**Write:** Component inventory, route compatibility worksheet, CLI inventory, configuration matrix, and data-root role inventory under `execution/`.  
**Steps:** Use static parsing. Do not import the original application. Record source file hashes and observation time. Identify active-owned files and mark their mappings deferred.  
**Pass:** Every baseline route has a row; all source systems and frontend source calls are represented.  
**Fail action:** Record unknowns. Do not fill gaps by guessing live behavior.

### A02 — Build the private staging harness

**Write:** A minimal staged package, tests directory, fixture directory, private runtime/data directories, and test configuration.  
**Steps:** Use the existing Python executable without installing into its venv; direct bytecode, pytest cache, HOME-like application state where needed, and temporary files into staging. Disable real network transports. Use only private subprocess cwd and data paths.  
**Pass:** A fixture test can run and every created file is inside the allowlist. A deliberate prohibited source-network call fails.  
**Fail action:** Fix the harness before importing copied business modules.

**Additional isolation checks:** The existing virtual environment may contain an editable installation pointing to the original `examdata/src`. Inspect module resolution before importing any application module. Assert that every application module loaded during staged tests has a `__file__` under the approved staging tree; normal standard-library and third-party dependency modules may come from the existing interpreter installation. Reject symlinks/junctions or resolved paths that lead back to original application code. For copied Node code, resolve local imports and component paths and reject imports that escape staging. This check must fail deliberately when a forbidden original module or data path is supplied.

A copied test is not automatically safe: inspect its fixture setup, subprocess cwd, module imports, `.env` lookup, cache paths, and teardown first. Never copy the original `conftest.py` and assume it isolates itself correctly in a new location. Build an explicit staging test configuration.

### A03 — Capture safe fixtures

**Read:** Existing immutable JSON evidence and selected inactive source files.  
**Write:** Fixture provenance manifest and copied fixtures under staging.  
**Steps:** Record source path/hash, before-copy hash, destination hash, after-copy hash, scope, and license/access notes where already present. Use small representative artifacts. Do not copy credentials, original databases, entire caches, or active-owner modules.  
**Pass:** Stable copies match and have provenance. Synthetic fixtures are labeled synthetic.  
**Fail action:** If hashes change, mark that source unstable and defer it; do not repeatedly copy an actively changing file.

### A04 — Freeze contracts and identity rules

**Write:** Contract models, JSON schemas, identity canonicalization decision, quality transition table, and examples.  
**Steps:** Implement the models in Section 4. Define required/optional fields, enum values, null behavior, public ID mapping, collision checks, and versioning.  
**Tests:** Round-trip native IDs, aliases, IELTS Q41, grouped alternatives, parent answers, table choices, unknown dates, conflicts, required images, and lineage.  
**Pass:** No source-specific information is lost and identity is deterministic.

### A05 — Implement the provider protocol and registry

**Write:** Protocol, capability model, fixture providers, dispatch service.  
**Steps:** Define operations for discovery, courses, containers, questions, answers, resources, assets, regions, tags, and coverage. Unsupported operations return a typed unsupported result. Capability filtering precedes dispatch.  
**Tests:** Unsupported filters, alias routing, unavailable optional provider, multiple-provider partial success, all-provider failure.  
**Pass:** No fake empty successes, no accidental CIE routing for IELTS IDs.

### A06 — Implement configuration and the runner

**Write:** Resolved configuration, component manifest validator, fake Node CLI scripts, bounded runner, private doctor output.  
**Steps:** Follow Section 6; test fake scripts before copying any parser. Do not execute original Node components.  
**Tests:** Missing executable, spaces in paths, invalid JSON, multiple JSON values, nonzero exit, stderr redaction, queue full, output overflow, timeout, cancellation, process cleanup, environment precedence.  
**Pass:** Every failure has a stable internal classification and cleanup evidence.

### A07 — Stage Edexcel and CIE read adapters

**Write:** Mapping wrappers against private fixtures or private schema fixtures.  
**Steps:** Preserve native identity, hierarchy, answer resolution, provenance, and region hashes. Do not access the original database or resume CIE.  
**Tests:** Exact/ancestor/descendants answers, missing MS, missing index, hash-conflict mapping, multi-region and rotated-page metadata.  
**Pass:** Contract outputs are semantically equal to fixture inputs. Real database/crop acceptance remains deferred.

### A08 — Stage IELTS and TOEFL read adapters

**Write:** Wrappers over copied immutable JSON and, if safe, copied inactive parser code.  
**Steps:** Keep cache/data roots private. Preserve native errors and all quality distinctions. Use fake fetch or offline transport.  
**Tests:** Q41/missing slots, variants, unresolved identities, answer conflicts, audio alignment state, TOEFL table rows, multiple choice count, locked jj, unknown dates, bad cache content.  
**Pass:** No source request occurs and no data is silently upgraded to verified.

### A09 — Stage catalog and revision publication

**Write:** Private mapping/catalog store, builder, immutable revision manifests, pointer publisher.  
**Steps:** Build only from staged fixtures. Validate identities/references, generate diffs, publish atomically, retain previous revisions.  
**Tests:** Duplicate native IDs, collision detection, incomplete references, failed publication, concurrent publishers, stale current pointer, rollback, stable cursor references.  
**Pass:** Failed builds cannot change current and valid builds are reproducible.

### A10 — Stage the isolated v2 API

**Write:** Application factory under the staged package; do not import the original `app.py`.  
**Steps:** Add endpoints in Section 5.4 as capabilities become available. Materials/timetable use clearly labeled test fixtures only; real integration remains deferred.  
**Tests:** Response models, error mapping, pagination, partial success, missing/restricted/conflicting items, link resolution, maximum limits.  
**Pass:** OpenAPI and runtime responses agree; no link claims an unavailable production feature.

### A11 — Stage binary handling and request budgets

**Write:** Private asset/crop transport and budget helpers.  
**Steps:** Use synthetic PDF/image/audio fixtures or copied approved small immutable samples. Validate paths and media types.  
**Tests:** 200/206/416, ETag where implemented, path traversal, Windows drive/UNC paths, wrong media type, total response size, disconnect, temporary-file cleanup.  
**Pass:** Binary content and headers are correct and resource limits are enforced.

### A12 — Prepare legacy compatibility adapters

**Write:** Proposed wrappers and fixture-based tests in staging, plus the per-route worksheet.  
**Steps:** Preserve legacy defaults and payloads. Mark active-owned and unavailable-real-data cases deferred. Do not monkeypatch original files.  
**Pass:** Each of 71 baseline rows has a test or a specific deferred dependency; fixture passes are labeled `staged_pass`, never `merged_pass`.

### A13 — Stage the frontend API client and operations views

**Write:** A copied frontend proposal, client module, fixture server, checkpoint readers, coverage fixtures.  
**Steps:** Preserve original UX. Replace source requests only in the copy. Do not start on 5188 or talk to 8000. Do not load or change Kimi-owned timetable code.  
**Tests:** Subject aliases, all seasons with partial failure, unavailable data, correct system-specific selectors, source quality display, no exposed key.  
**Pass:** Fixture browser flows work and are explicitly labeled as staged fixture validation.

### A14 — Prepare packaging and merge proposals

**Write:** Proposed component release manifest, staged documentation, a file-by-file patch plan, migration/rollback rehearsal against private fixtures.  
**Steps:** Identify every eventual original target path and the base hash used to prepare it. Avoid a whole-tree replacement patch. List active-owner deferred files separately.  
**Pass:** A reviewer can see exactly what will change and how each change can be reversed.

### A15 — Finish Phase A and wait safely

**Write:** `PHASE_A_REPORT.md`, updated ledger, staged test logs, deferred-work list, ownership-release requirements.  
**Steps:** Finish all independent allowed tasks. Report what is staged, what is unverified, and which gates remain closed. Stop dependent original-project modifications.  
**Pass:** No claim that integration or deployment is complete. Original services remain untouched by this executor.  
**Next:** Await explicit human release. Do not poll forever or autonomously open Phase B.

## 12. Phase B: merge only after explicit release

### B00 — Verify release and take a fresh baseline

Record the user's exact release instruction, time, allowed paths, and remaining restrictions. Re-read Kimi's final work, route registrations, tests, reports, and source hashes. Rebuild the compatibility worksheet with added routes. Preserve Kimi's implementation as the new baseline.

If ownership remains ambiguous for a file, leave that file protected and continue only with released paths. Do not roll back Kimi changes to make a staged patch apply.

### B01 — Rebase staged proposals onto the final tree

Compare every proposed file with its recorded base hash and the final original. Apply a three-way semantic reconciliation in a private copy first. Resolve differences one module at a time. Update fixtures when the final baseline legitimately changed, recording why.

Acceptance: No Kimi feature or test disappears. Every changed original file has a specific purpose and a reviewed diff. Broad unrelated formatting fails this gate.

### B02 — Integrate shared configuration and component packaging

Merge runtime configuration and runner modules. Preserve old aliases and startup behavior. Change legacy gateways incrementally, testing each before the next. Keep database schema and data roots unchanged at this stage.

Acceptance: Both legacy Node gateways retain their established outputs and failure semantics; clean bundle component discovery works independently of cwd.

### B03 — Integrate contracts, registry, and local read catalog

Add stable mappings and provider services without rewriting raw data. Rehearse a real catalog build from approved consistent snapshots. Compare counts and references by scope, not just total row count.

Acceptance: Native lookup round trips, revision publication, rollback, and preserved decisions/provenance all pass.

### B04 — Register v2 routes in the shared application

Modify the final `app.py` only now. Add v2 routes without removing or shadowing legacy routes. Test path ordering, parameterized/static conflicts, operation IDs, tags, response models, and binary documentation.

Acceptance: All final baseline routes remain registered. OpenAPI/route inventory differences are intentional and documented. Legacy default content types remain unchanged.

### B05 — Integrate released materials, syllabus, and timetable features

Use Kimi's final modules and tests. Add adapters rather than replacing them with staged fixture implementations. Validate a representative original document and structured result for each supported layout/version. Preserve null session/date fields and unavailable-season evidence.

Acceptance: Final capabilities accurately reflect actual CIE and Edexcel support. No mock fixture is exposed as real source data.

### B06 — Migrate frontend source discovery

Move the existing frontend source behavior into backend services with matching tests. Then switch the frontend API client behind a reversible setting. Keep the old path available during compatibility validation.

Acceptance: Complete real local user flows work for each supported system. The browser no longer owns source-fetching business logic. Partial-season behavior and syllabus links remain correct.

### B07 — Integrate jobs, coverage, and diagnostics

Add read-only adapters for real checkpoints. Preserve source-owned checkpoint authority and stop requirements. Generate coverage from published data and explicit expected manifests.

Acceptance: Stopped jobs stay stopped, old reports do not override newer checkpoints, partial coverage remains partial, and public diagnostics are sanitized.

### B08 — Rehearse data-root migration

Use approved consistent backups, private destinations, and explicit copy manifests. Verify hashes, foreign keys, references, row counts, index identity, manual decisions, and provenance. Do not delete originals.

Acceptance: Rehearsal and restore both pass. A separate real-data cutover authorization is recorded before any live path pointer changes.

### B09 — Freeze and run final acceptance

Freeze implementation changes for the acceptance run. Run targeted regressions, then the final full suite and clean installed-bundle tests. Record the exact source/data revisions and every skip reason. If a change is made after the run, rerun the affected checks and any required final gate.

Acceptance: No unexplained failures, no skipped mandatory acceptance, no mock-only claim of live source validation, and no stale test counts presented as new results.

### B10 — Deliver the integration and deployment proposal

Produce the final code diff, compatibility matrix, models/OpenAPI, migration diff, test report, browser evidence, known gaps, version/hash manifest, deploy instructions, and rollback instructions.

Do not restart the existing service or deploy merely because the integration is ready. If the user has authorized cutover, perform the approved steps and verify the running version. Otherwise report “integration ready; cutover not run.”

## 13. Standard task record and execution ledger

Create a record for every A/B packet with this structure:

```json
{
  "task_id": "A04",
  "status": "not_started",
  "mode": "PHASE_A_ISOLATED_ONLY",
  "dependencies": ["A03"],
  "allowed_write_roots": [],
  "input_hashes": {},
  "changed_files": [],
  "commands": [],
  "exit_codes": [],
  "test_results": [],
  "evidence_paths": [],
  "remaining_gaps": [],
  "blocked_by": [],
  "next_action": "",
  "updated_at": ""
}
```

Allowed task statuses: `not_started`, `in_progress`, `staged_pass`, `merged_pass`, `partial`, `blocked`, `deferred_active_owner`, `not_run`. Status changes require evidence. Do not mark an entire packet passed when mandatory items are deferred.

For every executed command record cwd, command or script path, relevant nonsecret environment, start/end time, exit code, and stdout/stderr evidence files. Do not paste secrets into command logs. A command exiting zero does not automatically prove its intended effect.

After interruption, read the ledger and hashes before continuing. Do not restart completed work or assume an interrupted write finished. Inspect partial output, validate it, and resume at the first incomplete dependency.

## 14. Safe PowerShell startup and verification instructions

These commands are for the implementation executor, not evidence that implementation has happened. Run them in a private shell. Review all paths before executing.

```powershell
Set-Location -LiteralPath 'C:\Users\weo\Desktop\api'
$integrationRoot = 'C:\Users\weo\Desktop\api\integration-staging'
$integrationEvidence = 'C:\Users\weo\Desktop\api\docs\integration\execution'

# Inspect existing directories before creating or reusing them.
Test-Path -LiteralPath $integrationRoot
Test-Path -LiteralPath $integrationEvidence

# Create only after ownership is confirmed. Never delete an existing tree.
New-Item -ItemType Directory -Path $integrationRoot -Force | Out-Null
New-Item -ItemType Directory -Path $integrationEvidence -Force | Out-Null

# Process-local settings only. No setx and no user/system environment edits.
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONIOENCODING = 'utf-8'
$env:GIT_OPTIONAL_LOCKS = '0'

# Read-only inventory of the original repository.
git -C 'C:\Users\weo\Desktop\api\examdata' status --porcelain=v1 --untracked-files=normal
git -C 'C:\Users\weo\Desktop\api\examdata' log -1 --format='%H %ad %s' --date=iso
```

Do not run the saved route-inventory script during Phase A as-is: its current output path overwrites the planning baseline. Copy it into staging, change its output to `execution/`, verify that it only reads source text, and then run the staged copy.

Before running staged tests, create their config and directories. An example command after A02 is implemented:

```powershell
$integrationPython = 'C:\Users\weo\Desktop\api\examdata\.venv\Scripts\python.exe'
Set-Location -LiteralPath $integrationRoot

# Only staged tests. Do not point this at examdata/tests.
& $integrationPython -m pytest -c .\pytest.ini .\tests `
  --basetemp .\runtime\pytest-temp `
  -o cache_dir=.\runtime\pytest-cache
```

The existing interpreter may be used to execute staged code, but do not install packages into it. If a missing dependency prevents isolated work, first check available installed packages; then record the blocker or create a separate private environment if authorized. Do not upgrade the shared venv.

Tests must set private database/data paths before imports. Test the path guard itself using a deliberately forbidden path. A `NETWORK_MODE=offline` setting counts only if tested code enforces it; install a failing fake transport in the staged test harness.

Do not start an HTTP server unless needed. Prefer in-process TestClient for the isolated app. If a browser test needs a server, choose an available private loopback port, record the PID you created, and terminate only that PID afterward. Never kill processes by broad executable name.

## 15. Required acceptance matrix

### 15.1 Contract and identity tests

- Deterministic IDs across repeated builds.
- Alias normalization without IELTS/CIE confusion.
- Qualification/specification distinctions preserved.
- Native ID round trip.
- Collision detection.
- Split/merge lineage.
- Unknown dates and unsupported filters.
- Parent/child questions and answer fallback.
- Grouped answers and missing slots.
- Table-choice and multiple-selection structure.
- Quality state cannot be promoted without evidence.

### 15.2 API tests

- Every final legacy route appears in the compatibility worksheet.
- Legacy defaults and binary formats remain compatible.
- New envelope and public errors match OpenAPI.
- Partial source success and all-source failure are distinct.
- Stable cursor pagination across a fixed revision.
- Invalid/stale cursor behavior.
- Resource links resolve only to supported capabilities.
- No arbitrary URL proxy.
- No expensive crop/download side effect during ordinary search.
- No N subprocesses for N list items.

### 15.3 Storage and runner tests

- Failed builds leave current unchanged.
- Concurrent publication cannot overwrite a newer revision.
- Restore of previous pointer succeeds.
- Atomic cache write and invalid-page rejection.
- No original data root used in tests.
- Runner timeout/cancellation cleans up children.
- Queue/output/response budgets are enforced.
- Environment precedence and component path discovery are deterministic.
- Read-only code directory works.
- Non-ASCII and space-containing paths work.

### 15.4 Binary and content tests

- PDF/PNG/audio magic bytes and MIME agree.
- Bounded base64/ZIP outputs.
- Range 206/416 and ETag behavior where declared.
- Safe filename and path handling, including Windows paths.
- Hash mismatch rejects a crop.
- Multi-region/rotated crop samples have current visual evidence in Phase B.
- Missing required images prevent content-complete status.
- Audio integrity does not imply verified alignment.
- Original/manual/generated answers remain distinguishable.

### 15.5 Frontend and installed-bundle tests

- CIE/Edexcel course -> syllabus -> resources -> question -> answer -> crop.
- IELTS book/variant/skill/test -> question -> audio state.
- TOEFL set -> table question -> answer and restricted-jj state.
- Materials and timetable flows after Kimi release.
- All-season partial failures remain visible.
- API key never appears in browser code or responses.
- Clean installation includes Node components and packaged JSON data.
- Running from another cwd works.
- Old and new clients can coexist.
- Rollback restores the previous client/service configuration.

### 15.6 Evidence labels

Every report must use one of: `static_inspection`, `synthetic_fixture`, `copied_snapshot`, `isolated_real_data`, `live_local_service`, `live_upstream_sample`, `full_source_validation`, or `deployed_target_validation`.

Do not collapse these labels into “tested.” Fixture and snapshot tests are valuable but cannot prove source freshness, production performance, or live deployment.

## 16. Stop, defer, and rollback rules

| Condition | Required action |
| --- | --- |
| A write would leave the Phase A allowlist | Do not execute; prepare the change in staging and mark deferred |
| Original source changes while copying | Reject the unstable copy; record owner activity; continue independent work |
| Kimi feature conflicts with staged proposal | Preserve Kimi final baseline; reconcile after release; never overwrite with stale copy |
| A test tries to reach real upstream | Fail the test; fix transport isolation; do not treat it as a live validation opportunity |
| A test points to original DB/data | Stop before import/execution; correct private roots |
| Strict CIE stop condition | Preserve checkpoint; no retry, source switch, or force bypass |
| PDF/index hash mismatch | Return conflict; no silent reindexing |
| Migration counts/references differ unexpectedly | Stop publication/cutover; retain old current and investigate in private copy |
| Runner exceeds time/output budget | Terminate/wait; release resources; return classified failure |
| Disk/permission failure | Stop writes/publication; preserve current readable revision and evidence |
| No human release for Phase B | Complete all Phase A work; report awaiting release; do not infer permission |
| No deployment authorization | Deliver release and rollback proposal; mark deployment not_run |

Rollback units are code release, component manifest, data revision pointer, database backup, frontend switch, and job checkpoint. Roll them back separately. Never restore an old database over new writes without freezing or reconciling those writes.

Clean only your own precisely recorded staging temporary files. Before any recursive deletion, resolve the absolute target and verify it is a strict child of the approved staging root. Do not delete raw evidence, published revisions, manual decisions, Kimi outputs, or original temporary folders.

## 17. Deliverables and reporting

### 17.1 Phase A deliverables

1. Ownership/mode record and path allowlist.
2. Component, route, CLI, configuration, and data-role inventories.
3. Complete legacy compatibility worksheet.
4. Contracts, schemas, identity decision, and quality rules.
5. Private fixture provenance manifest.
6. Staged registry/providers/runner/catalog/v2 API and tests.
7. Staged frontend/client and operations proposals.
8. Proposed file-by-file merge map with base hashes.
9. Isolated test logs and failure/skip explanations.
10. Deferred active-owner work and exact Phase B release requirements.
11. A clear statement that originals were not modified by this executor and integration has not yet been applied.

### 17.2 Phase B deliverables

1. Fresh Kimi-final baseline and ownership release record.
2. Merged code diff preserving all baseline routes.
3. Updated OpenAPI and compatibility results.
4. Real-data migration rehearsal/diff and restore evidence.
5. Final test, browser, binary, runtime, and installation results.
6. Release manifest with exact component versions and hashes.
7. Accurate current gaps and coverage by scope.
8. Deploy/cutover and rollback instructions.
9. Actual running-target evidence only if cutover was authorized and performed.

### 17.3 Progress message format

Use short factual updates:

```text
Mode: PHASE_A_ISOLATED_ONLY
Completed: A00–A04
Current: A05 provider registry
Evidence: <paths>
Deferred: materials/timetable and original shared files; Kimi ownership lock remains
Original services: not touched by this executor
Next: run capability-dispatch fixture tests
```

Do not repeatedly ask whether to continue ordinary permitted work. Continue the allowed dependency chain. Ask only when an actual gate requires human action, and explain that the gate comes from the user's instruction to leave Kimi's project alone.

### 17.4 Final report format

The final report must state: execution mode reached; tasks completed; tasks staged versus merged; files changed; tests and evidence types; data effects; original-service effects; compatibility coverage; remaining gaps; closed/open gates; next exact action.

Do not end with “all done” while active-owner integration, original-project tests, or deployment are deferred. Use a precise result such as “Phase A complete; changes remain staged; Phase B awaits your explicit release of Kimi-owned paths.”

## 18. Planning assumptions and decisions to verify later

The source inventory and status figures are snapshots from 2026-10-05. Kimi may add routes, files, data, or tests after this plan. Phase B must use its final output as the baseline.

Unknowns that do not prevent Phase A include the final Edexcel timetable implementation, actual loaded version of port 8000, final repository organization, remote deployment target, production concurrency, dataset size, and PostgreSQL availability.

Do not choose a destructive default to resolve these unknowns. Keep the current physical layout initially, use private fixtures now, and defer only the work that requires the unknown fact.

No schedule estimate authorizes skipping acceptance. Work packet completion is based on artifacts and evidence, not elapsed time or token usage. The engineering integration and the remaining dataset-completion work are separate deliverables.
