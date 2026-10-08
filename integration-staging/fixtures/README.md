# Staged fixtures (Phase A)

Fixture files copied into this directory are the only stable inputs staged tests
may read. Original trees stay read-only: nothing under `examdata/`, `ielts-api/`,
`ielts-data/`, `toefl-api/`, `frontend/`, or the probe directories is read by
staged tests.

Rules (plan section 11/A03):

- every fixture gets a provenance entry (source path, source hash, before-copy
  hash, destination hash, after-copy hash, scope, access notes);
- small representative artifacts only: no credentials, no original databases,
  no whole caches, no active-owner modules;
- synthetic fixtures are labelled `synthetic_fixture`;
- if a source file changes between hashes, mark it unstable and defer it
  instead of copying it again.

The provenance manifest (`fixtures/PROVENANCE.json`, human-readable twin
`fixtures/PROVENANCE.md`) is written by `integration-staging/tools/a03_capture_fixtures.py`
and verified by `integration-staging/tests/test_fixture_provenance.py`.

## Layout

| Path | Contents |
| --- | --- |
| `copied/` | byte-identical snapshots of small, non-active upstream JSON metadata (`copied_snapshot`) |
| `synthetic/` | hand-authored fixtures carrying `"fixture_kind": "synthetic"` inside the file (`synthetic_fixture`) |

`copied/` holds metadata only: revision pointers, a PDF-import provenance manifest,
a printed-page map, a subject-catalogue list and a third-party content index. No
examination question text, no timetable data, no database and no credential is copied —
sources of that kind are recorded in the manifest's `deferred_sources` list instead.
