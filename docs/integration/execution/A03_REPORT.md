# A03 — Capture safe fixtures (Phase A, `PHASE_A_ISOLATED_ONLY`)

- **Packet:** A03 of `docs/integration/MASTER_EXECUTION_PLAN_EN.md` §11
- **Status:** `staged_pass` (staged only — nothing merged, nothing deployed)
- **Date:** 2026-10-05 (local +08:00)
- **Dependencies:** A02 (private staging harness) — `staged_pass`
- **Writable roots used:** `integration-staging/` and `docs/integration/execution/` only

## 1. What the plan required (A03)

> **Read:** existing immutable JSON evidence and selected inactive source files.
> **Write:** fixture provenance manifest and copied fixtures under staging.
> **Steps:** record source path/hash, before-copy hash, destination hash, after-copy hash, scope, and licence/access notes where already present. Use small representative artifacts. Do not copy credentials, original databases, entire caches, or active-owner modules.
> **Pass:** stable copies match and have provenance. Synthetic fixtures are labeled synthetic.
> **Fail action:** if hashes change, mark that source unstable and defer it; do not repeatedly copy an actively changing file.

## 2. Copied fixtures (`copied_snapshot`)

Six byte-identical snapshots, 137,668 bytes total. `source_sha256_before == source_sha256_after == destination_sha256` for every one.

| Fixture | Source | Bytes | sha256 (source before/after == destination) |
| --- | --- | --- | --- |
| `ielts-indexes-current` | `ielts-data/indexes/current` | 156 | `b786b370117affa1a18c26f300c770f93690d438550bace4676965d149db77f7` |
| `ielts-manifests-current` | `ielts-data/manifests/current` | 157 | `c1f3d59caa348ccf2280a9e1ef7897d8dcf0034b7686f733f16d11bd5d9e685c` |
| `ielts-pdf-provenance` | `ielts-data/manifests/pdf-provenance.json` | 52,580 | `0725aa6213084e6fee1411451c66943f2e89225ebec935aa4f7a7342ca7aca2a` |
| `ielts-printed-pages` | `ielts-api/data/printed-pages.json` | 44,949 | `ab876413450ca749355e1b4489843c1acef235fd6059cea48dc76b52e8856432` |
| `edexcel-subjects-source` | `frontend/edexcel-subjects-source.json` | 22,614 | `b293e88820c43f0af404f36571dd83a040c12881312e528764919f7aa015a9bc` |
| `toefl-ddy-index` | `toefl-api/data/ddy-index.json` | 17,212 | `50dc50a58bb6536507bf1f508b1d959945e949d82a8aa0fe56149b11a8c37500` |

All six are **metadata**, not examination content:

- two revision pointers (`dataset_revision`, `published_at`, `artifact`);
- a PDF-import provenance manifest (pdf path, pdf sha256, page numbers);
- a printed-page resolution map (numeric pairs → page numbers);
- an Edexcel subject catalogue (titles, urls, Pearson category labels);
- a third-party TPO index (id, title, upstream file, link, paragraph/char counts — no passage text).

Access/licence hints already present in the sources (`source`, `board`, `generated_at_utc`, `checked_at`) are recorded per entry in `access_notes_from_source`.

## 3. Synthetic fixtures (`synthetic_fixture`)

Three hand-authored fixtures, each carrying `"fixture_kind": "synthetic"` and a `_provenance` block inside the file. They contain no upstream data and no real document hashes.

| Fixture | Bytes | Purpose |
| --- | --- | --- |
| `fixtures/synthetic/ielts/questions-synthetic.json` | 4,542 | native ids + aliases, grouped alternatives, parent answer with sub-parts, table question with answer cell, the **missing answer slot Q41**, an answer conflict, a required image, lineage |
| `fixtures/synthetic/cie/cie-index-synthetic.json` | 3,044 | CIE index shape: question + part hierarchy, table structure, unknown date, answer conflict, required image, lineage |
| `fixtures/synthetic/edexcel/index-synthetic.json` | 1,712 | Edexcel shape: qualification level, unit/paper codes, session labels, unknown dates, document roles |

