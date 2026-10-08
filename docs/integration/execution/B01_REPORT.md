# B01 Report — private-copy reconciliation (release-independent half)

- **Packet**: B01 (`PHASE_B_PENDING_RELEASE`)
- **Run id**: `b00b01-20261006T132400`
- **Status**: `partial` — F01 corrected and F03 layout validated in a private candidate; the three-way reconciliation against a *released* tree is gate-blocked and is recorded as a gap, not a pass.
- **Write roots used**: `integration-staging/`, `docs/integration/execution/` only.
- **Original tree**: read-only. `A14_MERGE_MAP.json` is byte-unchanged (sha256 `29940a0b0582b8b7e8e6fea79692ba849e3d25dd917dfa059d8bbda98fc3654a`).

> **Staged, not merged.** No original file was written, no service restarted, no database touched, no upstream request made, no CIE batch resumed, nothing deployed. All seven gates remain closed.

## 1. F01 corrected in a new B01 merge map

A14 targeted `examdata/cli.py` with `base_exists=false` but a "restore the recorded base
bytes" reversal. The real entry point, confirmed read-only:

| Fact | Value |
| --- | --- |
| Real CLI file | `examdata/src/examdata/cli.py` (exists, 60747 bytes) |
| Real CLI sha256 | `514f04204f85ee146d5c209d5c1a29c41a5306395ca8e40a5e1a7ee5d6b29292` |
| `examdata/cli.py` | does **not** exist |
| Entry point | `examdata = "examdata.cli:app"` (`examdata/pyproject.toml` `[project.scripts]`) |

`B01_MERGE_MAP.json` (new; the frozen A14 map is untouched) applies the correction:

- CLI target → `examdata/src/examdata/cli.py`, with `base_exists=true`, the real
  `base_sha256`, `entry_point=examdata.cli:app`;
- rollback semantics fixed: a **new** file is removed only if its candidate SHA256 still
  matches (never "restore bytes" for a file that had no base); an **existing** file is
  restored from the **B00 latest released base**, re-checking for later modifications —
  never restored from an A14 snapshot.

Map contents: **247 entries**, all carried with an explicit `b01_disposition` +
`b01_reason`; **92 `not_merged`** carried with a reason; 6 `planned_original_edits`; 9
`active_owner_deferred`. Zero entries were reconciled (the released tree does not exist)
and zero were promoted to pass.

Built by `b01_build_merge_map.py`; all seven build invariants true (A14 byte-unchanged,
247 entries all dispositioned, 92 not_merged, CLI target corrected to the real file, no
entry promoted). Evidence: `b01_build_merge_map_run.txt`, exit 0.

## 2. F03 layout validated in a private candidate

See `B01_LAYOUT_DECISION.md`. Private candidate at the proposed final layout
`examdata/src/examdata/integration/`, imported with the private tree as the only import
root:

- `examdata` resolves to the private shim, not the editable install;
- **0** modules resolve outside the private tree;
- **49** modules import cleanly; **3** fail;
- **28/28** `contracts/schema/*.json` load.

**Finding F03-GUARD-DEP (high).** `runtime/{manifest,runner,settings}.py` import the
test-only `..testing.guards`, whose root heuristic requires the tree be named
`integration-staging`. At the target layout `examdata.integration.runtime` (and `legacy`,
which imports it) fail with `RuntimeError: staged package is not inside an
'integration-staging' tree`. Fix proposed (not applied to the original tree): move the
path-root computation into a product-safe module and keep the guard test-only, with the
"block `examdata`" rule relaxed to "allow `examdata`/`examdata.integration` only inside
the private tree".

Real Node components stay **not_run** (not released); `fake-node-cli`/synthetic manifest
stay separate from any production component list.

## 3. Commands and evidence

| # | Command (cwd `C:/Users/weo/Desktop/api`) | Exit | Evidence |
| --- | --- | ---: | --- |
| 1 | `examdata/.venv/Scripts/python.exe integration-staging/runtime/phase-b/b00b01-20261006T132400/b01_build_merge_map.py` | 0 | `evidence/B01/.../b01_build_merge_map_run.txt`, `B01_MERGE_MAP.json` |
| 2 | `... b01_build_private_copy.py` | 0 | `private/B01_PRIVATE_COPY_MANIFEST.json` |
| 3 | `... b01_validate_layout.py` | 0 | `evidence/B01/.../b01_layout_validation_run.txt`, `B01_LAYOUT_VALIDATION.json` |
| 4 | `cd integration-staging && PYTHONDONTWRITEBYTECODE=1 ../examdata/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider` | 0 | `evidence/B01/.../b01_staged_pytest_rerun.txt` — **887 passed, 0 failed, 0 skipped** (2 warnings: `httpx2` deprecation, unknown `cache_dir` because `-p no:cacheprovider`) |

## 4. Deferred — blocked by a closed gate

`gate:original_paths_released` is closed; no human release credential exists in this
session. Therefore **not done** (recorded as gaps, not passes):

- the three-way (old base → new released original → staged proposal) reconciliation;
- released-tree re-derivation of the baseline/worksheet and re-classification of the 7
  `deferred_active_owner` routes;
- applying the F03 guard-dependency fix to a validated candidate;
- `wheel` / clean-environment install (B09).

Exact missing release scope: the human must record `original_paths_released` with
instruction text, timestamp, path scope and remaining constraints. Opening it opens none
of the others.

## 5. Evidence

```
docs/integration/execution/evidence/B01/b00b01-20261006T132400/
  B01_MERGE_MAP.json
  B01_LAYOUT_VALIDATION.json
  b01_build_merge_map_run.txt
  b01_layout_validation_run.txt
  b01_staged_pytest_rerun.txt
  b01_build_outputs_run.txt
docs/integration/execution/B01_LAYOUT_DECISION.md
docs/integration/execution/B01_MERGE_MAP.md
docs/integration/execution/B01_RECONCILIATION_DIFF.md
docs/integration/execution/B01_TEST_REPORT.md
docs/integration/execution/B01_ROLLBACK_PLAN.json
```

## 6. Next action

Resume the released-tree reconciliation only on an explicit human release. Otherwise
continue release-independent B01 preparation (apply the F03 fix in a fresh private
candidate and re-validate) and keep B01 `partial` with the exact missing release scope.

## 7. Suggested outputs

All six suggested outputs from prompt §3.3 now exist, derived from the frozen
`B01_MERGE_MAP.json` so they cannot drift from it:

- `B01_LAYOUT_DECISION.md`, `B01_MERGE_MAP.json`, `B01_REPORT.md` (earlier);
- `B01_MERGE_MAP.md` — 247 entries by group, 92 `not_merged`, 9 `active_owner_deferred`,
  6 `planned_original_edits`, plus the F01 correction;
- `B01_RECONCILIATION_DIFF.md` — reconciliation scope, the two-way/three-way limitation,
  disposition summary, per-group merge requirements;
- `B01_TEST_REPORT.md` — executed checks (887 suite, map build, layout validation) and the
  explicit `not_run` list with blocking gates;
- `B01_ROLLBACK_PLAN.json` — 247 entry actions + 6 planned-edit actions; new files use
  "delete only if the candidate SHA256 still matches", existing files use "restore the B00
  latest released base and verify no later modification is overwritten" (F01 semantics).

