# A13 — Staged frontend API client and operations views (staged)

Packet A13 of `docs/integration/MASTER_EXECUTION_PLAN_EN.md` §11 (plan 3.5).
Status: **staged_pass** (staged in `integration-staging/`, not merged, not
deployed). All seven Phase B gates remain closed.

## 1. Scope

Plan A13 — "Stage the frontend API client and operations views". Write: a
copied frontend proposal, client module, fixture server, checkpoint readers,
coverage fixtures. Steps: preserve the original UX; replace source requests
only in the copy; do not start on 5188 or talk to 8000; do not load or change
Kimi-owned timetable code. Pass: fixture browser flows work and are explicitly
labeled as staged fixture validation.

Delivered as four staged pieces, all inside the packet writable roots
(`integration-staging/`, `docs/integration/execution/`):

1. **Copied frontend proposal** — `integration-staging/frontend/` (15 files):
   6 copied originals (2 byte-identical `copied_snapshot`, 4 `modified_copy`
   with recorded source hashes), 4 new modules, 3 private fixtures, plus the
   two provenance manifests. The original `frontend/` tree was read-only;
   source requests are replaced only in the copy.
2. **Staged v2 API client** (`client.mjs`) consuming the staged
   `/api/v2` envelope: envelope parsing, typed errors, per-season fan-out,
   resource→document mapping; gated by the reversible `examdata.v2-client`
   flag (default on).
3. **Offline fixture server** (`fixture-server.mjs`) speaking the staged
   envelope over private fixtures: binds `127.0.0.1` only, defaults to an
   ephemeral port, and refuses the protected original ports `{5188, 8000}`
   (exit 2). Port 8000 is never contacted.
4. **Operations checkpoint readers and coverage views**
   (`src/examdata_integration/operations/`) over 6 hand-authored synthetic
   fixtures shaped like the two native checkpoint formats (CIE batch runner,
   `ielts-run-checkpoint/1`); read-only semantics, no guess and no exception
   on unknown input.

The three native checkpoint files (`cie-location-batch/checkpoint.json`,
`ielts-data/test-s03/runs/run-ok/checkpoint.json`,
`ielts-data/runs/pte-20261004/checkpoint.json`) were consulted once with the
Read tool as format references; no test parses them and no live batch/run
state was read. No Kimi-owned timetable/materials code was loaded or changed
and nothing was ever started on 5188.

## 2. Deliverables

Frontend — `integration-staging/frontend/`:

| file | provenance | role |
| --- | --- | --- |
| `index.html` | `modified_copy` | adds a `#staged-banner` after the site header (staged fixture validation wording) |
| `app.js` | `modified_copy` | wires `liveSearch()` to the staged client behind the `examdata.v2-client` flag; removes the dead `/gateway` fetch helper; labels `quality==='synthetic_fixture'` rows `STAGED FIXTURE · 合成夹具` |
| `styles.css` | `copied_snapshot` | byte-identical to `frontend/styles.css` |
| `search.mjs` | `copied_snapshot` | byte-identical to `frontend/search.mjs` |
| `README.md` | `modified_copy` | rewritten as staged-copy notes; shares only the file name with the original document (the merge must reconcile it) |
| `tests/search.test.mjs` | `modified_copy` | keeps the 10 subject/paper normalization tests verbatim; import repointed to `../search.mjs`; the resources block is retired with the staged copy; LF |
| `client.mjs` | `new_file` | staged v2 API client (envelope, typed errors, per-season fan-out, mapping) |
| `fixture-server.mjs` | `new_file` | offline fixture server for the staged envelope (127.0.0.1, protected-port refusal) |
| `tests/client.test.mjs` | `new_file` | 10 client unit tests over injected fetch |
| `tests/flow.test.mjs` | `new_file` | 7 end-to-end flow tests against the in-process fixture server |
| `fixtures/catalog.json` | `new_file` | private synthetic catalog fixture (1 851 bytes) |
| `fixtures/syllabi.json` | `new_file` | private synthetic syllabi fixture with per-system season arrays (810 bytes) |
| `fixtures/resources.json` | `new_file` | private synthetic resources fixture (10 164 bytes) |
| `PROVENANCE.json` | — | `frontend-provenance/1`: 6 copied (source + staged sha256) + 4 new |
| `fixtures/PROVENANCE.json` | — | `fixture-provenance/1` for the 3 fixtures (sha256 + size) |