## 4. Sources inspected and deliberately deferred

| Source | Status | Reason |
| --- | --- | --- |
| `cie-index-batch-2026-10-01/9709/2024-Jun-11/cie-index.json` | `deferred_examination_material` | Contains **verbatim examination question text** extracted from a CIE paper. Examination material is the active owner's area, and the CIE batch is stopped and off-limits. The CIE adapter is tested against the schema-shaped synthetic fixture instead. |
| `ielts-data/indexes/rev-8b21015ab64bb73c/questions.json` | `deferred_too_large` | 15 MB derived question index; above the small-artifact cap. |
| `toefl-api/data/jj-index.json` | `deferred_maybe_active` | Modified the same day (2026-10-05 09:47 local) → treated as potentially active. |
| `frontend/catalog.json` | `deferred_build_artifact` | 577 KB regenerable frontend build artifact. |
| `ielts-data/normalized/…/cambridge-1-1.json` | `deferred_derived_exam_content` | ~175 KB normalized test content derived from examination material. |

## 5. Mechanism

`integration-staging/tools/a03_capture_fixtures.py` (sha256 `2636b1e4dfe6242dd6449739e41725b34a2b2a9fdc3142c6bcc0645ec254c3ea`) enforces the rules rather than trusting them:

- deny list on directory components (`.venv`, `node_modules`, `__pycache__`, `.pytest_cache`, `.git`, `site-packages`, `.data`, `pdf`, `audio`, `downloads`, `raw`), on file suffixes (databases, archives, binaries, certificates), on name patterns (`.env*`, `credential`, `secret`, `token`, `password`, `id_rsa`, `*.pth`) and on path prefixes (original app code, execution records, IELTS derived/normalized/rev trees, CIE batch work);
- size cap 400 KB; source must be inside the workspace and outside the staging tree;
- before/after hashing of the source; a source whose hash changes across the copy is **removed from staging**, marked `deferred_unstable` and never re-copied in the same run;
- destination hash recomputed from the bytes actually written;
- canonical `fixtures/PROVENANCE.json` plus a human-readable `fixtures/PROVENANCE.md`;
- `--check` re-verifies the manifest against the files on disk without copying.

`integration-staging/tests/test_fixture_provenance.py` (11 tests) verifies the manifest independently of the tool: destination hash match, containment in the fixture root, copy stability (`before == after == destination`), synthetic labelling, deny-list absence, that the CIE examination index is recorded as deferred and is *not* copied, and a content canary (`"Express 3y"`, a verbatim fragment of the real CIE question) that must not appear in any fixture.

## 6. Evidence

| Evidence | Path | Label |
| --- | --- | --- |
| Capture run (9 entries, 6 copied, 3 synthetic, exit 0) | `docs/integration/execution/evidence/A03/fixture_capture_stdout.txt` | `copied_snapshot` |
| Independent source-vs-copy hash cross-check (all 6 MATCH) | `docs/integration/execution/evidence/A03/fixture_hash_crosscheck.txt` | `static_inspection` |
| Staged suite with the fixture tests (29 passed, exit 0) | `docs/integration/execution/evidence/A03/pytest_run_stdout.txt` | `synthetic_fixture` |
| Leak check | `docs/integration/execution/evidence/A03/leak_check_after_capture.txt` | `static_inspection` |
| Attribution of out-of-allowlist writes | `docs/integration/execution/evidence/A03/owner_activity_attribution.txt` | `static_inspection` |
| Closing checks transcript | `docs/integration/execution/evidence/A03/final_checks.txt` | `static_inspection` |

## 7. Leak check and attribution

