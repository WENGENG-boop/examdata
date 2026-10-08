# B01 Layout Decision — private candidate at the proposed final layout

- **Run id**: `b00b01-20261006T132400`
- **Status**: private-candidate validation only. Nothing here is merged or deployed; the original tree was neither imported nor written.
- **Scope**: release-independent half of B01 (F03). The three-way semantic reconciliation against a *released* original tree is gate-blocked (`gate:original_paths_released` closed) and is not attempted.

## 1. Proposed final layout

| Item | Staged (Phase A) | Proposed final target |
| --- | --- | --- |
| Python package | `integration-staging/src/examdata_integration/` | `examdata/src/examdata/integration/` |
| Package name | `examdata_integration` | `examdata.integration` (a new subpackage of `examdata`) |
| Contracts / schemas | `integration-staging/contracts/` | repo level `examdata/contracts/` (copied into the release bundle) |
| Legacy registry entry points | `examdata_integration.api.dataset:default_dataset` | `examdata.integration.api.dataset:default_dataset` |

Rationale (from `A14_MERGE_MAP.json` `requirements_for_merge.python`): the staged
`adapters/` and `api/` names collide with existing `examdata` packages, so the staged
package is re-rooted as a **new subpackage** `examdata.integration`. Every entry is one
file, so re-rooting is mechanical; no original file is overwritten by any python entry.

## 2. Private candidate built and validated

Built under `integration-staging/runtime/phase-b/b00b01-20261006T132400/private/`
(builder: `b01_build_private_copy.py`; validator: `b01_validate_layout.py`;
probe: `b01_import_probe.py`). The private tree is minimal — no venv, live DB, PDF/CIE
data, caches or secret config — and is the only import root used for the probe
(no staging `PYTHONPATH`, no `EXAMDATA_INTEGRATION_STAGING_ROOT` override).

| Check | Result | Evidence |
| --- | --- | --- |
| `examdata` resolves to the private shim, not the editable install | pass | probe `examdata_within_private: true` |
| Modules resolving **outside** the private tree | **0** | `B01_LAYOUT_VALIDATION.json` |
| Modules imported cleanly at the target layout | 49 | same |
| Modules that **failed** to import | **3** | same |
| `contracts/schema/*.json` load | 28 / 28 | same |
| Package-name rename left no stale `examdata_integration` in `.py`/`.json` | pass | `B01_PRIVATE_COPY_MANIFEST.json` |

## 3. Finding F03-GUARD-DEP (high) — product code depends on the test-only guard

At the proposed final layout the following fail to import with
`RuntimeError: staged package is not inside an 'integration-staging' tree`:

- `examdata.integration.runtime` (and everything importing it, e.g. `legacy` via
  `legacy/bridge.py: from ..runtime.classification import RunnerOutcome`)
- `examdata.integration.legacy`

**Root cause.** Product modules import the staging test harness guard:

```
src/examdata_integration/runtime/manifest.py   from ..testing.guards import STAGING_ROOT, is_within
src/examdata_integration/runtime/runner.py     (same guard)
src/examdata_integration/runtime/settings.py   (same guard)
```

`testing/guards.py::_resolve_staging_root()` requires the tree to be named
`integration-staging` (or an override env var), and `runtime/__init__.py` eagerly
imports `.manifest`. So any import of the runtime package raises once the package sits
at `examdata/src/examdata/integration/`.

**Why this matters.** `testing/guards.py` is test-only harness code; a product module
must not depend on it for its path root. Importing the package with the staging
override env set would be exactly the "let the wrong layout pass by leaning on the
staging PYTHONPATH" case the plan forbids, so it is recorded as a finding, not worked
around.

**Proposed fix (for B01/B02, not applied to the original tree).**
- Move the path-root computation into a product-safe module, e.g.
  `examdata/integration/runtime/paths.py`, that resolves roots from the deployment
  root it is given (as `manifest.py` already does for components) rather than from
  `__file__` parents or a directory-name heuristic.
- Keep `testing/guards.py` test-only: it keeps the isolation rule (refuse the original
  `examdata` tree) but is no longer imported by product code.
- In the target layout the guard's "block `examdata`" rule must change to: allow
  `examdata` / `examdata.integration` **only when they resolve inside the private
  tree**, and still refuse the real original `examdata/src` / shared editable checkout.

## 4. Node components and frontend (unchanged from A14, still not_run)

Real Node components (`ielts-api/**`, `toefl-api/**`) are not released, so component
discovery stays **not_run**; `fake-node-cli` and the synthetic manifest stay separate
from any production component list and must not be promoted. Frontend `tests/` and
`fixtures/` must stay out of the production static surface. These are B02/B06 items and
are deferred.

## 5. Deferred

- Released-tree three-way reconciliation (needs `original_paths_released`).
- Final import/resource adjustments after the fix above are applied to the candidate.
- `wheel` / clean-environment install — B09, not claimed here.

## 6. Evidence

```
docs/integration/execution/evidence/B01/b00b01-20261006T132400/
  B01_MERGE_MAP.json
  B01_LAYOUT_VALIDATION.json
  b01_build_merge_map_run.txt
  b01_layout_validation_run.txt
```
