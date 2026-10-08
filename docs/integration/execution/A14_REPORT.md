# A14 — Packaging and merge proposals (staged)

Packet A14 of `docs/integration/MASTER_EXECUTION_PLAN_EN.md` section 11:

> **A14 — Prepare packaging and merge proposals**
> **Write:** Proposed component release manifest, staged documentation, a file-by-file patch
> plan, migration/rollback rehearsal against private fixtures.
> **Steps:** Identify every eventual original target path and the base hash used to prepare it.
> Avoid a whole-tree replacement patch. List active-owner deferred files separately.
> **Pass:** A reviewer can see exactly what will change and how each change can be reversed.

Everything in this packet is **staged**: no original file was written, no original test or
application ran, nothing was merged, published, installed, or deployed. All seven Phase B
gates remain closed (`docs/integration/execution/execution-ledger.json`).

## 1. Scope

A14 turns the frozen A00–A13 staging tree into four reviewable proposals:

1. a **file-by-file merge map** — every staged candidate file, its eventual original target
   path, the base hash it was prepared from, the Phase B action, and the exact reversal;
2. a **proposed release manifest** — the bundle contents, observed dependency versions,
   smoke checks, exclusions and the six rollback units (plan 10.4, 16.6);
3. **staged documentation** — the proposed merged docs, plus a generated v2 API reference;
4. a **migration/rollback rehearsal** — every reversible unit exercised offline against
   private fixtures.

In scope: reading and hashing original files, reading two staging provenance manifests,
reading the private venv's package metadata, and writing inside the two Phase A roots only.

Out of scope and untouched: the original source, data, configuration, tests, documentation,
caches and checkpoints; the live database; ports 5188/8000; the shared virtual environment;
any upstream source; the stopped CIE batch; and every Kimi-owned materials/timetable module.

## 2. Deliverables

| Artefact | Size | What it is |
| --- | --- | --- |
| `docs/integration/execution/A14_MERGE_MAP.json` | 247 entries | Machine-readable merge map: `staged_path`, `staged_sha256`, `kind`, `proposed_target`, `target_observed`, `base`, `phase_b_action`, `reversal`, `verification`, plus `not_merged`, `planned_original_edits`, `active_owner_deferred` and `requirements_for_merge` |
| `docs/integration/execution/A14_MERGE_MAP.md` | generated | The same map as reviewable tables |
| `docs/integration/execution/A14_RELEASE_MANIFEST.json` | `release-manifest-proposal/1` | Proposed bundle: Python package, Node components, frontend assets, contracts/schemas, component manifest, dependency versions, configuration examples, migration tools, smoke checks, rollback instructions, exclusions, gates, `not_run` list |
| `docs/integration/execution/A14_REHEARSAL.json` | `a14-rehearsal/1` | Six rollback units, 21 checks, per-unit method and evidence |
| `integration-staging/docs/v2-api-reference.md` | generated | 39 documented v2 operations read from the staged app factory's OpenAPI document |
| `integration-staging/docs/integration-guide.md` | 10.9 KB | Proposed merged integration guide (plan 9.3 checklist) |
| `integration-staging/docs/release-and-rollback.md` | 9.3 KB | Proposed packaging, smoke checks and per-unit rollback instructions (plan 10.4) |
| `integration-staging/docs/README.md` | 1.5 KB | Staged docs index (not published before the Phase B release) |
| `integration-staging/tools/a14_build_artifacts.py` | tool | Builds and re-checks the four generated artefacts |
| `integration-staging/tools/a14_rehearsal.py` | tool | Runs the six-unit rehearsal in a private sandbox |

Merge map shape — 247 entries, 7 groups, 2 372 694 bytes:

| group | files | kinds | reversal |
| --- | --- | --- | --- |
| python | 62 | 62 new_file | 62 delete_file |
| tests | 43 | 43 new_file | 43 delete_file |
| contracts | 74 | 74 new_file | 74 delete_file |
| fixtures | 49 | 6 copied_snapshot, 43 new_file | 49 delete_file |
| frontend | 13 | 4 modified_copy, 2 copied_snapshot, 7 new_file | 6 restore_base_bytes, 7 delete_file |
| config | 2 | 2 new_file | 2 delete_file |
| docs | 4 | 4 new_file | 4 delete_file |

- **Not a whole-tree replacement.** Every entry is one file, and every entry carries its own
  reversal. Only 5 of the 247 targets already exist in the original tree (the frontend
  copies); the other 242 are new paths.
- **12 recorded bases, 0 drift observed** at build time. Base hashes are point-in-time
  observations of an actively edited tree: drift is recorded, never repaired here.
- **92 files are listed as `not_merged`** with a reason each: Phase A tooling (53), private
  staging runtime state (30), the synthetic fixture component (3), the staging test
  configuration and README (2), and the frontend/config provenance notes (3).
- **6 planned original edits** are listed separately, with the packet that owns each and the
  observed base hash, because the edit itself is Phase B work and no staged file can carry it:
  `examdata/src/examdata/api/app.py` (B04), `examdata/pyproject.toml` (B02),
  `examdata/cli.py` (B02/B10), `frontend/server.mjs` (B06), `examdata/docs/API.md` (B10),
  `docs/PROJECT_STATUS.md` (B10). `examdata/cli.py` is recorded as absent at observation time.
- **Active-owner deferred files** are listed in their own section of the map (materials,
  timetable, `api/{unified,ielts,toefl}.py`, `pyproject.toml`/`cli.py`/README, the frontend
  tree, `ielts-api/`, `toefl-api/`, `ielts-data/`, the CIE batch directories and the plan
  inputs): they are not merge candidates for this packet and are not to be copied or executed.

## 3. Validation model

Four independent checks, all offline:

1. **Map self-check** (`a14_build_artifacts.py --check`, rc 0). Recomputes every staged
   `sha256` from disk; re-observes every recorded base and reports drift; re-observes the six
   planned-edit bases; proves coverage — every file in the merge-candidate roots is either
   mapped or listed as `not_merged`; regenerates the Markdown and the v2 reference and compares
   them to the committed copies with the generation stamp stripped; and re-observes the
   dependency versions.
2. **Regeneration determinism.** The v2 reference is generated from `create_app().openapi()`;
   the generated document is byte-identical across processes and hash seeds (section 5.2).
3. **Rollback rehearsal** (`a14_rehearsal.py --check`, rc 0). Six units, 21 checks: every map
   entry applied into a sandbox and rolled back to a byte-identical pre-apply tree; manifest
   swap/re-read/restore; revision pointer publish → publish → rollback with both revisions
   still readable; the frontend switch toggled off and on against in-memory storage; three
   checkpoint fixtures read with unchanged hashes. The database unit is recorded `not_run`.
4. **Staged suites.** `887 passed` (pytest, isolated harness, private fixtures, offline) and
   `27/27` (node, frontend fixtures over `127.0.0.1` only).

Evidence labels stay honest: the map records `copied_snapshot` versus `new_file` versus
`modified_copy` per entry, the manifest records the smoke checks with the transcript that
proves each, and the rehearsal records `not_run` where a unit cannot be exercised.

## 4. Evidence

| Path | Proves |
| --- | --- |
| `evidence/A14/rehearsal_stdout.txt` | The six rehearsal units and all 21 checks, in order |
| `evidence/A14/pytest_run_stdout.txt` | `887 passed, 1 warning` |
| `evidence/A14/node_tests_stdout.txt` | `tests 27 / pass 27 / fail 0` |
| `evidence/A14/final_checks.txt` | The closing checks run (§1–§11) |

## 5. Corrections made in this packet

Four defects were found and fixed while preparing the map, the manifest and the rehearsal.
Each is recorded because it changes what a reviewer can rely on.

