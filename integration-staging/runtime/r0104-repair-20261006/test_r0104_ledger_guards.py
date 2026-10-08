"""R01-R03 regression suite for the corrected b_ledger_update.py (private copies only).

Run:
    python integration-staging/runtime/r0104-repair-20261006/test_r0104_ledger_guards.py

Every operation runs against a PRIVATE COPY of the ledger via EXAMDATA_B_LEDGER.
The REAL ledger is never written. All credentials used to open a gate are
SYNTHETIC fixtures labelled `synthetic_credential`; no real gate is opened.

Covers:
  R01  unsupported status schema (done / merged_pass / arbitrary aliases refused)
  R02  protected patch fields refused; refusal preserves ledger bytes; a patch
       cannot remove prerequisites and then claim completion
  R03  action-level gate requirements; a private-preparation pass does not
       satisfy an original-action prerequisite
  positive controls: legitimate partial progress and a private-preparation pass

Exits 0 only when every rejection fires and every positive control holds.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

RUN = Path(__file__).resolve().parent
API = RUN.parents[2]
LEDGER = API / "docs/integration/execution/execution-ledger.json"
TOOL = API / "integration-staging/tools/b_ledger_update.py"
COPIES = RUN / "ledger-copies"
PY = sys.executable

FROZEN_LEDGER_SHA = "6d4449d3997b437fd3ea3a1fe7925fc78a7c0adbe0a5d3b793d6a8063101b4ba"

results: list[tuple[str, bool]] = []


def new_copy(name: str) -> Path:
    COPIES.mkdir(parents=True, exist_ok=True)
    dst = COPIES / name
    shutil.copy2(LEDGER, dst)
    return dst


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run(ledger: Path, *argv: str) -> tuple[int, str]:
    env = dict(os.environ)
    env["EXAMDATA_B_LEDGER"] = str(ledger)
    p = subprocess.run([PY, str(TOOL), *argv], capture_output=True, text=True,
                       cwd=str(API), env=env)
    return p.returncode, (p.stdout + p.stderr).strip()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def expect_refused(label: str, ledger: Path, *argv: str, text: str = "REFUSED",
                   forbid: str | None = None) -> bool:
    before = sha(ledger)
    code, out = run(ledger, *argv)
    ok = code == 2 and text in out
    if forbid and forbid in out:
        ok = False
        print(f"    rejected for the wrong reason: {forbid!r} present")
    if sha(ledger) != before:
        ok = False
        print(f"    LEDGER MUTATED by refused op {label}")
    first = out.splitlines()[0] if out else ""
    print(f"[{'PASS' if ok else 'FAIL'}] {label}: exit={code} {first[:110]}")
    if not ok:
        print(f"    full output: {out[:300]}")
    results.append((label, ok))
    return ok


def expect_ok(label: str, ledger: Path, *argv: str) -> tuple[bool, dict | None]:
    code, out = run(ledger, *argv)
    ok = code == 0
    data = load(ledger) if ok else None
    print(f"[{'PASS' if ok else 'FAIL'}] {label}: exit={code} "
          f"{(out.splitlines()[0] if out else '')[:100]}")
    if not ok:
        print(f"    full output: {out[:300]}")
    results.append((label, ok))
    return ok, data


def record(ledger: Path, task_id: str) -> dict:
    return {t["task_id"]: t for t in load(ledger)["tasks"]}[task_id]


def fixture_files() -> dict[str, Path]:
    """Synthetic fixtures (labelled as such) for the private copies."""
    d = RUN / "fixtures"
    d.mkdir(parents=True, exist_ok=True)
    files: dict[str, Path] = {}
    files["evidence_patch"] = d / "patch_evidence.json"
    files["evidence_patch"].write_text(json.dumps({
        "commands": [{"seq": 1, "purpose": "targeted regression", "tool": "Bash",
                      "command": "python test_r0104_ledger_guards.py",
                      "cwd": str(RUN), "exit_code": 0,
                      "evidence": "runtime/r0104-repair-20261006/evidence/"}],
        "exit_codes": [0],
        "test_results": [{"check": "r01_r02_r03", "result": "pass", "exit_code": 0,
                          "evidence": "runtime/r0104-repair-20261006/evidence/",
                          "label": "synthetic_fixture"}],
    }, indent=2), encoding="utf-8")
    files["claim_original"] = d / "patch_claim_original.json"
    files["claim_original"].write_text(json.dumps(
        {"original_changes_applied": True}, indent=2), encoding="utf-8")
    files["drop_prereqs"] = d / "patch_drop_prereqs.json"
    files["drop_prereqs"].write_text(json.dumps(
        {"dependencies": [], "blocked_by": []}, indent=2), encoding="utf-8")
    files["drop_then_complete"] = d / "patch_drop_then_complete.json"
    files["drop_then_complete"].write_text(json.dumps({
        "dependencies": [], "blocked_by": [],
        "commands": [{"command": "true", "exit_code": 0}],
        "test_results": [{"check": "x", "result": "pass", "exit_code": 0,
                          "evidence": "synthetic"}],
    }, indent=2), encoding="utf-8")
    files["benign"] = d / "patch_benign.json"
    files["benign"].write_text(json.dumps(
        {"notes": "legitimate partial progress (synthetic fixture)"}, indent=2),
        encoding="utf-8")
    files["synthetic_cred"] = d / "cred_synthetic.json"
    files["synthetic_cred"].write_text(json.dumps({
        "instruction": "SYNTHETIC credential for private-copy tests; opens no real gate.",
        "timestamp": "2026-10-06T13:00:00+08:00",
        "scope": "**",
        "constraints": "private copy only; no cutover, no live data, no network",
        "label": "synthetic_credential",
    }, indent=2), encoding="utf-8")
    return files


def precondition(ledger: Path, mutate) -> None:
    data = load(ledger)
    mutate(data)
    save(ledger, data)


def set_task(data: dict, task_id: str, **fields) -> None:
    for t in data["tasks"]:
        if t["task_id"] == task_id:
            t.update(fields)


def main() -> int:
    f = fixture_files()

    # ---------------- R01: unsupported status schema -------------------------
    l1 = new_copy("l01-status.json")
    expect_refused("R01 done", l1, "--task", "B01", "--status", "done",
                   text="claims original-side effects")
    expect_refused("R01 merged_pass", l1, "--task", "B01", "--status", "merged_pass",
                   text="claims original-side effects")
    for alias in ("complete", "finished", "DONE", "staged_pass_", "live", "deployed"):
        expect_refused(f"R01 alias {alias!r}", l1, "--task", "B01", "--status", alias,
                       text="REFUSED")
    # done with an evidence patch is still refused (schema check precedes everything)
    expect_refused("R01 done+evidence", l1, "--task", "B01", "--status", "done",
                   "--patch-file", str(f["evidence_patch"]),
                   text="claims original-side effects")

    # ---------------- R02: protected patch fields ----------------------------
    l2 = new_copy("l02-patch.json")
    expect_refused("R02 claim original_changes_applied",
                   l2, "--task", "B01", "--status", "partial",
                   "--patch-file", str(f["claim_original"]),
                   text="protected field")
    expect_refused("R02 drop dependencies+blocked_by",
                   l2, "--task", "B01", "--status", "partial",
                   "--patch-file", str(f["drop_prereqs"]),
                   text="protected field")
    expect_refused("R02 drop prereqs then claim completion",
                   l2, "--task", "B01", "--status", "staged_pass",
                   "--original-changes-applied", "false",
                   "--patch-file", str(f["drop_then_complete"]),
                   text="protected field")
    for bad in ("status", "mode", "task_id", "action", "guarded_action_gates_open",
                "guarded_action_gates_missing", "allowed_write_roots", "updated_at"):
        p = RUN / "fixtures" / f"patch_{bad}.json"
        p.write_text(json.dumps({bad: "x"}, indent=2), encoding="utf-8")
        expect_refused(f"R02 protected {bad!r}", l2, "--task", "B01",
                       "--status", "partial", "--patch-file", str(p),
                       text="protected field")
    p = RUN / "fixtures" / "patch_unknown.json"
    p.write_text(json.dumps({"totally_unknown": 1}, indent=2), encoding="utf-8")
    expect_refused("R02 unknown field", l2, "--task", "B01", "--status", "partial",
                   "--patch-file", str(p), text="not allowed")

    # ---------------- R03: action-level gates --------------------------------
    # Precondition: B01 is a completed original-action pass (non-private) so it
    # satisfies an original prerequisite; open original_paths_released with a
    # SYNTHETIC credential on the private copy.
    l3 = new_copy("l03-action.json")
    precondition(l3, lambda d: set_task(
        d, "B01", status="staged_pass", action="runtime_merge",
        guarded_action_gates_open=True, guarded_action_gates_missing=[],
        original_changes_applied=True))
    ok_open, _ = expect_ok("R03 open release gate (synthetic)", l3,
                           "--task", "B02", "--open-gate", "original_paths_released",
                           "--credential", str(f["synthetic_cred"]), "--allow-unblock")
    # B02 primary action needs only original_paths_released (now open) -> accepted
    # WITHOUT the service-cutover gate: the R03 precision correction.
    ok_primary, data3 = expect_ok("R03 B02 config_integration without cutover", l3,
                                  "--task", "B02", "--action", "config_integration",
                                  "--status", "staged_pass",
                                  "--original-changes-applied", "false",
                                  "--patch-file", str(f["evidence_patch"]))
    if ok_primary and data3:
        gates = data3["gates"]
        cutover_closed = gates["existing_service_cutover_authorized"]["open"] is False
        results.append(("R03 cutover still closed after config pass", cutover_closed))
        print(f"[{'PASS' if cutover_closed else 'FAIL'}] R03 cutover still closed: "
              f"open={gates['existing_service_cutover_authorized']['open']}")
    # The service_cutover action DOES require the cutover gate (still closed).
    expect_refused("R03 B02 service_cutover requires cutover gate", l3,
                   "--task", "B02", "--action", "service_cutover",
                   "--status", "staged_pass",
                   "--original-changes-applied", "false",
                   "--patch-file", str(f["evidence_patch"]),
                   text="requires gate(s)")
    expect_refused("R03 unknown action", l3, "--task", "B02", "--action", "nonsense",
                   "--status", "staged_pass", "--original-changes-applied", "false",
                   "--patch-file", str(f["evidence_patch"]),
                   text="unknown action")

    # A private-preparation pass must NOT satisfy an original-action prerequisite.
    l4 = new_copy("l04-privprep-dep.json")
    precondition(l4, lambda d: set_task(
        d, "B01", status="staged_pass", action="private_preparation",
        guarded_action_gates_open=False,
        guarded_action_gates_missing=["original_paths_released"]))
    expect_ok("R03 open release gate (synthetic) on l4", l4,
              "--task", "B02", "--open-gate", "original_paths_released",
              "--credential", str(f["synthetic_cred"]), "--allow-unblock")
    expect_refused("R03 private-prep dep does not satisfy original prereq", l4,
                   "--task", "B02", "--action", "config_integration",
                   "--status", "staged_pass",
                   "--original-changes-applied", "false",
                   "--patch-file", str(f["evidence_patch"]),
                   text="private-preparation only")

    # ---------------- positive controls --------------------------------------
    l5 = new_copy("l05-positive.json")
    ok_partial, data5 = expect_ok("POS legitimate partial progress", l5,
                                  "--task", "B01", "--status", "partial",
                                  "--patch-file", str(f["benign"]))
    if ok_partial and data5:
        rec = record(l5, "B01")
        good = (rec["status"] == "partial" and rec["original_changes_applied"] is False
                and rec.get("notes", "").startswith("legitimate"))
        results.append(("POS partial record truthful", good))
        print(f"[{'PASS' if good else 'FAIL'}] POS partial record truthful: "
              f"status={rec['status']} oca={rec['original_changes_applied']}")

    # Private-preparation pass: B01 complete (private-prep dep is fine for a
    # private action) + release gate open on the private copy.
    l6 = new_copy("l06-privprep.json")
    precondition(l6, lambda d: set_task(
        d, "B01", status="staged_pass", action="private_preparation",
        guarded_action_gates_open=False, guarded_action_gates_missing=[]))
    expect_ok("POS open release gate on l6", l6,
              "--task", "B02", "--open-gate", "original_paths_released",
              "--credential", str(f["synthetic_cred"]), "--allow-unblock")
    ok_pp, data6 = expect_ok("POS private-preparation pass accepted", l6,
                             "--task", "B02", "--status", "staged_pass",
                             "--original-changes-applied", "false",
                             "--private-preparation-only",
                             "--patch-file", str(f["evidence_patch"]))
    if ok_pp and data6:
        rec = record(l6, "B02")
        good = (rec["status"] == "staged_pass"
                and rec.get("action") == "private_preparation"
                and rec["original_changes_applied"] is False
                and rec.get("guarded_action_gates_open") is False)
        results.append(("POS private-prep records guarded action uncovered", good))
        print(f"[{'PASS' if good else 'FAIL'}] POS private-prep guarded action "
              f"uncovered: action={rec.get('action')} "
              f"open={rec.get('guarded_action_gates_open')} "
              f"missing={rec.get('guarded_action_gates_missing')}")

    expect_refused("R02 original-changes-applied true", l5, "--task", "B01",
                   "--status", "staged_pass", "--original-changes-applied", "true",
                   "--patch-file", str(f["evidence_patch"]), text="REFUSED")

    # ---------------- the REAL ledger and gates are untouched ----------------
    real_sha = sha(LEDGER)
    real_ok = real_sha == FROZEN_LEDGER_SHA
    results.append(("REAL ledger byte-identical to frozen hash", real_ok))
    print(f"[{'PASS' if real_ok else 'FAIL'}] REAL ledger unchanged: {real_sha[:12]}")
    gates = load(LEDGER)["gates"]
    closed = all(v["open"] is False for v in gates.values())
    results.append(("REAL gates all closed", closed))
    print(f"[{'PASS' if closed else 'FAIL'}] REAL gates all closed: "
          f"{[g for g, v in gates.items() if v['open']]}")

    ok_all = all(ok for _, ok in results)
    print()
    print(f"{sum(1 for _, ok in results if ok)}/{len(results)} checks passed")
    print("ALL R01-R03 GUARDS ENFORCED" if ok_all else "SOME CHECKS FAILED")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