Operations — `integration-staging/src/examdata_integration/operations/`:

| file | role |
| --- | --- |
| `__init__.py` | exports `checkpoints`, `coverage` (1 469 bytes) |
| `checkpoints.py` | read-only readers for the CIE batch runner checkpoint and `ielts-run-checkpoint/1` run files; missing native stop fields stay `None`; superseded snapshots stay visible as stale rows; unrecognised input becomes an explicit `unknown` row with problems instead of an exception or a guess (10 978 bytes) |
| `coverage.py` | coverage view derived from checkpoint observations: partial failure never zeroes counters or hides a blocked source; same-instant disagreements become explicit conflicts; with neither counters nor sources the state is `UNKNOWN` (9 702 bytes) |

Fixtures — `integration-staging/fixtures/synthetic/operations/` (6 JSON +
`README.md` + `PROVENANCE.json`, schema `fixture-provenance/1`, 6 entries,
sha256 recorded):

| fixture | bytes | drives |
| --- | --- | --- |
| `cie-batch-checkpoint-running.json` | 1 485 | running batch derives `in_progress`; missing stop fields stay `None` |
| `cie-batch-checkpoint-stopped.json` | 1 649 | read-only batch adapter; healthy stopped coverage |
| `ielts-run-checkpoint-ok.json` | 852 | healthy IELTS run checkpoint coverage row |
| `ielts-run-checkpoint-ok-stale.json` | 889 | a stale summary is kept as superseded and can never override a newer snapshot |
| `ielts-run-checkpoint-partial.json` | 1 070 | partial failure never zeroes counters / hides a blocked source |
| `unsupported-checkpoint.json` | 658 | unknown checkpoint → explicit problems, no exception |

Tests — 31 Python tests + 27 node tests:

| file | tests | covers |
| --- | --- | --- |
| `tests/test_operations_checkpoints.py` | 15 | checkpoint readers: running/stopped CIE, IELTS ok/stale/partial, unsupported, missing stop fields |
| `tests/test_operations_coverage.py` | 9 | coverage honesty: partial, stale superseded, conflicts, all-blocked, unknown |
| `tests/test_frontend_staged_copy.py` | 7 | copy conformance: manifests vs disk, staged-only new files, no original-path writes |
| `frontend/tests/search.test.mjs` | 10 | subject aliases, full-width digits, zero padding, Edexcel variant, paper/ms pairing |
| `frontend/tests/client.test.mjs` | 10 | envelope, typed errors, fan-out, partial/all failure, selectors, flag reversibility |
| `frontend/tests/flow.test.mjs` | 7 | served page/modules/snapshots, envelope, content hash, error envelopes, route_not_found, no key material |

Tools — `integration-staging/tools/`: `a13_capture_fixtures.py`
(regenerates/`--check`s the operations provenance), `a13_frontend_provenance.py`
(regenerates/`--check`s both frontend manifests; carries the source overrides
and change notes).

Evidence and ledger — `docs/integration/execution/`:
`evidence/A13/{node_tests_stdout.txt, pytest_run_stdout.txt,
operations_provenance_stdout.txt, frontend_provenance_stdout.txt,
final_checks.txt, python_rerun.txt, frontend_rerun.txt}` (the last three are
produced by the closing checks); ledger patch
`integration-staging/runtime/ledger-patches/A13_close.json`.

## 3. Validation model

**Acceptance mapping.** Each plan-A13 test point is covered, at fixture
level, in the staged copy:

- **Subject aliases** — `search.test.mjs`: Chinese names and full-width
  digits, leading-zero syllabus codes (`580`→`0580`), maths defaulting to
  9709 while explicit IGCSE stays selectable (`mathematics igcse`→`0580`),
  duplicate-title qualification resolution, Edexcel variant and Chinese
  subject alias (`经济学`→`ial18-economics`).
- **All seasons with partial failure** — `client.test.mjs`: fan-out over
  every board season merges documents; a failed season is reported without
  discarding the others; an all-failed fan-out rejects instead of claiming
  no matches. The operations side proves the same idea for coverage: a
  partial checkpoint keeps counters and shows the blocked source.
- **Unavailable data** — `client.test.mjs`: `documentFromResource` marks
  unavailable items (`content_available === false` → no content link) and
  drops unknown roles.
