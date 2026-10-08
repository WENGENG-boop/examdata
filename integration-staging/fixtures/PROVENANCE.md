# A03 fixture provenance

- schema: `examdata.integration.fixture-provenance/1`
- generated: 2026-10-05T19:16:40+08:00 (local) / 2026-10-05T11:16:40+00:00 (UTC)
- generator: `integration-staging/tools/a03_capture_fixtures.py` (sha256 `2636b1e4dfe6242dd6449739e41725b34a2b2a9fdc3142c6bcc0645ec254c3ea`)
- summary: {"by_kind": {"copied_snapshot": 6, "synthetic": 3}, "copied": 6, "copied_bytes": 137668, "deferred": 0, "entries": 9, "skipped": 0, "synthetic": 3}

## Copied fixtures (`copied_snapshot`)

| fixture | source | source sha256 (before == after) | dest sha256 | bytes | status |
| --- | --- | --- | --- | --- | --- |
| ielts-indexes-current | `ielts-data/indexes/current` | `b786b370117affa1` | `b786b370117affa1` | 156 | copied |
| ielts-manifests-current | `ielts-data/manifests/current` | `c1f3d59caa348ccf` | `c1f3d59caa348ccf` | 157 | copied |
| ielts-pdf-provenance | `ielts-data/manifests/pdf-provenance.json` | `0725aa6213084e6f` | `0725aa6213084e6f` | 52580 | copied |
| ielts-printed-pages | `ielts-api/data/printed-pages.json` | `ab876413450ca749` | `ab876413450ca749` | 44949 | copied |
| edexcel-subjects-source | `frontend/edexcel-subjects-source.json` | `b293e88820c43f0a` | `b293e88820c43f0a` | 22614 | copied |
| toefl-ddy-index | `toefl-api/data/ddy-index.json` | `50dc50a58bb65365` | `50dc50a58bb65365` | 17212 | copied |

## Synthetic fixtures (`synthetic_fixture`)

| fixture | destination | bytes | synthetic marker | scope |
| --- | --- | --- | --- | --- |
| ielts-questions-synthetic | `integration-staging/fixtures/synthetic/ielts/questions-synthetic.json` | 4542 | True | Hand-authored IELTS-shaped question set for identity tests: native ids, aliases, grouped alternatives, parent answers, the missing Q41 slot |
| cie-index-synthetic | `integration-staging/fixtures/synthetic/cie/cie-index-synthetic.json` | 3044 | True | Hand-authored CIE-shaped paper index for identity tests: question hierarchy, table structure, unknown date, answer conflict, required image, lineage |
| edexcel-index-synthetic | `integration-staging/fixtures/synthetic/edexcel/index-synthetic.json` | 1712 | True | Hand-authored Edexcel-shaped paper index for identity tests: unit/paper codes, session labels, qualification levels |

## Sources inspected and deferred

| source | status | reason |
| --- | --- | --- |
| `cie-index-batch-2026-10-01/9709/2024-Jun-11/cie-index.json` | deferred_examination_material | Contains verbatim examination question text extracted from a CIE paper: examination material, and the CIE batch is stopped and off-limits. The CIE adapter will be tested against a schema-shaped synthetic fixture instead. |
| `ielts-data/indexes/rev-8b21015ab64bb73c/questions.json` | deferred_too_large | 15 MB derived question index: exceeds the small-representative-artifact cap and is derived from examination material. |
| `toefl-api/data/jj-index.json` | deferred_maybe_active | Modified during the same day as this packet (2026-10-05 09:47 local): treated as potentially active, so it is not copied. |
| `frontend/catalog.json` | deferred_build_artifact | 577 KB build artifact of the frontend pipeline (regenerable, above the size cap). |
| `ielts-data/normalized/normalized-v1/rev-8b21015ab64bb73c/cambridge-1-1.json` | deferred_derived_exam_content | ~175 KB normalized test content derived from examination material; representative synthetic fixtures are used instead. |

Scope notes:

- Copied fixtures are byte-identical snapshots of small, non-active JSON metadata files; they contain no credentials, no database, no examination question text and no timetable data.
- Synthetic fixtures are hand-authored, contain no upstream data, and carry `"fixture_kind": "synthetic"` inside the file.
- The manifest is the authority for fixture integrity; `integration-staging/tests/test_fixture_provenance.py` verifies it against the files on disk.
