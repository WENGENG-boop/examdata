# A05 — Provider protocol and registry (Phase A, isolated)

**Status:** staged pass. Nothing merged, nothing deployed; every Phase B gate
remains closed. Work is confined to `integration-staging/` and
`docs/integration/execution/`.

## 1. Scope

Build the plan §3.5 / §5.2 provider layer on top of the frozen A04 contracts:

* a typed **capability** model (the ten read operations) and an availability
  state, so an optional provider that is down is not silently treated as empty;
* a frozen **provider protocol** and **descriptor** every provider publishes;
* **typed results** (`ProviderResult` / `DispatchResult`) in which only a
  genuine success carries data and an unsupported capability or an
  uninterpretable filter is never mistaken for "zero results";
* a **registry** that filters by declared capability, routes native aliases
  explicitly (never defaulting to the first provider), and dispatches across
  providers with a deterministic aggregate status and error precedence;
* **fixture-backed providers** for CIE, Edexcel and IELTS that map the A03
  synthetic fixtures onto the A04 models, preserving native identity, hierarchy,
  table structure, conflicts and the missing answer slot.

Inputs (hashed into the ledger): the four governing documents, the A04 report,
the A03 synthetic fixtures and provenance, and the A04 evidence.

## 2. Deliverables

Source (staged package `integration-staging/src/examdata_integration/providers/`):

| file | role |
| --- | --- |
| `capabilities.py` | `Capability` (10 ops), `CAPABILITIES`, `TARGET_REQUIRED`, `Availability` |
| `results.py` | `OutcomeStatus`, `ERROR_PRECEDENCE`, `ProviderResult`, `DispatchResult`; `_sanitize` (bounds length and redacts filesystem paths) |
| `protocol.py` | frozen `ProviderDescriptor`, runtime-checkable `Provider` protocol (`query(capability, *, filters, target)`) |
| `registry.py` | `ProviderRegistry`: `register`/`unregister`, `capability_providers`, alias routing (`register_alias`/`route`/`owns_alias`/`aliases_for`), `dispatch`; 5 typed errors |
| `fixtures.py` | `FixtureProvider` base + `CIEIndexProvider`, `EdexcelIndexProvider`, `IELTSQuestionsProvider`; edge doubles `NullProvider`, `UnavailableProvider`, `FailingProvider` |
| `__init__.py` | the public surface |

Tools: `integration-staging/tools/a05_probe_dispatch.py` (20-scenario offline
dispatch probe), `integration-staging/tools/a05_final_checks.py` (closing
checks), `integration-staging/tools/a05_close_patch.py` (ledger patch).

Tests (staged): `tests/test_providers_registry.py` (20 tests),
`tests/test_providers_fixtures.py` (46 tests).

## 3. Dispatch semantics (frozen, tested)

Order is fixed so an unsupported or unavailable provider can never be reached by
an accidental call:

1. unknown provider id → `failed(unknown_provider)`;
2. capability not declared → `unsupported` (capability filtering precedes the call);
3. provider unavailable → `unavailable` (`retryable`);
4. filter the provider cannot interpret → `filter_rejected` with the offending
   `filter_key` (never silently ignored);
5. otherwise call `provider.query`; a raised exception becomes
   `failed` with a **sanitized** detail (no local path can surface).

Aggregate rule: at least one success → `ok` (or `partial` with warnings); every
requested provider failed → `error` with a deterministic `code` chosen by
`ERROR_PRECEDENCE = (unsupported, filter_rejected, unavailable, not_found,
failed)`; no provider requested → `error(no_provider_requested)`. An empty
success stays `ok` with no error — empty is not unsupported.

Alias routing is explicit: an unknown alias raises (`UnknownAliasError`), it
never defaults to the first registered provider; a conflicting rebind raises
(`AliasRoutingError`) and leaves the original binding intact.

## 4. Fixture-provider mapping (what is preserved)

* **Admission** — a provider accepts only a fixture labelled
  `fixture_kind == "synthetic"`; anything else raises, so real examination
  material can never enter the staged provider layer.
* **CIE** — course native subject `9999` + alias; paper container native
  identity `{subject, year, season, paper, date:null}`; question hierarchy
  `1 → 1(a), 1(b)` with `number_path`/`parent_ref`; table payload for Q2;
  conflict + required image on Q3; hash-only documents; regions carry a page but
  no bbox (gap `missing_region`); unknown date (gap `unknown_date`).
