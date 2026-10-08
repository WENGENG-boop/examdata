# A09 — catalog store decision (architecture record, plan §7.2 / §7.3)

**Status:** staged decision for Phase A. Not merged, not deployed. Phase B storage is
deferred and gated.

## Decision

The staged catalog store is a **file-backed, immutable JSON revision snapshot behind
an atomically-replaced pointer file**, not a SQLite database.

- `revisions/<dataset_revision>.json` — one immutable revision body (entries, counts,
  fixed input revisions, explanations, problems). Written once through a temp file and
  `os.replace`; an existing revision with a different body is refused.
- `current.json` — a small versioned pointer (`schema: catalog-pointer/1`) holding
  `dataset_revision`, `published_at` and `previous`, replaced atomically.
- Publication is compare-and-swap: a builder that read an older current and then tries
  to publish is refused (`StalePublisherError`), so a stale builder cannot overwrite a
  newer revision. The previous revision is retained for rollback and for cursors bound
  to it.

## Why this satisfies §7.3

Plan §7.3 is inherently filesystem-shaped: build into a run-owned staging directory,
publish an immutable revision, replace a pointer atomically without symbolic-link
privileges, keep the previous revision, and leave the pointer unchanged on failure.
A JSON revision body plus an atomic pointer file implements steps 2–9 directly with
stdlib only (`os.replace`, `uuid`-named temp files), and every one of those properties
is asserted by the A09 tests and probe:

- failed validation (no snapshot, or a revision that does not match its entries) leaves
  `current.json` byte-identical;
- concurrent publishers are tested with compare-and-swap;
- rollback restores the retained previous revision atomically;
- a cursor bound to a revision is refused as stale (409) once that revision is no
  longer published, and resolves while it is retained.

## Why not SQLite yet

§7.2 defaults to a separate SQLite catalog database **unless a measured fixture-scale
implementation proves a simpler JSON snapshot sufficient**. The staged scope is exactly
that measurement:

- every staged catalog fixture is a handful of entries (the base fixture has 5 rows);
- the whole catalog for the current synthetic scope is small enough that a full
  snapshot rewrite is cheap and a whole-file atomic replace is trivially safe;
- the aggregate read index is not yet fed by real data — no original database is read,
  no upstream source is fetched, and no real mapping volume exists to size an index for;
- introducing SQLite now would add a schema, a migration path and a second write
  surface before there is any measured pressure to justify them, and would risk
  touching the primary schema (§7.2 forbids that).

## Threshold that would force SQLite

Revisit this decision and move to the separate SQLite catalog database (§7.2) as soon as
any of the following is measured on real (Phase B) data:

1. the catalog exceeds roughly **10⁵ entries**, or a full snapshot JSON exceeds roughly
   **50 MB** — at which point a whole-file rewrite and full in-memory diff stop being
   cheap;
2. a query needs an index the in-memory store cannot provide within the response budget
   (e.g. substring/ranked search over searchable fields at scale);
3. concurrent writers beyond compare-and-swap of a single pointer are required;
4. per-entry incremental updates become the norm rather than whole-revision publication.

Until one of those is measured, the JSON snapshot stays. The store is deliberately
narrow (mapping row → stable ID + native locator + quality + lineage, references rather
than duplicated raw files, §7.2), so a future move to SQLite is a re-implementation of
`CatalogStore`/`RevisionPublisher` behind the same model, not a change to the contracts.

## Scope boundary

This record covers the **staged** store only. The real catalog database, its migration,
and the cutover are Phase B and remain behind the closed gates
(`real_data_write_authorized`, `existing_service_cutover_authorized`). No original
database, schema or service is touched by this decision.
