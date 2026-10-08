# A12 — Legacy 71-route compatibility worksheet (staged)

Packet A12 of `docs/integration/MASTER_EXECUTION_PLAN_EN.md` §11 (plan 5.5).
Status: **staged_pass** (staged in `integration-staging/`, not merged, not
deployed). All seven Phase B gates remain closed.

## 1. Scope

Give every route of the frozen 71-route v1 baseline an explicit compatibility
disposition, proven by staged tests, without touching the original
application, its database or its services:

1. **Static shape extraction** of the four original FastAPI modules
   (`examdata/src/examdata/api/{app,unified,ielts,toefl}.py`) by AST only —
   the modules are never imported or executed; their byte hashes are recorded
   before and after the packet (no drift).
2. **Staged legacy compatibility package**
   (`integration-staging/src/examdata_integration/legacy/`): pure proposal
   builders (`translate`), a shape/parity summariser (`parity`), node-CLI
   bridge envelope contracts (`bridge`) and the registry/decisions vocabulary
   (`decisions`), plus `registry.json` — one row per baseline route.
3. **Worksheet** (`A12_ROUTE_COMPATIBILITY_WORKSHEET.json`, schema
   `examdata.integration.route_compatibility_worksheet/2`) carrying the A01
   columns plus `row_id`/`mechanism`/`coverage_kind`/`owner`/`notes` and the
   per-row `row_origin`/`handler_doc_line`/`line`/`a01_proposal` extras.
4. **Offline compatibility probe** (`evidence/A12/compat_probe.json`,
   schema `examdata.integration.compat_probe/1`): pytest collection proves
   every test id referenced by the registry exists, and a targeted run of the
   five staged legacy test files ties the rows to a dated green run.

Writable roots used: `integration-staging/` and
`docs/integration/execution/`. No original path was written; the original
application and its tests were never run. The original materials/timetable
routers were touched only for existence/hash checks (never parsed, never
executed).

## 2. Deliverables

Legacy package — `integration-staging/src/examdata_integration/legacy/`:

| file | role |
| --- | --- |
| `__init__.py` | exports `bridge`, `decisions`, `parity`, `translate` |
| `translate.py` | v1 payload builders reproducing the statically extracted success shapes (pagination, question bundles, paper trees, boards, search, IELTS/TOEFL gateway payloads); pure functions, no I/O |
| `parity.py` | shape summariser + parity checker used to compare extracted v1 shapes against staged v2 payloads at contract level |
| `bridge.py` | node-CLI bridge contract for the IELTS/TOEFL gateway rows: `RunResult` → legacy envelope mapping, outcome classification aligned with `runtime.classification.RunnerOutcome` |
| `decisions.py` | registry loader (`rows()`, `row_id()`, `registry_sha256()`), mechanism/status vocabulary, evidence helpers |
| `registry.json` | the 71-row registry (schema `examdata.integration.legacy_registry/1`; 127 663 bytes; sha256 `f9e1870b79616bbb…`) |

Registry facts (frozen):

- `row_count` = 71; `allowed_statuses` = 7
  (`not_started`, `fixture_ready`, `staged_pass`, `merged_pass`,
  `deferred_active_owner`, `blocked`, `not_applicable_with_reason`);
- mechanisms: `add_v2_adapter_keep_legacy_defaults` 21,
  `keep_legacy_only` 16, `bridge_node_cli_keep_legacy_payload` 20,
  `keep_legacy_namespace` 7, `deferred_active_owner` 7;
- statuses: `staged_pass` 64, `deferred_active_owner` 7;
- coverage kinds: `envelope_contract` 33, `static_contract` 24,
  `fixture_translation` 14;
- sources hashed in the registry: the four original api modules (read-only,
  byte-identical at close: `app.py 753749fa…`, `unified.py 9568b295…`,
  `ielts.py 9d79ee00…`, `toefl.py 051449da…`).

Worksheet facts:

- 23 columns = the A01 18 columns + `row_id`, `mechanism`, `coverage_kind`,
  `owner`, `notes`; extra row keys `row_origin`, `handler_doc_line`, `line`,
  `a01_proposal` (the A01 proposal is preserved per row when A12 overrides
  it);
- coverage 71/71 baseline rows, `post_baseline_count` 0 (the active owner
  added no route to the four api modules during A12); any route added later
  is appended by the builder as `post_baseline`/`post_baseline_unreviewed`
  and re-runs the rescan;
- `rescan`: static AST without import; recorded vs. fresh source hashes of
  the four api modules identical (no drift);
- `active_owner_files`: `examdata/src/examdata/materials/router.py` and
  `examdata/src/examdata/timetable/router.py` exist (existence only);
- `problems` = [] .

Tests — `integration-staging/tests/` (5 modules, 145 tests):