* **Edexcel** — course aliases `WMA`/`synthetic-maths`; paper container with
  `unit_code`/`paper_code`; two sessions with unknown dates; document assets;
  no question/answer data (typed `unsupported`, not an empty success).
* **IELTS** — book container with a dataset revision; `Q3 → Q3.i, Q3.ii`;
  grouped alternatives → `OptionsPayload`; table choice → `TablePayload`;
  `Q41` missing answer slot preserved as `UNKNOWN`/`UnknownPayload` with an
  empty-success + `missing_answer_slot` gap; `Q5` conflict stays `unverified`;
  a **year filter is rejected** (a book number is not an examination date).
* **Invariants** — every emitted model is `content_class = synthetic`; every
  answer stays `verification = "unverified"`; coverage arithmetic is
  self-consistent (`observed == excluded + unknown + missing + partial + verified`).

## 5. Evidence

| check | result | evidence |
| --- | --- | --- |
| Dispatch probe, 20 scenarios, offline | **A05_PROBE: PASS (0 failing)** | `evidence/A05/dispatch_stdout.txt` |
| Staged suite, offline | **141 passed**, exit 0 | `evidence/A05/pytest_run_stdout.txt` |
| Registry semantics (filtering, aliases, precedence) | **PASS** | `tests/test_providers_registry.py` |
| Fixture mapping (hierarchy, tables, gaps, provenance) | **PASS** | `tests/test_providers_fixtures.py` |
| Closing checks | see `final_checks.txt` | `evidence/A05/final_checks.txt` |

Suite growth: A04 baseline 75 → 141 (A05 adds 66 tests: 20 registry + 46 fixtures).

## 6. Corrections made in this packet

1. `results._sanitize` bounded length and collapsed whitespace but did **not**
   remove filesystem paths, so a provider exception carrying
   `C:\private\path\secret.db` would have surfaced that path in the public
   aggregate error message. Fixed: drive-rooted and POSIX paths are replaced
   with `<path>` before bounding. A registry test asserts the path never reaches
   the message while the exception type is still reported.
2. `test_providers_registry.test_error_precedence_is_deterministic` registered
   its "unsupported" provider with the capability it was dispatching for, so the
   provider *succeeded* and the test raised `TypeError`. Fixed: the provider now
   declares an unrelated capability, so the request is genuinely unsupported.
3. `test_providers_fixtures.test_cie_table_question_maps_to_a_table_payload`
   used a `question` filter, which is a gate (returns the full set), not a
   narrowing selector; it now uses `target="2"`.
4. `a05_final_checks.py` initially **rewrote** the dispatch transcript while
   re-running the probe, which changed its bytes (LF vs the `tee`-produced CRLF)
   and invalidated the hash the ledger had recorded at close time. Fixed: an
   evidence transcript is now treated as **read-only after close** — the tool
   verifies the stored transcript and only creates it when it is genuinely
   absent. Correspondingly, `a05_close_patch.py` excludes post-close artefacts
   from `changed_files` as well as from the hash set, so a post-close transcript
   can never be listed as a changed file.

## 7. Deliberate limitations

* Providers read only the A03 synthetic fixtures; there is **no real-data
  adapter** yet (that is A07/A08) and **no network or database access**.
* `tags`, `materials` and `timetable` are intentionally unimplemented (no
  fixture exists and they belong to the active owner), so requesting those
  capabilities yields a typed `unsupported` — the designed behaviour, recorded
  as `deferred_active_owner`, not a defect.
* The capability model is the plan's ten read operations; write operations are
  out of scope for the read-only integration.

## 8. Remaining gaps / deferred

* Real CIE/Edexcel/IELTS/TOEFL adapters (A07/A08) and the catalog (A09) consume
  this layer next; nothing here reads protected or live resources.
* Real-data behaviour, cross-source reconciliation and any promotion to
  verified stay Phase B behind the write-authorization gate.

## 9. Next action

A06 — configuration and the controlled Node runner (plan §11): freeze the
gateway spawn contract, an environment template, and a confined Node runner that
resolves only inside the staged tree, with tests for missing executable, paths
with spaces, invalid/multiple JSON values, non-zero exit, stderr redaction,
queue-full, output overflow, timeout, cancellation, process cleanup and
environment precedence — all offline.
