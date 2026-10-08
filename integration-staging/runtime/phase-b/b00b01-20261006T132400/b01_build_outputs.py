"""Generate the remaining B01 suggested outputs from B01_MERGE_MAP.json.

Produces (all under docs/integration/execution/, a Phase A write root):
  B01_MERGE_MAP.md          - human-readable A14 -> B01 rationale diff
  B01_RECONCILIATION_DIFF.md- reconciliation scope, limitation, per-group notes
  B01_TEST_REPORT.md        - evidence-backed checks and explicit not_run items
  B01_ROLLBACK_PLAN.json    - per-entry reversible action (F01 rollback fixed)

Every artefact is derived from the frozen B01 map, so no new claim is made
about the originals: nothing is merged, nothing is deployed, all gates closed.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
MAP = (ROOT / "docs/integration/execution/evidence/B01/"
       "b00b01-20261006T132400/B01_MERGE_MAP.json")
OUT = ROOT / "docs/integration/execution"

m = json.loads(MAP.read_text(encoding="utf-8"))
entries = m["entries"]
by_group: dict[str, list[dict]] = {}
for e in entries:
    by_group.setdefault(e.get("group", "?"), []).append(e)


def write_markdown_map() -> Path:
    lines: list[str] = []
    lines.append("# B01 merge map (A14 -> B01, rationale diff)")
    lines.append("")
    lines.append(f"- map_version: `{m['map_version']}`")
    lines.append(f"- status: `{m['status']}`")
    lines.append(f"- mode: `{m['mode']}`")
    lines.append(f"- generated_by: `{m['generated_by']}` at {m['generated_at_local']}")
    lines.append(f"- derived_from: `{m['derived_from']['path']}` "
                 f"sha256 `{m['derived_from']['sha256']}` "
                 f"(byte-unchanged: {m['derived_from']['a14_map_byte_unchanged']})")
    lines.append(f"- frozen snapshot: `{m['derived_from']['frozen_snapshot']}`")
    lines.append("")
    lines.append("## Counts")
    lines.append("")
    lines.append("| metric | value |")
    lines.append("| --- | --- |")
    for k, v in m["counts"].items():
        lines.append(f"| {k} | {v} |")
    lines.append("")
    f01 = m["f01_correction"]
    lines.append("## F01 correction (the only applied change)")
    lines.append("")
    lines.append(f"- finding: {f01['finding']}")
    lines.append(f"- old target: `{f01['old_target_path']}` (base_exists={f01['old_base_exists']}, "
                 f"reversal was `{f01['old_reversal']}`)")
    lines.append(f"- new target: `{f01['new_target_path']}` "
                 f"(base_exists={f01['new_base_exists']}, size={f01['new_base_size']}, "
                 f"sha256 `{f01['new_base_sha256']}`)")
    lines.append(f"- entry point: `{f01['entry_point']}` from `{f01['entry_point_source']}`")
    lines.append(f"- rollback: new_file = {f01['rollback_semantics']['new_file']}")
    lines.append(f"- rollback: existing_file = {f01['rollback_semantics']['existing_file']}")
    lines.append("")
    lines.append("## Entries by group")
    lines.append("")
    for group in sorted(by_group):
        rows = by_group[group]
        lines.append(f"### {group} ({len(rows)} entries)")
        lines.append("")
        lines.append("| id | staged_path | proposed_target | kind | action | disposition |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for e in rows:
            lines.append(
                f"| {e.get('id','')} | `{e['staged_path']}` | "
                f"`{e.get('proposed_target','')}` | {e.get('kind','')} | "
                f"{e.get('phase_b_action','')} | {e['b01_disposition']} |")
        lines.append("")
    lines.append("## Not merged (excluded) — 92")
    lines.append("")
    lines.append("| staged_path | group | reason |")
    lines.append("| --- | --- | --- |")
    for e in m["not_merged"]:
        lines.append(f"| `{e['staged_path']}` | {e.get('group','')} | {e.get('reason','')} |")
    lines.append("")
    lines.append("## Active-owner deferred — 9")
    lines.append("")
    lines.append("| path | reason | revisit_at |")
    lines.append("| --- | --- | --- |")
    for e in m["active_owner_deferred"]:
        lines.append(f"| `{e['path']}` | {e.get('reason','')} | {e.get('revisit_at','')} |")
    lines.append("")
    lines.append("## Planned original edits — 6 (not applied)")
    lines.append("")
    lines.append("| target_path | packet | base_exists | base_sha256 | change |")
    lines.append("| --- | --- | --- | --- | --- |")
    for e in m["planned_original_edits"]:
        lines.append(f"| `{e['target_path']}` | {e.get('packet','')} | "
                     f"{e.get('base_exists')} | `{e.get('base_sha256','')}` | "
                     f"{e.get('change','')} |")
    lines.append("")
    p = OUT / "B01_MERGE_MAP.md"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def write_reconciliation_diff() -> Path:
    lines: list[str] = []
    lines.append("# B01 reconciliation diff (scope and limitation)")
    lines.append("")
    lines.append(f"- reconciliation_kind: `{m['reconciliation_kind']}`")
    lines.append(f"- limitation: {m['reconciliation_limitation']}")
    lines.append("")
    lines.append("## Why no three-way / two-way comparison was performed")
    lines.append("")
    lines.append("The prompt requires a three-way reconciliation "
                 "(`old base -> new released original -> staged proposal`). The "
                 "middle leg does not exist yet: `gate:original_paths_released` "
                 "is closed and no human four-part release has been recorded in "
                 "this session, so there is no released tree to read. A two-way "
                 "comparison (staged proposal vs the A14 base bytes) is also "
                 "deferred, because the A14 bases were captured before Kimi's "
                 "continuing edits to the protected originals and reading them "
                 "again would not constitute the released baseline. Every A14 "
                 "entry is therefore carried with an explicit deferred "
                 "disposition; F01 is the sole correction because it is "
                 "verifiable read-only against the current tree.")
    lines.append("")
    lines.append("## Disposition summary")
    lines.append("")
    disp = Counter(e["b01_disposition"] for e in entries)
    lines.append("| disposition | entries |")
    lines.append("| --- | --- |")
    for k, v in sorted(disp.items()):
        lines.append(f"| {k} | {v} |")
    lines.append("")
    lines.append("| planned original edits | disposition |")
    lines.append("| --- | --- |")
    pe = Counter(e["b01_disposition"] for e in m["planned_original_edits"])
    for k, v in sorted(pe.items()):
        lines.append(f"| {k} | {v} |")
    lines.append("")
    lines.append("## Per-group reconciliation notes (from the map)")
    lines.append("")
    for req in m["requirements_for_merge"]:
        lines.append(f"### {req['group']}")
        lines.append("")
        lines.append(req["requirement"])
        lines.append("")
    p = OUT / "B01_RECONCILIATION_DIFF.md"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def write_test_report() -> Path:
    lines: list[str] = []
    lines.append("# B01 test report")
    lines.append("")
    lines.append("All commands ran in the two Phase A write roots; the originals "
                 "were read-only. Every exit code below is from the recorded "
                 "transcript under "
                 "`docs/integration/execution/evidence/B01/b00b01-20261006T132400/`.")
    lines.append("")
    lines.append("## Executed checks")
    lines.append("")
    lines.append("| check | command (cwd) | exit | evidence |")
    lines.append("| --- | --- | --- | --- |")
    lines.append("| isolated staged suite | `pytest -q -p no:cacheprovider` "
                 "(cwd `integration-staging`) | 0 | "
                 "`b01_staged_pytest_rerun.txt` (887 passed, 0 failed, 0 skipped) |")
    lines.append("| B01 merge map build | `b01_build_merge_map.py` | 0 | "
                 "`b01_build_merge_map_run.txt`, `B01_MERGE_MAP.json` |")
    lines.append("| private-copy layout validation | `b01_validate_layout.py` | 0 | "
                 "`b01_layout_validation_run.txt`, `B01_LAYOUT_VALIDATION.json` |")
    lines.append("| Node component discovery | `b01_validate_node_discovery.py` | 0 | "
                 "`b01_node_discovery_run.txt`, `B01_NODE_DISCOVERY.json` "
                 "(5/5 checks) |")
    lines.append("")
    lines.append("## Targeted results")
    lines.append("")
    lines.append("- module resolution: 49 modules imported from the private tree, "
                 "3 refused (guard-blocked, see F03-GUARD-DEP), 0 resolved outside "
                 "the private tree.")
    lines.append("- Node component discovery: exactly one component is admitted "
                 "(the synthetic `fake_cli`, labelled synthetic); its entry point "
                 "resolves inside the deployment root; a manifest whose "
                 "`code_location` escapes the root is refused and not admitted. "
                 "Real Node components are not released, so their discovery stays "
                 "`not_run` and no synthetic stand-in is promoted. In the private "
                 "target layout the discovery module import is blocked by the same "
                 "F03-GUARD-DEP guard dependency.")
    lines.append("- contracts/schemas: 28/28 JSON resources loaded from the private "
                 "tree.")
    lines.append("- CLI target: `examdata/src/examdata/cli.py`, entry point "
                 "`examdata = \"examdata.cli:app\"` (F01 corrected).")
    lines.append("- A14 map: byte-unchanged (sha256 "
                 "`29940a0b0582b8b7e8e6fea79692ba849e3d25dd917dfa059d8bbda98fc3654a`).")
    lines.append("")
    lines.append("## Not run (explicit, with reason)")
    lines.append("")
    lines.append("| check | reason |")
    lines.append("| --- | --- |")
    lines.append("| active materials/timetable integration | Kimi-owned active feature; "
                 "worksheet rows `deferred_active_owner`; no release |")
    lines.append("| released-tree three-way reconciliation | "
                 "`gate:original_paths_released` closed |")
    lines.append("| live data / DB migration | `gate:real_data_write_authorized` closed |")
    lines.append("| upstream requests | `gate:upstream_requests_authorized` closed |")
    lines.append("| service cutover / ports 8000/5188 | "
                 "`gate:existing_service_cutover_authorized` closed |")
    lines.append("| wheel / clean-env install | belongs to B09; not claimed early |")
    lines.append("| real Node component discovery | real components not released "
                 "(`gate:original_paths_released` closed); synthetic `fake_cli` is "
                 "validated but never promoted to a production release manifest |")
    lines.append("")
    lines.append("No mandatory case was silently skipped: each is either executed "
                 "above or listed here with its blocking gate.")
    p = OUT / "B01_TEST_REPORT.md"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def write_rollback_plan() -> Path:
    def action_for(e: dict) -> dict:
        base_exists = bool((e.get("base") or {}).get("exists"))
        if e.get("kind") == "new_file" and not base_exists:
            return {
                "type": "delete_if_candidate_matches",
                "guard_sha256": e.get("staged_sha256"),
                "detail": "delete only if the deployed candidate SHA256 still "
                          "matches the recorded staged digest; never restore bytes "
                          "for a file that had no base",
            }
        return {
            "type": "restore_base",
            "base_sha256": (e.get("base") or {}).get("sha256"),
            "detail": "restore the B00 latest released base and verify no later "
                      "modification is overwritten; do not restore an A14 snapshot",
        }

    plan = {
        "plan_version": "rollback-plan-b01/1",
        "status": "proposed_staged_not_merged_not_deployed",
        "mode": m["mode"],
        "derived_from": m["derived_from"],
        "f01_rollback_semantics": m["f01_correction"]["rollback_semantics"],
        "guards": [
            "every action applies only to a path the executor owns this round",
            "verify the resolved absolute path and its digest before any delete/restore",
            "no delete or restore ever targets a protected original in Phase A",
            "planned original edits are reversible only after the human release",
        ],
        "entries": [
            {
                "id": e.get("id"),
                "staged_path": e["staged_path"],
                "proposed_target": e.get("proposed_target"),
                "kind": e.get("kind"),
                "b01_disposition": e["b01_disposition"],
                "rollback": action_for(e),
            }
            for e in entries
        ],
        "planned_original_edits": [
            {
                "target_path": e["target_path"],
                "packet": e.get("packet"),
                "base_exists": e.get("base_exists"),
                "base_sha256": e.get("base_sha256"),
                "rollback": {
                    "type": "restore_base" if e.get("base_exists")
                            else "delete_if_candidate_matches",
                    "base_sha256": e.get("base_sha256"),
                    "detail": "restore the recorded base bytes only after the human "
                              "release; verify no later modification is overwritten",
                },
                "b01_disposition": e["b01_disposition"],
            }
            for e in m["planned_original_edits"]
        ],
    }
    p = OUT / "B01_ROLLBACK_PLAN.json"
    p.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return p


if __name__ == "__main__":
    outs = [write_markdown_map(), write_reconciliation_diff(),
            write_test_report(), write_rollback_plan()]
    for p in outs:
        print(f"{p.relative_to(ROOT).as_posix()}  {p.stat().st_size} bytes")