1. **The map's file walk included interpreter caches.** An in-packet `python -c` import wrote
   `__pycache__`/`*.pyc` under `integration-staging/src`, which the coverage check then
   reported as unmapped. The walk now excludes caches, pytest scratch
   (`runtime/pytest-temp`, `runtime/pytest-cache`) and the rehearsal sandbox
   (`runtime/a14-rehearsal`), so the check is stable: a full pytest run no longer changes the
   not-merged list, and `--check` passes immediately after a build.
2. **The staged v2 OpenAPI document was not reproducible.** FastAPI's default operation-id
   generator derives the id suffix from `list(route.methods)[0]` — a *set* — so the five
   GET+HEAD content rows published a different operation id in every interpreter process, and
   because one route yields one id for every method it accepts, the GET and HEAD operations
   shared an id as well. The staged app now installs a deterministic generator and registers
   GET and HEAD as sibling routes. Verified: 39 operations, 39 unique ids, identical across
   `PYTHONHASHSEED` 0/7/999; FastAPI's duplicate-operation-id warnings dropped from 5 to 0.
   This is a staged contract improvement, not a behaviour change: the documented route set is
   unchanged and the full suite still passes 887/887.
3. **A smoke-check command did not work as written.** `node --test <dir>` does not expand a
   directory on node v24.19.0 — it tries to load the directory as a module. The release
   instructions, the integration guide and the release manifest's smoke check now use the
   node-expanded glob `integration-staging/frontend/tests/*.test.mjs`, which runs 27/27.
4. **The rehearsal's first run failed honestly, and the map was right.** The rehearsal seeded
   the sandbox from every recorded base, but a `copied_snapshot` base is *provenance* — it
   proves the copy is faithful (`verify_copy`) — not a pre-existing target: the merge creates
   that path, so its reversal is `delete_file`. The seed rule is now limited to
   `restore_base_bytes` entries, and a new check proves every `copied_snapshot` is byte-faithful
   to its recorded base (8 copies) with no drift.

## 6. Deliberate limitations

- **No wheel is built.** The private interpreter has no `setuptools`, `wheel` or `build`, and
  Phase A may neither install into the shared venv nor fetch a build backend. The packaging
  proposal therefore describes the wheel and records the exact B09 command
  (`python -m build --wheel`) instead of producing an unverifiable artifact. This is the one
  step of plan 10.4 that Phase A cannot complete without leaving the isolation boundary.
- **The database rollback unit is `not_run`.** No live database is opened in Phase A; the
  reversal is documented and deferred to B08.
- **The target layout is a proposal.** Plan 3.5 leaves the final module names to Phase B, so
  the map proposes `examdata/src/examdata/integration/**` and records `layout_decision` as a
  B01/B02 review point. Re-rooting is mechanical because every entry is one file.
- **The six planned original edits have no staged file.** The edit itself is Phase B work; the
  map records the base hash, the owning packet and the reversal.
- **Base hashes are point-in-time.** The original tree is being edited by the active owner;
  drift is observed and recorded, never repaired by this executor.
- **The staged docs are drafts.** Plan 9.3 updates shared documentation only after the Phase B
  release; these are the proposed versions.

## 7. Remaining gaps

- DEF-01 (materials/timetable and the other active-owned modules) — deferred to Phase B after
  explicit human release of the original paths.
- DEF-03 (packets B00–B10: merge, migration, service integration, deployment) — all seven
  gates closed.
- DEF-04 (stopped CIE batch), DEF-05 (remote deployment) — not authorized.
- The wheel build (section 6) — B09.
- The real dataset revision and the compatibility worksheet rows for Kimi-added routes: the
  worksheet is re-derived in Phase B against the released tree.

## 8. Next action

A15 — assemble `docs/integration/execution/PHASE_A_REPORT.md`: the packet-by-packet summary,
the deferred-work list, the ownership-release requirements, and an explicit statement that
staged work is neither merged nor deployed while Phase B remains deferred.