- New `__pycache__` directories in protected roots during the window: **0**.
- Files outside the two allowlist roots during the window: the leak transcript lists **40** paths and carries a wider count line of **97** (the count was taken over a wider path set than the lines kept). Every listed path is attributable to the active owner's concurrent test run inside `examdata/`: its own `.pytest_cache`, its `pytest-of-weo/pytest-22..23` basetemps whose node names match examdata's suite (`test_asset_path_escape_is_deni0`, `test_cie_index_read_api_and_al0`, …), plus `examdata/docs/DEPLOY.md` and `examdata/examples/curl.md`. The executor's own basetemp is `integration-staging/runtime/pytest-temp`, and its recorded node names are only `test_fixture_provenance.py`, `test_harness_isolation.py`, `test_node_import_guard.py`. Owner activity is expected and is never repaired (plan §0.9).
- The attribution is now **machine-generated**: `integration-staging/tools/a03_attribution.py` rebuilds `evidence/A03/owner_activity_attribution.txt` from the leak transcript, the pytest transcript and a listing of the executor basetemp, and names both basetemps explicitly so the claim can be checked without trusting the executor.
- `git -C examdata status --porcelain` in the same window shows the owner modifying `src/examdata/adapters/registry.py`, `adapters/edexcel/*`, `docs/API.md`, `pyproject.toml` and others — further evidence that the original tree is under active modification and must stay untouched.

## 8. Pass criteria → result

| Criterion | Result |
| --- | --- |
| Stable copies match and have provenance | PASS — 6/6 stable, `before == after == destination`, full provenance per entry |
| Small representative artifacts | PASS — 156 B … 52 KB, 137,668 B total |
| No credentials, databases, caches, active-owner modules | PASS — deny list enforced at capture and re-checked by the tests |
| Synthetic fixtures labelled synthetic | PASS — 3/3 carry `fixture_kind: synthetic`; the test asserts it |
| Unstable sources deferred, not re-copied | PASS — mechanism implemented; no source was unstable in this run, and five sources were deferred for other stated reasons |
| Examination material not copied | PASS — the CIE index is deferred with reason; a content canary guards against leaks |

## 8b. Correction during close-out (recorded, not hidden)

The first A03 closing-checks run exited **1**: `leak_check.attribution_present` failed because the hand-written attribution transcript named the owner basetemps and the executor's basetemp *node names*, but never the executor basetemp **path** (`integration-staging/runtime/pytest-temp`). The check was not weakened; the evidence was made complete and reproducible instead:

- added `integration-staging/tools/a03_attribution.py`, which regenerates the attribution from recorded evidence (leak transcript + pytest transcript + basetemp listing) and prints both basetemp paths;
- regenerated `evidence/A03/owner_activity_attribution.txt` with that tool (transcript: `evidence/A03/attribution_generator_stdout.txt`), and split the single attribution check into four named checks;
- refreshed the A03 patch hashes and re-closed A03 in the ledger (command rows seq 15–17; `failures` records the failed first run).

## 9. Deferred / not done in A03

- No examination material, timetable data, database, credential or cache was copied; the CIE index and the IELTS normalized/derived trees stay in the original project.
- The fixtures are metadata shapes only: they cannot substitute for a real-data integration test. Real-data behaviour remains Phase B work behind the `real_data_write_authorized` gate.
- `toefl-api/data/jj-index.json` was treated as potentially active and deferred; if the owner confirms it is stable, a later packet may capture it.
- Fixture content is intentionally minimal — enough to exercise identity, provenance and schema behaviour in A04/A05, not a full corpus.

## 10. Staged vs merged vs deployed

- **Staged:** `integration-staging/fixtures/**` (12 files) and the A03 tooling/tests.
- **Merged:** nothing. The original project was only read.
- **Deployed:** nothing. All seven Phase B gates remain closed.

## 11. Next action

A04 — freeze contracts and identity rules (plan §11): implement the Section 4 models as staged Python, with JSON schemas, the identity canonicalization decision, the quality transition table and examples; test round-trip of native IDs, aliases, IELTS Q41, grouped alternatives, parent answers, table choices, unknown dates, conflicts, required images and lineage against the A03 synthetic fixtures.
