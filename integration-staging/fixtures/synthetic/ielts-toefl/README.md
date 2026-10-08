# A08 IELTS / TOEFL adapter fixtures

Hand-authored **synthetic** fixtures that drive the A08 read adapters
(`examdata_integration.adapters.ielts`, `...toefl`, `...source_reader`). They are
shaped like IELTS and TOEFL source documents but contain invented content only:
no upstream IELTS/TOEFL material, no real document hashes, no real audio, no real
KMF detail token, and no credentials.

They live in their own directory (not `../adapters/`) so the frozen A07 manifest,
which globs `../adapters/*.json`, stays fresh.

| File | Purpose |
| --- | --- |
| `ielts-questions-a08-synthetic.json` | A second synthetic IELTS book carrying a question `variant`, edition uncertainty, raw source ids, special numbering, an unresolved answer conflict and a missing answer slot. |
| `ielts-audio-synthetic.json` | Audio alignment states: a linked full recording, a claimed-but-unsupported `verified` alignment, an `unverified` time window and `unknown`/`not_applicable`. |
| `toefl-questions-synthetic.json` | Official / TPO / jj identity classes, a restricted (metadata-only) jj set, table-choice rows/columns, multiple-selection information, missing options/table, an unknown exam date and a bad KMF URL. |
| `toefl-bad-cache-synthetic.json` | A cache with a non-object entry, an entry with no identity and a duplicate identity, to check the adapter reports rather than drops them. |

Every fixture declares `"fixture_kind": "synthetic"` and a `verification.status`
of `"synthetic"`; nothing here may be promoted to verified content.

Provenance is recorded in `PROVENANCE.json` by
`integration-staging/tools/a08_capture_fixtures.py` (`--check` verifies it).
