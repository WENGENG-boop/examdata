# A09 — Catalog store and revision publication (staged, Phase A)

**Packet:** A09 (plan §11), dependencies A04 (identity) and A03/A07/A08 (fixtures/harness).
**Status:** `staged_pass`. Staged only — **not merged, not deployed**. All seven Phase B
gates remain closed.

Evidence labels used in this report: `synthetic_fixture` (hand-authored mapping inputs),
`static_inspection` (frozen contracts/harness read, not run), and `copied_snapshot`
(only where a copied snapshot is named as provenance). No `isolated_real_data`,
`live_*`, `full_source_validation` or `deployed_target_validation` evidence is claimed.

---

## 1. Scope

A private mapping/catalog store, a builder that validates and diffs revisions, and an
immutable revision publisher with an atomic current pointer and cursors — offline,
stdlib only, private synthetic fixtures. This is the plan §7.2/§7.3 work: a mapping row
(native identity + locator + searchable fields + quality + lineage) becomes a stable
public ID and a stored entry, a build is reproducible or rejected, and publication never
disturbs the current pointer on failure.

Out of scope and deferred: real catalog data, the SQLite decision execution, database
migration, service cutover, and active materials/timetable integration (owned by Kimi).

## 2. Deliverables

Source (`integration-staging/src/examdata_integration/catalog/`):

| File | Role |
| --- | --- |
| `model.py` | `CatalogSource`, `CatalogEntry`, `CatalogSnapshot`; `compute_revision`; lossless `UNKNOWN` encoding |
| `store.py` | `CatalogStore`: stable IDs, duplicates, collisions, aliases, reference validation, gap mapping |
| `builder.py` | `CatalogBuilder.build`; contract→catalog mapping helpers; diff; removal/upgrade rejection |
| `revision.py` | `RevisionPublisher` (immutable revisions, atomic pointer, CAS, rollback) and cursors |
| `__init__.py` | docstring only (imports nothing, so no import cycle with frozen modules) |

Fixtures (`integration-staging/fixtures/synthetic/catalog/`, new dir so the frozen A07
adapter manifest stays fresh): `catalog-base-synthetic.json`,
`catalog-duplicate-native-id-synthetic.json`, `catalog-incomplete-reference-synthetic.json`,
`catalog-removal-unexplained-synthetic.json`,
`catalog-quality-upgrade-unexplained-synthetic.json`, and a generated `PROVENANCE.json`
(5 entries).

Tools: `a09_capture_fixtures.py`, `a09_probe_catalog.py`, `a09_final_checks.py`,
`a09_close_patch.py`.

Tests: `tests/test_catalog_store.py` (15), `tests/test_catalog_builder.py` (14),
`tests/test_catalog_revision.py` (14) — 43 new tests.

Docs: this report and `A09_STORE_DECISION.md` (the §7.2 architecture record).

## 3. Store

`CatalogStore.add` maps a native identity to a stable public ID through the frozen A04
identity rules (never a row number) and records a **visible problem** rather than
guessing:

- **benign duplicate** (same identity, same content revision + locator) deduplicates and
  returns the existing entry;
- **duplicate native id** (same identity, different content) is recorded *and* raised
  (`DuplicateNativeIdError`); `add_all` catches it so a build keeps going and still fails;
- **identity collision** (two different canonical identities on one public ID) and
  **alias conflict** (one alias claimed twice, atomically — the rejected identity is not
  half-registered) are recorded and rejected;
- **invalid identity** is a problem, never an exception.

`validate_references` reports a `container_ref`/`course_ref` that resolves to nothing as
`unresolved_identity`. `to_gap` maps the identity-related codes onto the frozen
`GapCode.UNRESOLVED_IDENTITY` at system scope.

The `UNKNOWN` sentinel (explicit "known to be unknown") is encoded as a reserved JSON
token and decoded back, so an identity survives `to_dict` → `from_dict` unchanged — the
frozen `plain()` would otherwise flatten it to the string `"unknown"` and silently change
a canonical identity. This is asserted directly.

## 4. Builder

`CatalogBuilder.build(sources, previous=…, explanations=…, input_revisions=…, created_at=…)`
follows the §7.3 transaction up to publication:

1. build a store from the staged sources; collect store problems + unresolved references;
2. compute the revision as a **pure function of the entries** (`compute_revision`), so a
   build is reproducible — `created_at` and `input_revisions` deliberately do not
   participate;
3. diff the previous revision (`added`/`removed`/`changed`/`quality_upgrades`);
4. reject an **unexplained removal** (a removed entry with no explanation);
5. reject a **quality upgrade without authoritative evidence** — only a move *up* the
   verification axis from an unverified state counts, and only
   `copied_snapshot`/`isolated_real_data`/`full_source_validation`/`deployed_target_validation`
   are authoritative (a `synthetic_fixture` never is);
