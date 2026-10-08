# A08 — IELTS and TOEFL read adapters (Phase A, isolated)

**Status:** staged pass. Nothing merged, nothing deployed; every Phase B gate
remains closed. Work is confined to `integration-staging/` and
`docs/integration/execution/`. No original file, database, service, upstream
source or the stopped CIE batch was touched.

## 1. Scope

Build the plan §11 A08 read layer on top of the frozen A07 adapter shape: turn a
raw IELTS or TOEFL source document into the frozen A04 contract entities
**without losing any irregularity**, and read the small *copied snapshots* of
non-protected original metadata files that the frozen A03 provenance manifest
records (TOEFL reading index, IELTS printed-page map, IELTS PDF-import
provenance, IELTS revision pointers).

Two new source kinds are introduced, so A08 adds a read step
(`source_reader.py`) rather than reusing A07's synthetic-only `reader.py`:

* **synthetic fixture** — hand-authored, `fixture_kind == "synthetic"`;
* **copied snapshot** — a byte-identical copy of a small original metadata file,
  which carries no `fixture_kind` field, so the kind is decided from the path
  (`fixtures/copied/` vs `fixtures/synthetic/`) and validated against the kinds
  the caller allows.

Nothing here opens a file the caller did not name, walks a tree, resolves a path
outside the staging root, or fetches anything. The adapter never reads the
original database, never resumes the CIE batch and never promotes content to
`verified`. Every irregularity becomes a visible `SourceProblem` instead of an
exception or a silent drop.

Inputs (hashed into the ledger): the four governing documents, the ledger, the
A07 report and its evidence, the frozen A04 contracts, the frozen A07 adapter
modules A08 reuses, the frozen A03 fixtures and their provenance manifest, and
the A02–A07 harness the A08 tests run under.

## 2. Deliverables

Source (staged package `integration-staging/src/examdata_integration/adapters/`):

| file | role |
| --- | --- |
| `source_reader.py` | `SourceKind` (synthetic / copied_snapshot / unknown / outside_staging), `classify_path`, `read_source` (`(doc, kind, problems)`; total, never raises for a data problem), `validate_kmf_url`, `iter_cache_entries`, `SourceProblem`/`SourceProblemCode` with their own gap map |
| `ielts.py` | `IELTSQuestionsAdapter` (question set → courses/containers/questions/answers/regions), `IELTSPagesAdapter` (copied printed-page map → documents/assets), `IELTSRevisionAdapter` (revision pointers), `IELTSAudioAdapter` (audio tracks → alignment states); `PageResolution`, `AudioTrack` |
| `toefl.py` | `TOEFLReadingIndexAdapter` (copied reading index → one container per passage), `TOEFLQuestionSetAdapter` (official / TPO / jj question sets), `TOEFLCacheAdapter` (cache reparse); `CacheReport` |

Staged fixtures (`integration-staging/fixtures/synthetic/ielts-toefl/`):

| path | role |
| --- | --- |
| `ielts-questions-a08-synthetic.json` | a second synthetic IELTS book: a question `variant`, unresolved edition, raw source ids, special numbering `7(b)(ii)`, an unresolved answer conflict and a missing answer slot |
| `ielts-audio-synthetic.json` | audio alignment states: a linked full recording, a claimed-but-unsupported `verified` alignment, an `unverified` time window, `unknown` and `not_applicable` |
| `toefl-questions-synthetic.json` | official / TPO / jj identity classes, a restricted (metadata-only) jj set, table-choice rows/columns, multiple-selection information, missing options/table, an unknown exam date and a bad KMF URL |
| `toefl-bad-cache-synthetic.json` | a cache with a non-object entry, an entry with no identity and a duplicate identity, to check the adapter reports rather than drops them |
| `PROVENANCE.json` | fixture-provenance/1 manifest for this packet (own file; the frozen A03 and A07 manifests are untouched) |
| `README.md` | provenance note |

These fixtures live in their own directory (not `../adapters/`) so the frozen A07
manifest, which globs `../adapters/*.json`, stays fresh.

Tools: `integration-staging/tools/a08_capture_fixtures.py` (writes / `--check`s
the A08 fixture provenance), `integration-staging/tools/a08_probe_adapters.py`
(40-scenario offline probe), `integration-staging/tools/a08_final_checks.py`
(closing checks), `integration-staging/tools/a08_close_patch.py` (ledger patch).

Tests (staged, 61 new): `tests/test_adapters_source_reader.py` (23),
`test_adapters_ielts.py` (22), `test_adapters_toefl.py` (16). They import the new
submodules directly (`from examdata_integration.adapters.ielts import ...`), so
the frozen A07 `adapters/__init__.py` is not modified.

## 3. The read step (new in A08, frozen, tested)

`read_source(path, *, allow=..., source_name=...)` returns
`(doc | None, kind, [problems])` and never raises for a data problem.

