# A07 — CIE and Edexcel read adapters (Phase A, isolated)

**Status:** staged pass. Nothing merged, nothing deployed; every Phase B gate
remains closed. Work is confined to `integration-staging/` and
`docs/integration/execution/`. No original file, database, service, upstream
source or the stopped CIE batch was touched.

## 1. Scope

Build the plan §11 A07 read layer: turn a raw, board-shaped index document into
the frozen A04 contract entities **without losing any irregularity**. Two boards
are covered here — CIE (paper index with a question tree) and Edexcel
(subject/unit index). IELTS and TOEFL follow in A08.

The adapter never reads the original database, never resumes the CIE batch and
never promotes content to `verified`. Every input is a private synthetic fixture;
every irregularity becomes a visible `AdapterProblem` instead of an exception or
a silent drop.

Inputs (hashed into the ledger): the four governing documents, the ledger, the
A06 report and its evidence, the frozen A04 contracts and the A06 runtime surface
the adapters reuse.

## 2. Deliverables

Source (staged package `integration-staging/src/examdata_integration/adapters/`):

| file | role |
| --- | --- |
| `problems.py` | `ProblemCode` (13 codes), `AdapterProblem` (`to_dict`, `to_gap`), `problem()`; maps adapter codes onto frozen `GapCode`s |
| `reader.py` | `read_index`, `validate_index`, `SUPPORTED_SCHEMA_VERSIONS` — the only file-opening step; total, never raises for a data problem |
| `documents.py` | `DocumentTable` (role → hash), `document_problems`, `hash_conflict_problem` |
| `answers.py` | `AnswerMode` (exact/ancestor/descendants/none), `ResolvedAnswers`, `resolve_answers`, `conflicts_without_decision` |
| `regions.py` | `page_rotation_table`, `build_regions` — region geometry and rotation, conflicts preserved |
| `bundle.py` | `AdapterBundle` — mapped entities plus every problem; `walk_questions`, `problems_for`, `gaps`, `to_dict` |
| `cie.py` | `CIEIndexAdapter` — CIE paper index → courses/containers/questions/answers/regions/assets |
| `edexcel.py` | `EdexcelIndexAdapter` — Edexcel subject/unit index → courses/containers/assets/regions |
| `__init__.py` | the public surface |

Staged fixtures (`integration-staging/fixtures/synthetic/adapters/`):

| path | role |
| --- | --- |
| `cie-index-adapters.json` | synthetic raw CIE index: subject 8888, paper 21, no session date, `qp`+`in` documents (no `ms`), three rotated pages, questions exercising descendants/exact/ancestor answers, a hash conflict and a region on an undeclared page |
| `edexcel-index-adapters.json` | synthetic raw Edexcel index: one IAL subject with aliases, three units (missing `ms` on two, a conflicting region hash on one), unknown session dates |
| `PROVENANCE.json` | fixture-provenance/1 manifest for this packet (own file; the frozen A03 manifest is untouched) |
| `README.md` | provenance note |

Tools: `integration-staging/tools/a07_capture_adapter_fixtures.py` (writes /
`--check`s the adapter provenance), `integration-staging/tools/a07_probe_adapters.py`
(42-scenario offline probe), `integration-staging/tools/a07_final_checks.py`
(closing checks), `integration-staging/tools/a07_close_patch.py` (ledger patch).

Tests (staged, 94): `tests/test_adapters_answers.py` (16),
`test_adapters_cie.py` (17), `test_adapters_documents.py` (14),
`test_adapters_edexcel.py` (13), `test_adapters_provenance.py` (6),
`test_adapters_reader.py` (14), `test_adapters_regions.py` (14).

## 3. The read step (frozen, tested)

`read_index(path)` returns `(dict | None, [problems])` and never raises for a data
problem. A missing file or directory → `missing_index`; unreadable bytes →
`unreadable_index`; malformed JSON → `invalid_json`; a non-object document →
`invalid_json`; anything not labelled `fixture_kind: "synthetic"` →
`wrong_fixture_kind`; an unknown `schema_version` → `unsupported_schema_version`
(only `"1"` is supported). A failed read yields `None`, never a half-parsed
document.

## 4. Documents, answers and regions (frozen, tested)

**Documents.** The role → hash table is kept honest: a hash is never invented, a
missing mark scheme is its own `missing_ms` problem (never confused with a
missing question paper), and a region citing a hash that disagrees with the table
raises `hash_conflict` while the cited hash is **preserved verbatim** and the
region stays `unverified`.

**Answers.** Three stated shapes are kept distinct:

* `exact` — the answer is on the question; tagged `matching_method=exact`
  (`grouped` when alternatives are given);
* `ancestor` — the nearest ancestor's answer is inherited, tagged `ancestor`, with
  `lineage.parent_refs` naming the ancestor (so it is never mistaken for a stated
  answer);
* `descendants` — a synthesised answer whose `alternatives` are the parts' values
  in order, `original_value=None`, `ordering_rule="descendant_order"`;
* `none` — nothing is inherited or derived.

An answer the index does not state is never invented: a question with no reachable
answer in its mode yields `missing_answer` and keeps the empty slot. Every emitted
answer is `verification="unverified"` and `content_class="synthetic"`. An unknown
`answer_mode` yields `unresolved_answer_mode` and behaves as `none`.