6. on any problem return `snapshot=None` — nothing publishable.

Mapping helpers (`source_from_course/container/question/asset/region`) copy the frozen
model's identity, locator, hash, bbox and revision fields exactly; where the frozen model
carries no value (e.g. `content_class`) the default is `"unknown"`, never an invented
`"official"`. A question's container/parent identity is required input — a caller that
does not know it must pass `UNKNOWN`, not a guess.

## 5. Publication

`RevisionPublisher` writes each revision once (temp file + `os.replace`), refuses to
overwrite a revision with a different body, and replaces `current.json` atomically.
Publication is **compare-and-swap**: `expected_current` that does not match the live
current revision raises `StalePublisherError` and leaves the pointer untouched.
`publish(None)` and a revision that does not match its entries both raise
`PublicationRejected` with the pointer byte-identical. `rollback` restores the retained
previous revision atomically; both revisions stay available.

Cursors bind query, sort, dataset revision and last key, carry a `sha256` integrity tag,
are length-bounded (4096), and are rejected as **invalid** (400) when tampered with or as
**stale** (409) with restart instructions when their revision is no longer published.

The store choice (JSON snapshot + atomic pointer over SQLite) is recorded in
`A09_STORE_DECISION.md`, with the measured fixture-scale justification and the threshold
that would force SQLite.

## 6. Evidence

| Evidence | What it proves |
| --- | --- |
| `evidence/A09/catalog_stdout.txt` | `A09_PROBE: PASS (0 failing)` — 30 offline scenarios |
| `evidence/A09/pytest_run_stdout.txt` | `430 passed` (387 prior + 43 A09), 0 failures |
| `evidence/A09/provenance_check.txt` | `A09_PROVENANCE: PASS (5 entries)` |
| `evidence/A09/final_checks.txt` | closing checks (produced after the ledger closes) |
| `integration-staging/fixtures/synthetic/catalog/PROVENANCE.json` | every fixture labelled synthetic, no upstream content |
| `integration-staging/runtime/ledger-patches/A09_close.json` | the ledger close patch (input hashes, changed files, commands, exit codes) |

The probe covers identity stability/determinism, native-locator round-trip, benign
duplicates, duplicate native id, collision, alias conflict, incomplete references (and
their gap mapping), reproducible revision, empty diff, unexplained/explained removal,
unexplained/authoritative quality upgrade, "synthetic is never authoritative", lossless
`UNKNOWN`, publication + immutable revision, failed publication leaving the pointer
untouched, compare-and-swap, rollback, and cursor round-trip/tamper/stale/retained.

## 7. Corrections during the packet

- A wrong default of `"official"` for `content_class` where the frozen model carries no
  value was replaced with `"unknown"` (never invent a content class).
- `to_gap` originally referenced a non-existent `GapScope.CATALOG`; the frozen enum has
  no such member, so the mapping uses `GapScope.SYSTEM` and keeps the finer role in the
  problem's own `scope` field.
- `plain()`-based serialisation flattened `UNKNOWN` to `"unknown"`; explicit `to_dict`
  overrides on `CatalogSource`/`CatalogEntry` encode the sentinel losslessly.

## 8. Deliberate limitations

- Only synthetic fixtures and a private temp root are used; no original database, no
  upstream fetch, no service start, no CIE batch resume.
- The staged catalog is not fed by real data and is not the production index; the SQLite
  decision execution and migration are Phase B.
- Quality promotion past `unverified` is not performed; it is rejected unless an
  authoritative evidence label is present, and no such label is attached to synthetic
  fixtures.
- Active materials/timetable integration stays deferred to the active owner.

## 9. Remaining gaps

- The real catalog database, its migration, and cutover remain behind the closed gates
  (`real_data_write_authorized`, `existing_service_cutover_authorized`).
- No real mapping volume exists to size the aggregate read index; the SQLite threshold in
  `A09_STORE_DECISION.md` is a stated future trigger, not a measurement.
- The inherited A06 runner stderr-reader race remains (frozen packet, not an A09
  regression) and is left documented.

## 10. Next action

**A10 — isolated v2 API**: an application factory under the staged package (never
importing the original `app.py`), the §5.1 envelope, the §5.2 error map (409 =
identity/revision/hash conflict incl. stale cursor), the §5.4 routes, and an OpenAPI
document that agrees with the running staged app. Materials/timetable use clearly
labelled test fixtures only; no link claims an unavailable production feature.