- **Correct system-specific selectors** — `client.test.mjs`: a chosen season
  queries only that season with the edexcel selector set; a paper number
  joins the per-season token list; `syllabi.json` carries per-system season
  arrays; `flow.test.mjs` asserts the staged `app.js` keeps both selector
  sets and no `/gateway`.
- **Source quality display** — `app.js` labels rows with
  `quality === 'synthetic_fixture'` as `STAGED FIXTURE · 合成夹具`, and the
  staged page carries the `#staged-banner` notice.
- **No exposed key** — `flow.test.mjs`: "no key material appears in the
  staged files"; the fixtures hold no credentials and the client and server
  need none.
- **Explicit staged fixture validation labeling (pass criterion)** — the
  banner text (`集成暂存副本 · staged fixture validation · 仅合成夹具数据，
  未连接真实来源`), the server banner (`staged fixture validation · 仅
  127.0.0.1`), and the envelope warning constant
  `staged_fixture_validation` all mark the copy as staged; the flow tests
  exercise the fixture browser flows end to end and assert the envelope
  warning.

**Offline/containment posture.** Node tests run entirely against the
in-process fixture server on `127.0.0.1` (ephemeral port); the server refuses
`5188`/`8000` at startup; no external fetch exists in the copy. Python tests
specifically run under the staged harness guards (network and module guards
active). Nothing in the packet reads a database, starts an original service,
or calls upstream.

**Honesty rules kept.** Operations coverage is derived, never stored; stale
summaries are superseded but visible; disagreements are explicit conflicts;
unknown input stays unknown with problems attached. Nothing was promoted:
every artefact remains fixture-level (`synthetic_fixture`,
`static_inspection`, `copied_snapshot`); no `merged_pass` exists anywhere.

## 4. Evidence

| evidence | label | file |
| --- | --- | --- |
| node suite green: 27/27 (10 search + 10 client + 7 flow) | `synthetic_fixture` | `evidence/A13/node_tests_stdout.txt` |
| full staged suite green: 887 passed / 0 failed | `synthetic_fixture` | `evidence/A13/pytest_run_stdout.txt` |
| operations provenance PASS (6 entries, sha256 recorded) | `static_inspection` | `evidence/A13/operations_provenance_stdout.txt` |
| frontend provenance PASS (6 copied, 4 new, 3 fixtures) | `static_inspection` | `evidence/A13/frontend_provenance_stdout.txt` |
| closing checks PASS | `static_inspection` + `synthetic_fixture` | `evidence/A13/final_checks.txt` |
| fresh Python targeted re-run at close (31 tests) | `synthetic_fixture` | `evidence/A13/python_rerun.txt` |
| fresh node re-run at close (27 tests) | `synthetic_fixture` | `evidence/A13/frontend_rerun.txt` |

Test-count arithmetic: A12 closed at 856 Python tests; +24 operations
(checkpoints 15 + coverage 9) + 7 frontend copy = **887**.
The node suite adds 27 (duration 285.69 ms in the recorded run).
The frontend manifest records both the source and staged sha256 of all six
copied files; the two `copied_snapshot` entries are byte-identical to their
sources, and the closing checks re-verify the manifests in fresh
subprocesses.

## 5. Corrections made in this packet

1. **Coverage `UNKNOWN` guard.** The first draft classified an observation
   with neither counters nor sources as blocked; the all-blocked branch
   could mislabel an empty observation. Added, before the all-blocked
   judgment: `if state.counters is None and state.sources is None: return
   CoverageState.UNKNOWN`.
2. **Operations test wiring.** Two edits to `test_operations_coverage.py`
   after the first draft: added `from pathlib import Path` plus the
   `STAGING`/`FIXTURES` constants, and changed the observation helper to
   load fixtures through `checkpoints.read_checkpoint(FIXTURES / name,
   observed_at=WHEN)` instead of ad-hoc reads.
3. **Fixture gap found by the first operations run.** The first targeted run
   reported `1 failed, 879 passed` (the `| tail -30` pipeline masked the
   process exit code to 0): `cie-batch-checkpoint-running.json` lacked
   `current_paper`, so `test_cie_running_view_keeps_missing_stop_fields_none`
   raised `KeyError` (line 99). Fixed by inserting
   `"current_paper": "8888/2026/Jun/22"` between `last_fetch_at` and
   `loop_stage`, regenerating the manifest, and re-running: `880 passed`.
