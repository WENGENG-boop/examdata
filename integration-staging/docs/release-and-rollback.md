# Release and rollback (proposal)

Status: **proposed, staged only.** Nothing in this document has been merged, published,
installed, or deployed. It is the Phase A answer to plan section 10.4 ("the release bundle
must contain ...") and section 16.6 ("rollback is per unit, not per tree"). Phase B owns
every action described here.

Companion artifacts (both inside the Phase A writable roots):

- `docs/integration/execution/A14_RELEASE_MANIFEST.json` — the machine-readable bundle
  manifest described below.
- `docs/integration/execution/A14_MERGE_MAP.json` / `.md` — the file-by-file merge map with
  base hashes and per-file reversal.
- `docs/integration/execution/A14_REHEARSAL.json` — the rehearsal report for the reversible
  units that can be exercised offline.

## 1. What the release bundle contains

| Part | Proposed carrier | Where it comes from | Phase B action |
| --- | --- | --- | --- |
| Python package | `examdata` wheel | staged `integration-staging/src/examdata_integration/**` re-homed to `examdata/src/examdata/integration/**` | B02 decides the final module name, then builds |
| Node components | `ielts-api/`, `toefl-api/` as recorded baselines | existing original components | B02 records the final revision and packages them |
| Frontend assets | `frontend/**` (client, fixtures, tests) | staged `integration-staging/frontend/**` | B06 merges and wires the switch |
| Contracts and schemas | `examdata/contracts/**` | staged `integration-staging/contracts/**` | B01/B02 copy; no runtime reads them, tests do |
| Component manifest | `examdata.component-manifest/1` JSON | staged `integration-staging/contracts/component-manifest*.json` | B02 points the manifest at the merged paths |
| Dependency versions | recorded in the release manifest | `importlib.metadata` observations from the private venv | B02 re-observes after the merge |
| Configuration examples | `examdata/config.example.json`, `examdata/.env.example` | staged `integration-staging/config/staging-config.example.json`, `staging.env.example` | B02 installs as examples only |
| Migration tooling | catalog `RevisionPublisher`, identity mapper, quality transitions | staged Python package | B08/B09 run against the real data roots |
| Smoke checks | the table in section 3 | staged tooling | B09/B10 run them on the merged tree |
| Rollback instructions | section 4 | this document | shipped with the bundle |

Business data and secrets are **excluded** from the code package (plan 10.4). The bundle
carries code, schemas, examples, and instructions; the data roots stay where they are and
are addressed by configuration.

## 2. Packaging status and the one blocked step

The Python package is prepared as an importable source tree, not a built wheel. The staged
`pyproject.toml` change is a one-line extension of the existing `examdata` project: the
`packages.find` configuration already uses `where = ["src"]`, so re-homing the staged tree
under `examdata/src/examdata/integration/` is picked up without touching `[tool.setuptools]`.

Building a wheel is **deferred** (DEF: no offline build backend). The Phase A interpreter
`examdata/.venv/Scripts/python.exe` has no `setuptools`, `wheel`, or `build`, and Phase A
may not install into the shared virtual environment or fetch a build backend from the
network. The wheel therefore cannot be produced or verified in Phase A without violating
the isolation boundary.

Phase B command, once the environment is allowed to change:

```powershell
examdata\.venv\Scripts\python.exe -m build --wheel --outdir integration-staging\dist
```

Until then, the package is validated the way Phase A can validate it: imported from
`integration-staging/src`, exercised by the staged test suite, and described by the release
manifest with the observed dependency versions.

## 3. Smoke checks

Each check is a command a reviewer can run on the staged tree today. They prove the parts
that do not need the original project, the live database, or the network.

| Check | Command (from the project root) | Proves |
| --- | --- | --- |
| Offline doctor | `examdata/.venv/Scripts/python.exe -c "import sys; sys.path.insert(0,'integration-staging/src'); from examdata_integration.runtime import doctor; print(doctor.report())"` | Configuration resolves and components are discoverable without touching a source |
| v2 app factory | `examdata/.venv/Scripts/python.exe integration-staging/tools/a10_probe_api.py` | OpenAPI and runtime responses agree; envelope and error map hold |
| Node runner | `examdata/.venv/Scripts/python.exe integration-staging/tools/a06_probe_runner.py` | Controlled runner: allowlist, budgets, classification, no orphan process |
| Catalog build, publish, rollback | `examdata/.venv/Scripts/python.exe integration-staging/tools/a14_rehearsal.py` | Revision pointer publication and rollback on private fixtures |
| Frontend fixture flows | `node --test integration-staging/frontend/tests/*.test.mjs` | Staged client and fixture server flows over `127.0.0.1` only |
| Staged test suite | `cd integration-staging && ../examdata/.venv/Scripts/python.exe -m pytest -c pytest.ini` | The whole staged contract, offline, in the isolated harness |

All six are offline. The staged network guard is proven to reject real outbound calls
(A02), so a passing run cannot be explained by an accidental live request.

## 4. Rollback, per unit

Rollback is not a whole-tree operation. Plan 16.6 names six units; each is reversed
independently, so a bad release can be undone one layer at a time.

### 4.1 Code release

Reversal is per file, driven by `A14_MERGE_MAP.json`:

- Every `modified_copy` / `reconcile_modify` entry records the base bytes hash of the
  original file; restore those bytes.
- Every `new_file` / `add_file` entry is reversed by deleting the file.
- Every `copied_snapshot` / `verify_copy` entry needs no reversal beyond deleting the copy
  if the copy itself is unwanted.

Rehearsed offline in `A14_REHEARSAL.json` ("file rehearsal"): the map's entries are applied
into a sandbox and rolled back, and the sandbox is compared byte-for-byte with the pre-apply
state.

### 4.2 Component manifest

Reversal is restoring the previous manifest file. Component discovery re-reads the manifest
from disk on every resolution; there is no cached registry to invalidate.

Rehearsed offline ("manifest rehearsal"): the manifest set is loaded from a sandbox
deployment root, swapped, re-read, and restored.

### 4.3 Data revision pointer

Reversal is `RevisionPublisher.rollback()`: the `current` pointer moves back to the retained
`previous` revision. Both revisions stay readable, so a rollback never destroys the newer
build.

Rehearsed offline ("pointer rehearsal"): publish revision A, publish revision B, roll back,
and confirm `current` resolves to A while B remains present.

### 4.4 Database backup

Reversal is restoring the recorded backup and then reconciling writes made after it. Never
restore over new writes without freezing them first.

**not_run in Phase A** — no live database is touched (B08). This unit is documented, not
rehearsed.

### 4.5 Frontend switch

Reversal is flipping the switch, not reverting files. The staged client reads the
`examdata.v2-client` marker from storage: `setClientEnabled(false)` writes `off`, and
removing the marker switches the v2 client back on. No file change is needed in either
direction.

Rehearsed offline ("frontend switch rehearsal") against a fake storage, proving both
directions are reversible without touching disk.

### 4.6 Job checkpoint

There is nothing to reverse: the operations readers are read-only and never rewrite a
checkpoint. Reversal is therefore "no action", and the rehearsal proves it by confirming a
fixture checkpoint is byte-identical before and after a read.

## 5. Migration and rollback rehearsal

The rehearsal runs against private fixtures in a sandbox under
`integration-staging/runtime/rehearsal/`. It exercises the four units that can be exercised
without protected resources (code release, component manifest, data revision pointer,
frontend switch), records the checkpoint unit as read-only, and records the database unit as
`not_run`. Results and per-unit evidence are in
`docs/integration/execution/A14_REHEARSAL.json`; raw output is in
`docs/integration/execution/evidence/A14/rehearsal_stdout.txt`.

## 6. Exclusions

The bundle and this document deliberately exclude:

- live databases and business data (examdata `.db` files, the ielts-data corpus, CIE batch
  state);
- credentials, API keys, tokens, and any secret;
- Kimi-owned active modules (materials, timetable) and Kimi's in-flight edits to shared
  files;
- the synthetic fixture component (`components/fake-node-cli`) and its manifest;
- Phase A tooling, private runtime state, and staging provenance manifests.

## 7. What this document is not

- It is not a merge. Every path above is a proposal; the original tree was read-only
  throughout Phase A.
- It is not a deployment plan for Phase B itself. It says what the bundle contains, how each
  unit rolls back, and which checks prove the staged parts — the sequencing of Phase B
  belongs to the master plan.
- It does not claim the integration is complete. Phase B gates remain closed and are
  reported as deferred in the execution ledger.
