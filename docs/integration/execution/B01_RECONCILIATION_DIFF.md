# B01 reconciliation diff (scope and limitation)

- reconciliation_kind: `carried_pending_release`
- limitation: No released tree exists, so no three-way (old base -> new released original -> staged proposal) or two-way comparison was performed. Every A14 entry is carried unchanged with an explicit deferred disposition; F01 is the only correction applied because it is verifiable read-only.

## Why no three-way / two-way comparison was performed

The prompt requires a three-way reconciliation (`old base -> new released original -> staged proposal`). The middle leg does not exist yet: `gate:original_paths_released` is closed and no human four-part release has been recorded in this session, so there is no released tree to read. A two-way comparison (staged proposal vs the A14 base bytes) is also deferred, because the A14 bases were captured before Kimi's continuing edits to the protected originals and reading them again would not constitute the released baseline. Every A14 entry is therefore carried with an explicit deferred disposition; F01 is the sole correction because it is verifiable read-only against the current tree.

## Disposition summary

| disposition | entries |
| --- | --- |
| deferred_pending_release | 247 |

| planned original edits | disposition |
| --- | --- |
| carried_pending_release | 6 |

## Per-group reconciliation notes (from the map)

### python

B01/B02 choose the final module names (plan 3.5). The proposal roots the staged package at examdata/src/examdata/integration/ (a new subpackage) because the staged adapters/ and api/ names collide with the existing examdata packages. Re-rooting module-by-module later is mechanical: every entry is one file. No original file is overwritten by any python entry; B04 registers the v2 router in the final app.py.

### tests

Rebase path constants (tests compute STAGING from __file__) onto the merged tree, and reconcile conftest.py: drop the staging path pins and the original-package import block, keep the private data-root pinning for integration fixtures. The two harness self-tests (test_harness_isolation.py, test_node_import_guard.py) only stay if B01 keeps the corresponding guards.

### contracts

Keep the schemas/examples at repo level (examdata/contracts/) and copy them into the release bundle (plan 10.4 lists contracts/schemas). Regenerate only through the generator (tools/a04_generate_schemas.py), never by hand.

### fixtures

Fixtures are private test data: no fixture may be presented as real source data, copied snapshots keep their provenance manifest, and synthetic labels stay visible (plan 8). The fixture provenance manifests record staging destination paths and must be reconciled to the merged locations.

### frontend

B06: reconcile app.js/index.html/README/tests with Kimi's final frontend (the staged copies are based on the hashes in frontend/PROVENANCE.json). Ensure the merged static server does not expose frontend/tests/ or frontend/fixtures/, and keep the reversible examdata.v2-client switch.

### config

B02: merge the example files into the project configuration surface without changing existing environment variable names; legacy aliases (IELTS_API_DIR, TOEFL_API_DIR) keep working and still fail loudly on conflict.

### docs

Plan 9.3: shared documentation is updated only after the Phase B release. These staged drafts are the proposed versions; B10 decides final names and folds in the remaining packets (materials/timetable, deployment).