**Regions.** Every raw region becomes its own `Region` (a question with two
regions yields two, never one merged box). Page rotation is carried through when
the page is listed; a region on a page the index does not describe is
`unknown_rotation` with **no** transform, unless the index declares no page table
at all (then the absence is not an error). A region without four bounding numbers
is `missing_region_bbox`, not a silently empty region. Regions are always
`evidence_status="unverified"`.

## 5. Adapter problem → frozen gap mapping

Adapter codes are deliberately **not** added to the frozen `GapCode` vocabulary —
a missing index file is a property of the read step, not of stored content. The
subset that corresponds to a plan §4.3 content gap exposes `to_gap`:

| adapter problem | frozen gap |
| --- | --- |
| `missing_index`, `unreadable_index`, `invalid_json` | `deferred_source` |
| `missing_ms`, `missing_document_role` | `missing_document_hash` |
| `hash_conflict`, `unknown_rotation` | `unverified_content` |
| `missing_region_bbox` | `missing_region` |
| `missing_answer` | `missing_answer` |
| `unknown_date` | `unknown_date` |
| `wrong_fixture_kind`, `unsupported_schema_version`, `unresolved_answer_mode` | *(read-step diagnostic only)* |

## 6. Evidence

| check | result | evidence |
| --- | --- | --- |
| Adapter probe, 42 scenarios, offline | **A07_PROBE: PASS (0 failing)** | `evidence/A07/adapters_stdout.txt` |
| Staged suite, offline | **326 passed**, exit 0 | `evidence/A07/pytest_run_stdout.txt` |
| Reader / validation | **PASS** | `tests/test_adapters_reader.py` |
| Documents + conflicts | **PASS** | `tests/test_adapters_documents.py` |
| Answer resolution | **PASS** | `tests/test_adapters_answers.py` |
| Regions + rotation | **PASS** | `tests/test_adapters_regions.py` |
| CIE adapter | **PASS** | `tests/test_adapters_cie.py` |
| Edexcel adapter | **PASS** | `tests/test_adapters_edexcel.py` |
| Fixture provenance | **A07_PROVENANCE: PASS (2 entries)** | `tests/test_adapters_provenance.py` |
| Closing checks | see `final_checks.txt` | `evidence/A07/final_checks.txt` |

Suite growth: A06 baseline 232 → 326 (A07 adds 94 tests). All evidence labels are
`synthetic_fixture`.

## 7. Corrections made in this packet

1. **`Lineage` imported from the wrong module** in four adapter files; it lives in
   `contracts.models`, not `contracts.base`. The first smoke run failed on the
   import; fixed.
2. **Dead placeholder** in `cie.py` replaced with a proper `UNKNOWN_DATE` problem
   when the raw index carries no session date.
3. **`build_regions` gained `rotations_declared`** so an index with no page table
   is not falsely flagged `unknown_rotation`.
4. **`_own_answer`** no longer takes an unused `mode`; a stated answer is always
   tagged `exact`/`grouped`.
5. **Eight test-side expectation errors** fixed to the settled semantics (region
   tests default `declared=False`; `none`/unknown-mode expectations updated).
6. **Fixture hash length.** Both cited `cccc…` hashes in the CIE fixture were 62
   characters instead of 64; corrected to 64 and the fixture provenance re-hashed.
   (The adapter had correctly preserved the short hash verbatim — the defect was
   in the synthetic fixture, not the adapter.)

## 8. Deliberate limitations

* Only synthetic fixtures are read. There is **no** connection to the original
  database, no upstream fetch, no CIE batch resume and no service start.
* The adapters map index documents only. Active materials and historical
  timetable integration stay deferred to the active owner (A12 keeps the
  `deferred_active_owner` worksheet rows deferred).
* No content is promoted past `unverified`; promotion is a Phase B gate.
* CIE `answer_resolution` supports the four documented modes; a raw index using
  another mode is reported, not guessed.

## 9. Remaining gaps / deferred

* **Inherited A06 stderr race (not an A07 regression).** Running the frozen A06
  `tests/test_runner_classification.py` emits a nondeterministic
  `PytestUnhandledThreadExceptionWarning`: when a node child is killed mid-write
  (overflow/timeout/cancel), the `subprocess` reader thread raises
  `UnicodeDecodeError` decoding the fixture's non-UTF-8 stderr byte. It reproduces
  with the A06 tests alone (5 warnings) and does not affect any assertion; the
  failure is fail-closed (stderr is dropped, never leaked). The A06 runner is
  frozen, so this is recorded here and left for a future, explicitly-authorized
  change to `runtime/runner.py` (catch `UnicodeDecodeError` / decode with
  `errors="replace"`); it is **not** fixed in A07.
* A08 consumes the same adapter shape for IELTS and TOEFL; the IELTS Q41
  missing-answer slot and all conflicts stay `unverified`.
* Real-data behaviour and any promotion to `verified` stay Phase B behind the
  write-authorization gate.

## 10. Next action

A08 — IELTS and TOEFL read adapters over synthetic/copied fixtures (plan §11),
preserving the IELTS Q41 missing-answer slot, table structures, locked jj and
unknown dates; then A09 catalog + revision publication, A10 the isolated v2 API,
A11 binary ranges and budgets, A12 the route worksheet, A13 the frontend
proposal, A14 the file-by-file merge map and A15 `PHASE_A_REPORT.md`.