4. **Node invocation form.** `node --test integration-staging/frontend/tests/`
   exited 1 with `MODULE_NOT_FOUND` (the `; echo rc=$?; tail` suffix masked
   the harness exit code to 0). Correct form: the quoted glob
   `node --test "integration-staging/frontend/tests/*.test.mjs"`.
5. **Unavailable-item mapping (found by the first node glob run, 26/27).**
   `documentFromResource marks unavailable items` failed: an item with
   `content_available === false` still got the content link
   `http://staged.test/api/v2/assets/asset_test/content` because the mapping
   preferred `content_link` over the availability flag. Fixed in `client.mjs`:
   `const link = item.content_available === false ? null : (item.content_link
   ?? (item.links && item.links.content) ?? null);` → 27/27.
6. **Provenance reclassification.** The first manifest draft assumed the two
   test-support originals lived under a `tests/` subdirectory; the original
   tree keeps `README.md` and `search.test.mjs` at `frontend/` root. Fixed
   with `SOURCE_OVERRIDES` (staged `tests/search.test.mjs` ← source
   `frontend/search.test.mjs`), reclassifying both as `modified_copy` and
   narrowing `NEW_FILES` to the 4 genuinely new modules; both manifests were
   regenerated and `--check` passed (`6 copied, 4 new, 3 fixtures`).
7. **Development-script episode (no product impact).** A wire-log extraction
   heredoc exited 1 with `UnicodeEncodeError: 'gbk' codec` while writing
   non-ASCII output through the GBK console; re-run with
   `PYTHONIOENCODING=utf-8` succeeded. One inspection command used a
   non-existent path (`integration-staging/api/app.py`) and was corrected;
   it touched no deliverable.

The two red node/py runs and the directory-invocation failure ran through
suffix/pipe forms that masked their process exit codes to 0; they are
recorded in the ledger failures with `exit_code_masked: true`.

## 6. Deliberate limitations

- **Copy-only by construction.** The staged frontend is a modified copy with
  recorded source hashes; the merge (B06) must reconcile `README.md` (shared
  file name, different content), reapply the `app.js`/`index.html` edits on
  the final tree, and switch the frontend to the real backend behind the
  reversible `examdata.v2-client` flag.
- **The fixture server is a stand-in.** Phase A proves the frontend flows
  against an in-process Node fixture server that mimics the staged
  `/api/v2` envelope; it is not the Python staged API and is replaced at
  merge time.
- **"Browser flows" are node tests.** No real browser was launched (Phase A
  is offline); the flow tests exercise the served page, modules, snapshots
  and envelopes over HTTP on `127.0.0.1`.
- **Operations readers are fixture-level.** They are proven against 6
  synthetic fixtures shaped like the two native formats; the native
  checkpoint files were read once for shape only and are never parsed by
  tests. Real checkpoint adaptation is Phase B (B07).
- **Search normalization coverage is a subset.** The original
  `search.test.mjs` resources block (lines 15–39) is retired with the staged
  copy; the 10 subject/paper normalization tests are kept verbatim.
- **Node tests are not under the Python network guard**; offline behavior is
  by construction (no external fetch, 127.0.0.1-only server, protected-port
  refusal).
- **Kimi-owned files untouched.** No timetable/materials module was loaded,
  parsed or changed; those integrations stay deferred.

## 7. Remaining gaps

- Frontend merge (B06), operations/jobs integration (B07) and real
  checkpoint adapters (B07) require the Phase B release; none of it was
  attempted in Phase A.
- The original `frontend/` tree remains entirely Kimi-owned and unchanged by
  this packet; base hashes for the merge map are recorded in
  `frontend/PROVENANCE.json` (source sha256 per copied file).
- A14 (file-by-file merge map) and A15 (`PHASE_A_REPORT.md` + deferred list
  + release request) are the remaining Phase A packets.
- The staged work is **not merged and not deployed**; the live database,
  service restarts, upstream crawl and CIE batch resume remain Phase B and
  require explicit human release. All seven Phase B gates stay closed.

## 8. Next action

A14 — file-by-file merge map per plan: identify every eventual original
target path and the base hash used to prepare it, avoid a whole-tree
replacement patch, list active-owner deferred files separately, and show why
each change is reversible; then A15 (`PHASE_A_REPORT.md` + deferred-work
list + ownership-release requirements).
