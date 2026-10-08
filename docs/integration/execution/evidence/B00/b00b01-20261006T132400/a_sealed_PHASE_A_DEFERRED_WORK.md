# PHASE_A_DEFERRED_WORK — deferred items, ownership release, and the Phase B gate checklist

Companion to `docs/integration/execution/PHASE_A_REPORT.md`. This document lists what Phase A
deliberately did **not** do, what it could not verify, what the human user must supply to open
Phase B, and the gate checklist that Phase B must satisfy before any merge, migration, service
cutover, upstream request, CIE resume, deployment or cleanup.

The authoritative machine-readable records are `docs/integration/execution/execution-ledger.json`
(`deferred_work`, `gates`) and `docs/integration/execution/ownership.json` (`active_owner`,
`prohibited_operations`, `gates_record`).

## 1. Deferred work register

| ID | Item | Why deferred | Revisit at | Evidence |
| --- | --- | --- | --- | --- |
| DEF-01 | Materials, syllabus and timetable read features (Kimi-owned active code) | The active owner is still modifying the original project; the original paths are protected; no active-owned module may be copied or executed during Phase A | Phase B after explicit human release (packet B05) | `evidence/A00/owner_observation.txt`; `A00_INITIAL_REPORT.md` §3 |
| DEF-02 | Kander review module (`rules.review`) | Its git-commit / worktree / reviewer-runtime mechanics conflict with Phase A isolation (no git operations, no worktrees); reviewer CLIs are present but unused | Phase B kickoff (offer to the user) | `A00_INITIAL_REPORT.md` §8; `evidence/A00/checks_after_root_creation.txt` §4 |
| DEF-03 | Phase B packets B00–B10 (merge, data migration, service integration, deployment proposal) | All seven gates closed; only an explicit human instruction opens `original_paths_released` | On explicit human release of the original paths | `execution-ledger.json` tasks B00–B10; `ownership.json` `gates_record` |
| DEF-04 | Stopped CIE batch resume | Not authorized (plan §0.6 item 11; gate `cie_resume_authorized` closed) | Only with an explicit `cie_resume_authorized` instruction | `execution-ledger.json` `gates.cie_resume_authorized` |
| DEF-05 | Remote deployment | No target or authorization exists; plan §9/§12 require reporting `not_run` until a real target and authorization are recorded | Phase B only, with an explicit `remote_deployment_authorized` instruction | `execution-ledger.json` `gates.remote_deployment_authorized` |
| DEF-06 | Auto-promotion of staged work | Prohibited (plan §0.6 item 12); a `staged_pass` never becomes a merged result without Phase B release and review | Never automatic; only via Phase B packets after release | `ownership.json` `prohibited_operations` item 12 |

## 2. Phase A limitations carried forward

These are honest limits on what Phase A could prove. They are **not** failures; they are the
boundary of the isolated phase, and each maps to a Phase B packet.

| Limitation | Detail | Owner packet |
| --- | --- | --- |
| Wheel not built | The shared venv has no `setuptools`/`wheel`/`build`; Phase A may neither install into it nor fetch a build backend. The packaging proposal records the B09 command (`python -m build --wheel`) instead of an unverifiable artifact | B09 |
| Database rollback unit `not_run` | No live database is opened in Phase A; the reversal is documented and rehearsed in every other unit | B08 |
| Target layout is a proposal | Plan §3.5 leaves final module names to Phase B; the map proposes `examdata/src/examdata/integration/**` and records `layout_decision` as a B01/B02 review point | B01/B02 |
| Six planned original edits have no staged file | The edits themselves are Phase B work; the map records the base hash, owning packet and reversal for each | B02/B04/B06/B10 |
| Base hashes are point-in-time | The original tree is actively edited by the owner; drift is observed and recorded, never repaired by this executor | B00/B01 |
| Staged docs are drafts | Plan §9.3 updates shared documentation only after the Phase B release | B10 |
| Worksheet does not cover Kimi-added routes | The 71-route baseline is covered; routes added after the snapshot are re-derived in Phase B | B00 |

## 3. Ownership release requirements

Phase A has stopped and is waiting. The original project was read-only throughout, and it stays
protected until a human says otherwise.

**Release rule** (`ownership.json.active_owner.release_rule`):

> Phase B gate `original_paths_released` opens only on explicit human instruction after the
> owner's work is finished. Kimi inactivity or a "done" message does not release any path;
> staged work must not be promoted because the owner went quiet.

**Gate rule** (`ownership.json.gates_record.rule`):

> All seven gates start false. Only explicit human instructions open a gate, and each opened
> gate must record the human instruction text, timestamp, scope, and constraints.
> `original_paths_released` alone opens none of the others.

To release the original paths, the human user must provide **all four** of the following, which
the executor records in `execution-ledger.json.gates.original_paths_released`:

1. **Instruction text** — the exact human instruction that releases the paths.
2. **Timestamp** — when the release was given.
3. **Scope** — which original paths are released (a named subset or all of them).
4. **Constraints** — what remains protected.

Until then the executor does not poll, does not open Phase B, and does not promote any staged
work.

## 4. Phase B gate checklist

Every gate starts `false` and stays false until the human opens it with a recorded instruction.
Phase B may not proceed past a gate that its packet requires until that gate is open.

| # | Gate | Opens only on | Needed by |
| --- | --- | --- | --- |
| 1 | `original_paths_released` | Explicit human release instruction (text, time, scope, constraints) | B00–B07, B09, B10 |
| 2 | `real_data_write_authorized` | Explicit authorization to write real data | B03, B08 |
| 3 | `existing_service_cutover_authorized` | Explicit authorization to cut services over | B02, B06, B07 |
| 4 | `upstream_requests_authorized` | Explicit authorization to make upstream requests | B05 (and any crawl) |
| 5 | `cie_resume_authorized` | Explicit authorization to resume the stopped CIE batch | any CIE batch work |
| 6 | `remote_deployment_authorized` | Explicit authorization to deploy remotely | B10 |
| 7 | `original_cleanup_authorized` | Explicit authorization to clean up originals | B10 |

**Coupling:** opening gate 1 opens none of the others. In particular, permission to merge code
(gate 1) does **not** authorize database migration (gate 2), service restarts or cutover
(gate 3), upstream crawling (gate 4), CIE resume (gate 5), cleanup (gate 7), or deployment
(gate 6).

## 5. Phase B entry conditions

When the human releases the original paths, Phase B begins at **B00** and must:

1. record the release instruction text, timestamp, scope and constraints;
2. re-read Kimi's final work — routes, tests, reports and source hashes — and take a fresh
   baseline;
3. rebuild the compatibility worksheet, preserving all 71 baseline routes and adding any routes
   Kimi added after the Phase A snapshot;
4. preserve Kimi's implementation as the new baseline, and leave any file whose ownership is
   still ambiguous under protection;
5. apply the staged proposals with a three-way semantic reconciliation against the recorded base
   hashes, updating fixtures (with a recorded reason) only when the final baseline legitimately
   changed;
6. satisfy every applicable gate in section 4 before the action that gate guards.

Nothing in Phase A is merged or deployed, and this document makes no completion claim for the
integration or for any deployment.