| file | tests | covers |
| --- | --- | --- |
| `test_legacy_adapters.py` | 24 | fixture-translation rows against `default_dataset()` (21 adapter params + 3 registry-level) |
| `test_legacy_bridge_contracts.py` | 82 | static contract params for every row (71) + node-bridge envelopes (`test_node_bridge_envelope[ielts/toefl]`) |
| `test_legacy_decisions.py` | 11 | registry loader, row ids, vocabulary, evidence paths |
| `test_legacy_parity.py` | 10 | shape summariser / parity semantics |
| `test_legacy_translate.py` | 18 | payload builders incl. missing-slot semantics (IELTS Q41 shape), table structures, document hashes |

Tools — `integration-staging/tools/`: `a12_extract_legacy_shapes.py`
(static AST extractor), `a12_build_registry.py`,
`a12_build_worksheet.py`, `a12_probe_compat.py`, `a12_final_checks.py`,
`a12_close_patch.py`.

Evidence and ledger — `docs/integration/execution/`: `A12_REPORT.md`,
`A12_ROUTE_COMPATIBILITY_WORKSHEET.json`,
`evidence/A12/{legacy_shape_extract.json, pytest_run_stdout.txt,
collect_only_stdout.txt, legacy_tests_stdout.txt, compat_probe.json,
final_checks.txt, legacy_rerun.txt}`; ledger patch
`integration-staging/runtime/ledger-patches/A12_close.json`.

## 3. Compatibility model

**Three coverage kinds.** Every row is proven at the level its mechanism
allows, and the worksheet says which:

- `fixture_translation` (14 rows): the v1 payload builder is exercised
  against the frozen synthetic catalog (`default_dataset()`, revision
  `rev-bb3a81094e0d2cb8f5173708f56b3722`) and its output is checked against
  the extracted v1 success shape.
- `static_contract` (24 rows): the extracted v1 signature/shape (params,
  defaults, success/error shape, side effects) is frozen as a test that
  pins the row to the registry and the worksheet.
- `envelope_contract` (33 rows): bridge/success/error envelopes are checked
  as contracts, including the 20 node-CLI bridge rows whose payload contract
  is preserved (`RunnerOutcome` vocabulary, error-body mapping).

**Preservation.** The registry and worksheet preserve: native identities
(`row_id` + legacy path/method/handler/line), legacy defaults, missing
answer slots, question hierarchy and table structures (via the payload
builders and their tests), document hashes, answer-conflict and manual
decision payloads (A06 semantics referenced in the bridge decisions), and
provenance (`evidence_path` per row). Nothing is promoted: every row stays
`staged_pass` or `deferred_active_owner`; no row is `merged_pass`; the
evidence labels remain `static_inspection` / `synthetic_fixture`.

**Deferred rows (7).** Owned by the still-active original modules; A12 only
recorded their existence and kept them out of scope:

`GET /api/v1/materials`, `GET /api/v1/materials/cie/in-paper`,
`GET /api/v1/materials/{material_id}`,
`GET /api/v1/materials/{material_id}/content`, `GET /api/v1/timetable`,
`GET /api/v1/timetable/seasons`, `GET /api/v1/timetable/windows`.

They carry `status=deferred_active_owner`, mechanism
`deferred_active_owner`, and a `deferred_reason` naming the active owner.

**Probe.** `a12_probe_compat.py` runs two offline pytest passes inside
`integration-staging` (shared venv python, no installs, no network): a
`--collect-only` over the staged suite and a targeted run of the five legacy
modules. It also verifies every row's `evidence_path` exists and that the
full-suite evidence is fresh (its `passed` count equals the collected node
count). Result at close: **A12_PROBE: PASS (0 problems)** — 856 collected
node ids (the `856 tests collected` line agrees), all 71 rows have every
recorded test id collected (142 ids), adapter params 21/21 and
static-contract params 71/71 in both directions, deferred rows 7, legacy run
rc=0 with 145 passed / 0 failed.

## 4. Evidence

| evidence | label | file |
| --- | --- | --- |
| static shape extract (64 handler shapes, source hashes) | `static_inspection` | `evidence/A12/legacy_shape_extract.json` |
| registry + worksheet + probe chain (sha256-verified) | `static_inspection` | `evidence/A12/compat_probe.json` |
| full staged suite green: 856 passed / 0 failed | `synthetic_fixture` | `evidence/A12/pytest_run_stdout.txt` |
| collection transcript (856 node ids) | `static_inspection` | `evidence/A12/collect_only_stdout.txt` |
| targeted legacy run: 145 passed / 0 failed | `synthetic_fixture` | `evidence/A12/legacy_tests_stdout.txt` |
| closing checks PASS | `static_inspection` + `synthetic_fixture` | `evidence/A12/final_checks.txt` |
| fresh legacy re-run at close | `synthetic_fixture` | `evidence/A12/legacy_rerun.txt` |

The compat probe records the sha256 of its six sources (registry, worksheet,
A01 worksheet, full-suite transcript, both stdout transcripts); all six
match the on-disk bytes at close. The worksheet records the registry, its
build tool, the shape-rescan tool and the A01 worksheet hashes; the registry
records the four original api file hashes. The chain
`A01 → registry → worksheet → probe` is byte-verified end to end.