* A path outside the two staging roots → `(None, outside_staging, [outside_staging])`
  and the file is **not opened** (the containment check runs before any read).
* A missing file or directory → `missing_source`; unreadable bytes →
  `unreadable_source`; malformed JSON → `invalid_json`; a non-object document →
  `invalid_json`.
* A path under `fixtures/copied/` is `copied_snapshot`; under
  `fixtures/synthetic/` it is `synthetic`; anywhere else `unknown_source_kind`.
  A declared `fixture_kind` must agree with the path (`wrong_source_kind`): a
  copied snapshot must **not** claim `synthetic`, and a synthetic file must not
  omit the label.
* A declared `schema_version` other than `"1"` → `unsupported_schema_version`
  (checking is opt-in: an unlabelled copied snapshot is accepted).
* A failed read yields `None`, never a half-parsed document.

`validate_kmf_url` is a read-step rule, not a board mapping: a KMF link is
**checked, never followed**. It must be `https`, host `toefl.kmf.com`, path
`/detail/read/<hash>.html` (an optional trailing alphanumeric question anchor is
accepted). Any other scheme, host or shape → `invalid_kmf_url`.

`iter_cache_entries` iterates a cache document and reports a malformed entry
(a non-object, or one with no identity) as `bad_cache_entry` instead of dropping
it, so a cache is never silently shortened.

## 4. IELTS and TOEFL mapping (frozen, tested)

**IELTS question set.** Q41 with no reachable answer keeps the **empty slot**,
`answer_presence=missing` and a `missing_answer_slot` problem — it is never
invented and never promoted. A grouped answer becomes `options` with
`matching_method=grouped`; a table choice keeps its columns, rows and the answer
cell; a self-parent is normalised to the root while the raw parent is kept in the
lineage note; the question hierarchy and paths (`Q3`, `Q3.i`, `Q3.ii`) are
preserved. An answer conflict is preserved with `manual_decision=None`. Every
emitted answer stays `verification="unverified"` and `content_class="synthetic"`.
The A08 variant fixture keeps its `variant`, an unresolved `edition` (flagged
`edition_uncertain`), special numbering and the raw source id in the lineage.

**IELTS pages / provenance.** The copied printed-page map yields 664 printed
pages, 137 unresolved pages (`unresolved_page` → `missing_region`) and 133 assets
(9 PDF documents `application/pdf` + 124 imported assets with `media_type=None`,
each carrying its recorded hash). No document hash is invented; a copied
provenance entry with no hash is a `missing_document_hash`.

**IELTS revision.** Both revision pointers resolve to
`rev-8b21015ab64bb73c`; a stale pointer is reported, never silently accepted.

**IELTS audio.** A track that *claims* `verified` while its evidence is only
synthetic is capped at **effective `unverified`** with an `unverified_content`
problem — `audio_alignment unverified→verified` requires RENDER evidence, which a
synthetic fixture can never supply. A track with no time window yields
`missing_time_window` (`→ unknown_coverage`) and never invents an offset. The
`unknown` and `not_applicable` states stay distinct. Every audio integrity value
stays `unverified`.

**TOEFL reading index (copied).** One container per passage (72 containers, 72
distinct public ids); `declared_total=72` but `coverage_claimed=False` and every
`coverage=None` — a declared total is never presented as verified coverage.
Exactly two `unresolved_identity` problems arise for `tpo-38-2` (a duplicated KMF
hash `51ehlj` and a duplicated title `"The Racoon's Success"`); no legitimate
real KMF URL is rejected.

**TOEFL question sets.** official / TPO / jj are kept as distinct identity
classes; a restricted (jj) set is metadata-only (`restricted=True`,
`question_refs=[]`, a `restricted_source` problem) and its content is never
emitted. Table choices keep rows/columns and the answer cell; a multiple-selection
item keeps `selection_count=2` with `original_value='A'` and
`alternatives=['C']`. A question set with no options is `missing_options`, an
empty table is `missing_table`, a required-but-absent diagram is `missing_asset`;
an unknown exam date is `unknown_date`; a bad KMF URL is `invalid_kmf_url`.

**TOEFL cache reparse.** Five entries, two usable, three reported as
`bad_cache_entry` — a rejected entry is reported, never dropped.

## 5. Adapter problem → frozen gap mapping

A08 read-step codes are deliberately **not** added to the frozen `GapCode`
vocabulary; `SourceProblem.to_gap` exposes the subset that corresponds to a
plan §4.3 content gap:

| A08 problem | frozen gap |
| --- | --- |
| `missing_source`, `unreadable_source`, `invalid_json`, `unknown_source_kind`, `outside_staging`, `wrong_source_kind`, `unsupported_schema_version`, `restricted_source` | `deferred_source` |
| `bad_cache_entry`, `invalid_kmf_url`, `unverified_content` | `unverified_content` |
| `unresolved_identity` | `unresolved_identity` |
| `missing_options` | `missing_options` |
| `missing_table` | `missing_table` |
| `missing_answer_slot` | `missing_answer_slot` |
| `missing_asset` | `missing_required_image` |
| `missing_document_hash` | `missing_document_hash` |
| `unknown_date` | `unknown_date` |
| `unresolved_page` | `missing_region` |
| `unresolved_edition` | `unresolved_edition` |
| `answer_conflict` | `answer_conflict` |
| `missing_time_window` | `unknown_coverage` |

`SourceProblem` subclasses `AdapterProblem`, so it flows through the frozen
`AdapterBundle.gaps()` unchanged.

## 6. Evidence

| check | result | evidence |
| --- | --- | --- |
| Read-adapter probe, 40 scenarios, offline | **A08_PROBE: PASS (0 failing)** | `evidence/A08/adapters_stdout.txt` |
| Staged suite, offline | **387 passed**, exit 0 | `evidence/A08/pytest_run_stdout.txt` |
| Source read step (kinds, containment, KMF URL, cache) | **PASS** | `tests/test_adapters_source_reader.py` |
| IELTS questions / pages / revision / audio | **PASS** | `tests/test_adapters_ielts.py` |
| TOEFL reading index / question set / cache | **PASS** | `tests/test_adapters_toefl.py` |
| Fixture provenance | **A08_PROVENANCE: PASS (4 entries)**, rc=0 | `evidence/A08/provenance_check.txt` |
| Closing checks | see `final_checks.txt` | `evidence/A08/final_checks.txt` |

Suite growth: A07 baseline 326 → 387 (A08 adds 61 tests). Evidence labels are
`synthetic_fixture` (probe/tests) and `copied_snapshot` (the copied IELTS/TOEFL
metadata read by the pages / revision / reading-index adapters).

## 7. Corrections made in this packet

1. **`validate_kmf_url` was too strict.** The real copied reading index stores
   KMF links with a trailing question anchor (`/detail/read/<hash>.html/1`), which
   the first validator rejected — 51 of 72 legitimate links. It now accepts an
   optional trailing alphanumeric segment; `/detail/read/51ehlj.html/1` →
   `(True, 'ok')`, and a non-https mirror is still rejected. The URL is validated
   only; it is never requested.
2. **`answer_verification unknown→conflicting` is not a permitted transition.**
   The frozen quality rules require passing through `unverified` first; the IELTS
   adapter now applies `unknown→unverified` before the conflicting transition, so
   an unresolved conflict is recorded without an illegal jump.
3. **Test-side expectation on imported assets.** The pages test originally
   asserted every asset had a `media_type`; imported provenance assets have none.
   It now asserts 133 assets (9 PDF + 124 with `media_type is None`), each
   carrying its recorded hash — no product change.

## 8. Deliberate limitations

* Only synthetic fixtures and copied snapshots are read. There is **no**
  connection to the original database, no upstream fetch, no CIE batch resume and
  no service start.
* The adapters map index / metadata documents only. Active materials and
  historical timetable integration stay deferred to the active owner (A12 keeps
  the `deferred_active_owner` worksheet rows deferred).
* No content is promoted past `unverified`; promotion is a Phase B gate. In
  particular a synthetic audio fixture can never reach `verified` alignment.
* The copied IELTS PDF-import provenance records absolute original paths; these
  are preserved **verbatim** as provenance, not rewritten or resolved.
* The A03 IELTS question fixture carries no `schema_version`, so version checking
  is opt-in and unlabelled copied snapshots are accepted.

## 9. Remaining gaps / deferred

* **Inherited A06 stderr race (not an A08 regression).** Running the frozen A06
  `tests/test_runner_classification.py` emits a nondeterministic
  `PytestUnhandledThreadExceptionWarning`: when a node child is killed mid-write,
  the `subprocess` reader thread raises `UnicodeDecodeError` decoding the
  fixture's non-UTF-8 stderr byte. It reproduces with the A06 tests alone and does
  not affect any assertion; the failure is fail-closed (stderr is dropped, never
  leaked). The A06 runner is frozen, so this is recorded here and left for a
  future, explicitly-authorized change to `runtime/runner.py`.
* A09 consumes the catalog + revision publication; the A08 revision adapter reads
  pointers only and publishes nothing.
* Real-data behaviour and any promotion to `verified` stay Phase B behind the
  write-authorization gate.

## 10. Next action

A09 — catalog + revision publication (plan §11): a private mapping/catalog store,
a builder, immutable revision manifests and a pointer publisher; tests for
duplicate native ids, collision detection, incomplete references, failed
publication, concurrent publishers, a stale current pointer, rollback and stable
cursor references. A failed build must never change the current pointer and a
valid build must be reproducible. Then A10 the isolated v2 API, A11 binary ranges
and budgets, A12 the route worksheet, A13 the frontend proposal, A14 the
file-by-file merge map and A15 `PHASE_A_REPORT.md`.