## 5. Corrections made in this packet

1. **Adapter tests and `UNKNOWN`.** The first full legacy run reported
   `4 failed, 852 passed`: the adapter tests serialised `CatalogEntry` with
   `dataclasses.asdict`, which raises `TypeError` on
   `parent_native_id=UNKNOWN`. Fixed by using `entry.to_dict()`, which
   preserves the encoded `"__unknown__"` token.
2. **`board_source` output key.** The next run reported
   `1 failed, 855 passed`: `translate.legacy_search_page` did not emit the
   `board_source` key the extracted v1 shape requires. Fixed in
   `translate.py` (parameter + output key); the two affected tests updated;
   the suite then reported `856 passed`.
3. **Bridge test ids in the registry.** Probe run 1 exited 1 with 20
   problems: the bridge rows referenced
   `…::test_node_bridge_envelope_ielts` / `…_toefl`, which pytest collects
   as the parameterised ids `test_node_bridge_envelope_ielts[ielts]` /
   `[toefl]`. Resolved by renaming the test to `test_node_bridge_envelope`
   (parameterised over both boards; node count unchanged) and updating the
   registry generator to emit `::test_node_bridge_envelope[{board}]`; the
   registry was rebuilt (final sha256 `f9e1870b79616bbb…`) together with the
   worksheet, and the probe re-ran green.
4. **Evidence byte consistency.** During pre-close verification the compat
   probe was found to record LF-form text hashes for
   `collect_only_stdout.txt` / `legacy_tests_stdout.txt` while
   `write_text` had applied Windows newline translation (CRLF on disk).
   Fixed by writing all probe outputs with `newline="\n"` and re-running the
   probe; all six recorded source hashes now byte-match disk.
5. **Development-script iterations (no product impact).** The registry
   builder's first run raised a traceback (fixed by edit before the first
   successful render); one bridge introspection heredoc used
   `dataclasses.fields` on a non-dataclass and was rewritten; several
   inspection heredocs exited 1 on wrong-path/structure assumptions and were
   corrected in the next call.
6. **Closing-checks bootstrap and tool repair.** The first run of
   `a12_final_checks.py` exited 1 by construction (it bootstraps the two
   post-close transcripts it verifies) and additionally exposed a bug in the
   checks tool itself: the six-source expectation map held sha-only values
   while the verifier unpacked each entry as `(path, sha)` pairs, aborting the
   probe-facts section with
   `ValueError('too many values to unpack (expected 2)')`. The map was changed
   to `(path, sha256)` pairs and the exit-code reconciliation updated to the
   three rc!=0 commands; the close patch was rebuilt, the ledger re-merged,
   and the closing checks re-ran green (`FINAL_CHECKS: PASS`).

The two intermediate full-suite runs (`4 failed / 852 passed`,
`1 failed / 855 passed`) ran through `| tail` pipelines without `pipefail`;
their process exit codes were masked to 0. They are recorded in the ledger
failures with `exit_code_masked: true` so the regression signal is not
hidden.

## 6. Deliberate limitations

- **Static/offline by construction.** The four original api modules were
  parsed with AST only (never imported); the legacy package never reads the
  live database, starts a service or runs the original tests. Equivalence is
  asserted at the payload/contract level, not by running v1 and v2 services
  side by side (prohibited in Phase A).
- **The node-CLI bridge is contract-level.** The 20 bridge rows are proven
  through envelope contracts over synthetic `RunResult` records; no node
  process is executed and no aggregator directory is touched.
- **Materials/timetable remain with the active owner.** The 7 deferred rows
  were never parsed or executed; their compatibility work depends on the
  active owner's in-flight changes and stays deferred to Phase B.
- **The registry records one probe-level truth**, not per-row runtime
  traces: each row's `evidence_path` points at the staged test module or the
  probe that covers it.
- **Post-baseline routes are detectable but not auto-reviewed.** If the
  active owner adds routes later, re-running `a12_build_worksheet.py` appends
  them as `post_baseline_unreviewed` for review in a later packet.

## 7. Remaining gaps

- Legacy compatibility at runtime (real v1 traffic replay, node CLI
  execution, database merge) requires the Phase B release; none of it was
  attempted.
- The 7 materials/timetable rows stay `deferred_active_owner`.
- A13 (frontend proposal, copy-only), A14 (file-by-file merge map) and A15
  (`PHASE_A_REPORT.md`) are the remaining Phase A packets.
- The staged work is not merged and not deployed; the live database, service
  restart, upstream crawl and CIE batch resume remain Phase B and require
  explicit human release.

## 8. Next action

A13 — frontend proposal: a copy-only staging proposal for the frontend
(`integration-staging/` contains no frontend copy yet; the proposal lists
the files to copy and the integration points without touching
`frontend/`), then A14 (file-by-file merge map) and A15
(`PHASE_A_REPORT.md` + deferred list + release request).
