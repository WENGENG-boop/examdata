"""Self-test for b_ledger_update.py against a PRIVATE COPY of the ledger.

Copies docs/integration/execution/execution-ledger.json into a run directory,
points the tool at the copy via EXAMDATA_B_LEDGER, and exercises every
rejection condition from the B00/B01 prompt §2.2:

  R1  gate opening without the human four-part credential
  R2  credential with missing four-part elements
  R3  credential present but --allow-unblock missing (blocked_by guard)
  R4  forged staged_pass: no concrete commands / exit codes / evidence
  R5  input digest changed between observation and update (concurrency);
      relative input paths resolve against the workspace root, so the
      rejection must be a real digest mismatch, never a path-resolution miss
  R5b an input file that genuinely no longer exists
  R6  trying to open two gates with one credential
  R7  modifying sealed A00-A15 records
  R8  recording a private candidate as merged_pass
  R9  widening allowed_write_roots
  R10 credential scope not covering a declared target path
  R11 positive control: a credentialed gate open lifts exactly one gate
      and leaves every other gate closed
  R12 positive control: matching --expect-inputs digests are accepted and the
      update is persisted
  R13 positive control: every status the tool writes (including `partial`)
      records original_changes_applied=false
  R14 machine-checked dependency guard (F04): a staged_pass is refused while a
      listed dependency is not complete (B01 depends on B00=partial)
  R15 per-packet gate requirement (F04): a staged_pass is refused while a gate
      the packet's guarded action needs is closed and --private-preparation-only
      is absent (B00 requires original_paths_released)
  R15b positive control (F04): with the packet's dependency complete and the
      required gate open, a --private-preparation-only staged_pass is accepted
      and records the still-missing guarded gate (B02)

Exits 0 when every rejection fires (and all positive controls hold) and the
ledger copy is byte-unchanged by all refused operations. The REAL ledger is
never written by this test.
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
API = RUN.parents[3]
LEDGER = API / "docs/integration/execution/execution-ledger.json"
TOOL = API / "integration-staging/tools/b_ledger_update.py"
PRIVATE = RUN / "ledger-copy" / "execution-ledger.json"
PY = sys.executable


def run(*argv: str) -> tuple[int, str]:
    env = dict(os.environ)
    env["EXAMDATA_B_LEDGER"] = str(PRIVATE)
    p = subprocess.run(
        [PY, str(TOOL), "--task", *argv],
        capture_output=True, text=True, cwd=str(API), env=env,
    )
    return p.returncode, (p.stdout + p.stderr).strip()


def main() -> int:
    PRIVATE.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(LEDGER, PRIVATE)
    base_digest = hashlib.sha256(PRIVATE.read_bytes()).hexdigest()
    results: list[tuple[str, bool]] = []

    def check(label: str, *argv: str, expect_exit: int = 2,
              expect_text: str = "REFUSED", forbid_text: str | None = None) -> bool:
        code, out = run(*argv)
        ok = code == expect_exit and expect_text in out
        if forbid_text and forbid_text in out:
            ok = False
            print(f"    rejected for the wrong reason: {forbid_text!r} present")
        if hashlib.sha256(PRIVATE.read_bytes()).hexdigest() != base_digest:
            ok = False
            print(f"    LEDGER MUTATED by op {label}")
        first = out.splitlines()[0] if out else ""
        print(f"[{'PASS' if ok else 'FAIL'}] {label}: exit={code} {first[:110]}")
        if not ok:
            print(f"    full output: {out[:300]}")
        return ok

    # helper inputs ------------------------------------------------------------
    (RUN / "cred_partial.json").write_text(json.dumps({
        "instruction": "partial", "timestamp": "2026-10-06T13:00:00+08:00",
    }, indent=2), encoding="utf-8")
    (RUN / "cred_full.json").write_text(json.dumps({
        "instruction": "I release the original paths for B00/B01.",
        "timestamp": "2026-10-06T13:00:00+08:00",
        "scope": "examdata/**",
        "constraints": "no cutover, no live data, no network",
    }, indent=2), encoding="utf-8")
    (RUN / "patch_no_evidence.json").write_text(json.dumps({
        "test_results": [{"check": "everything", "result": "pass", "evidence": None,
                          "exit_code": None, "label": "synthetic_fixture"}],
        "commands": [],
        "exit_codes": [],
    }, indent=2), encoding="utf-8")
    (RUN / "patch_with_evidence.json").write_text(json.dumps({
        "commands": [{"seq": 1, "purpose": "check", "tool": "Bash",
                      "command": "python check.py", "cwd": "C:/Users/weo/Desktop/api",
                      "exit_code": 0, "evidence": "evidence/B00/transcript.txt"}],
        "exit_codes": [0],
        "test_results": [{"check": "reconciled", "result": "pass", "exit_code": 0,
                          "evidence": "evidence/B00/transcript.txt",
                          "label": "static_inspection"}],
    }, indent=2), encoding="utf-8")

    (RUN / "inputs_bad.json").write_text(json.dumps(
        {"docs/integration/execution/A14_MERGE_MAP.json": "0" * 64},
        indent=2), encoding="utf-8")
    # A path that genuinely does not exist under the workspace root.
    (RUN / "inputs_missing.json").write_text(json.dumps(
        {"docs/integration/execution/NO_SUCH_FILE.json": "0" * 64},
        indent=2), encoding="utf-8")
    # Positive control input: the real recorded digest of a real file.
    (RUN / "inputs_good.json").write_text(json.dumps(
        {"docs/integration/execution/A14_MERGE_MAP.json": hashlib.sha256(
            (API / "docs/integration/execution/A14_MERGE_MAP.json").read_bytes()
        ).hexdigest()},
        indent=2), encoding="utf-8")
    (RUN / "patch_widen.json").write_text(json.dumps({
        "allowed_write_roots": [
            "C:/Users/weo/Desktop/api/integration-staging",
            "C:/Users/weo/Desktop/api/docs/integration/execution",
            "C:/Users/weo/Desktop/api/examdata",
        ],
    }, indent=2), encoding="utf-8")
    (RUN / "patch_out_of_scope.json").write_text(json.dumps({
        "changed_files": ["C:/Users/weo/Desktop/api/elsewhere/target.py"],
    }, indent=2), encoding="utf-8")

    # R1: gate without credential
    results.append(("R1 no-credential", check(
        "R1 no-credential", "B00", "--open-gate", "original_paths_released")))

    # R2: credential missing four-part elements
    results.append(("R2 partial-credential", check(
        "R2 partial-credential", "B00",
        "--open-gate", "original_paths_released",
        "--credential", str(RUN / "cred_partial.json"))))

    # R3: credential present but --allow-unblock missing
    results.append(("R3 unblock-guard", check(
        "R3 unblock-guard", "B00",
        "--open-gate", "original_paths_released",
        "--credential", str(RUN / "cred_full.json"))))

    # R4: forged staged_pass without evidence commands
    results.append(("R4 forged-pass", check(
        "R4 forged-pass", "B00", "--status", "staged_pass",
        "--original-changes-applied", "false",
        "--patch-file", str(RUN / "patch_no_evidence.json"))))

    # R5: changed input digest -- must reject for the digest reason, not
    # because the relative path failed to resolve (the pre-fix behaviour).
    results.append(("R5 digest-changed", check(
        "R5 digest-changed", "B00", "--status", "staged_pass",
        "--original-changes-applied", "false",
        "--patch-file", str(RUN / "patch_with_evidence.json"),
        "--expect-inputs", str(RUN / "inputs_bad.json"),
        forbid_text="missing")))

    # R5b: an input that genuinely no longer exists under the workspace root
    results.append(("R5b input-missing", check(
        "R5b input-missing", "B00", "--status", "staged_pass",
        "--original-changes-applied", "false",
        "--patch-file", str(RUN / "patch_with_evidence.json"),
        "--expect-inputs", str(RUN / "inputs_missing.json"),
        expect_text="missing at")))

    # R6: opening two gates with one credential
    results.append(("R6 two-gates", check(
        "R6 two-gates", "B00",
        "--open-gate", "original_paths_released",
        "--open-gate", "real_data_write_authorized",
        "--credential", str(RUN / "cred_full.json"))))

    # R7: sealed A record
    results.append(("R7 sealed-A", check(
        "R7 sealed-A", "A15", "--status", "staged_pass")))

    # R8: merged_pass
    results.append(("R8 merged_pass", check(
        "R8 merged_pass", "B00", "--status", "merged_pass",
        "--original-changes-applied", "false")))

    # R9: widening allowed_write_roots
    results.append(("R9 widen-roots", check(
        "R9 widen-roots", "B00", "--status", "staged_pass",
        "--original-changes-applied", "false",
        "--patch-file", str(RUN / "patch_widen.json"))))

    # R10: credential scope not covering a declared target path
    results.append(("R10 scope-mismatch", check(
        "R10 scope-mismatch", "B00",
        "--open-gate", "original_paths_released",
        "--credential", str(RUN / "cred_full.json"),
        "--allow-unblock",
        "--patch-file", str(RUN / "patch_out_of_scope.json"))))

    # R4b: staged_pass without original-changes-applied declaration
    results.append(("R4b missing-declaration", check(
        "R4b missing-declaration", "B00", "--status", "staged_pass")))

    # R14 (F04 rejection): B01 depends on B00, which is `partial` -- not a
    # complete status -- so a staged_pass on B01 must be refused on the
    # dependency check, before the blocked_by gate guard can fire. Runs while
    # PRIVATE is still byte-identical to the sealed ledger (R11 mutates it).
    results.append(("R14 dep-incomplete", check(
        "R14 dep-incomplete", "B01", "--status", "staged_pass",
        "--original-changes-applied", "false",
        "--patch-file", str(RUN / "patch_with_evidence.json"),
        expect_text="dependencies are not complete")))

    # R15 (F04 rejection): B00's dependency A15 is complete, but the packet's
    # guarded action needs original_paths_released, which is still closed here.
    # Without --private-preparation-only the pass must be refused on the gate
    # check.
    results.append(("R15 gate-closed", check(
        "R15 gate-closed", "B00", "--status", "staged_pass",
        "--original-changes-applied", "false",
        "--patch-file", str(RUN / "patch_with_evidence.json"),
        expect_text="requires gate(s)")))

    # R11 (positive control): properly credentialed gate open lifts exactly one
    # gate. The credential scope must cover every path B00 declares, so derive
    # it from the record instead of hard-coding (the record grows as B00 gains
    # changed_files; a stale scope is correctly refused by the tool).
    _base = json.loads(PRIVATE.read_text(encoding="utf-8"))
    _declared = {t["task_id"]: t for t in _base["tasks"]}["B00"].get("changed_files") or []
    (RUN / "cred_positive.json").write_text(json.dumps({
        "instruction": "I release the original paths for B00/B01 (positive control).",
        "timestamp": "2026-10-06T13:00:00+08:00",
        "scope": ",".join(sorted(set(_declared))) or "**",
        "constraints": "positive control only; no cutover, no live data, no network",
    }, indent=2), encoding="utf-8")
    code, out = run("B00", "--open-gate", "original_paths_released",
                    "--credential", str(RUN / "cred_positive.json"), "--allow-unblock")
    r11 = code == 0
    if r11:
        data = json.loads(PRIVATE.read_text(encoding="utf-8"))
        open_gates = [g for g, v in data["gates"].items() if v["open"]]
        r11 = open_gates == ["original_paths_released"]
        print(f"[{'PASS' if r11 else 'FAIL'}] R11 one-gate-only: open={open_gates}")
    else:
        print(f"[FAIL] R11 one-gate-only: exit={code} {out[:200]}")
    results.append(("R11 one-gate-only", r11))

    # R12 (positive control): an update whose --expect-inputs digests MATCH is
    # accepted and persisted, so the digest guard is not a blanket refusal.
    PRIVATE2 = RUN / "ledger-copy" / "execution-ledger-r12.json"
    shutil.copy2(LEDGER, PRIVATE2)
    env2 = dict(os.environ)
    env2["EXAMDATA_B_LEDGER"] = str(PRIVATE2)
    p = subprocess.run(
        [PY, str(TOOL), "--task", "B00", "--next-action",
         "R12 positive control: matching digests accepted",
         "--expect-inputs", str(RUN / "inputs_good.json")],
        capture_output=True, text=True, cwd=str(API), env=env2,
    )
    r12 = p.returncode == 0
    if r12:
        data = json.loads(PRIVATE2.read_text(encoding="utf-8"))
        rec = {t["task_id"]: t for t in data["tasks"]}["B00"]
        r12 = str(rec.get("next_action", "")).startswith("R12 positive control")
    print(f"[{'PASS' if r12 else 'FAIL'}] R12 digest-match accepted: exit={p.returncode}")
    if not r12:
        print(f"    full output: {(p.stdout + p.stderr)[:300]}")
    results.append(("R12 digest-match accepted", r12))

    # R13 (positive control): every status this tool writes declares
    # original_changes_applied=false, including a non-staged status such as
    # `partial`, so no private-preparation record can be read as a merge.
    PRIVATE3 = RUN / "ledger-copy" / "execution-ledger-r13.json"
    shutil.copy2(LEDGER, PRIVATE3)
    env3 = dict(os.environ)
    env3["EXAMDATA_B_LEDGER"] = str(PRIVATE3)
    p = subprocess.run(
        [PY, str(TOOL), "--task", "B00", "--status", "partial"],
        capture_output=True, text=True, cwd=str(API), env=env3,
    )
    r13 = p.returncode == 0
    if r13:
        data = json.loads(PRIVATE3.read_text(encoding="utf-8"))
        rec = {t["task_id"]: t for t in data["tasks"]}["B00"]
        r13 = rec.get("original_changes_applied") is False and rec["status"] == "partial"
    print(f"[{'PASS' if r13 else 'FAIL'}] R13 partial declares no-original-changes: "
          f"exit={p.returncode}")
    if not r13:
        print(f"    full output: {(p.stdout + p.stderr)[:300]}")
    results.append(("R13 partial declares no-original-changes", r13))

    # R15b (F04 positive control): precondition a private copy with the packet's
    # dependency complete (B01=staged_pass) and its first required gate open
    # (original_paths_released). B02 then has one required gate still closed
    # (existing_service_cutover_authorized), so a --private-preparation-only
    # staged_pass is accepted and records the guarded gate as not open.
    PRIVATE4 = RUN / "ledger-copy" / "execution-ledger-r15b.json"
    shutil.copy2(LEDGER, PRIVATE4)
    env4 = dict(os.environ)
    env4["EXAMDATA_B_LEDGER"] = str(PRIVATE4)
    p_open = subprocess.run(
        [PY, str(TOOL), "--task", "B00", "--open-gate", "original_paths_released",
         "--credential", str(RUN / "cred_positive.json"), "--allow-unblock"],
        capture_output=True, text=True, cwd=str(API), env=env4,
    )
    data4 = json.loads(PRIVATE4.read_text(encoding="utf-8"))
    for t in data4["tasks"]:
        if t["task_id"] == "B01":
            t["status"] = "staged_pass"
    PRIVATE4.write_text(json.dumps(data4, indent=2) + "\n", encoding="utf-8")
    p_act = subprocess.run(
        [PY, str(TOOL), "--task", "B02", "--status", "staged_pass",
         "--original-changes-applied", "false", "--private-preparation-only",
         "--patch-file", str(RUN / "patch_with_evidence.json")],
        capture_output=True, text=True, cwd=str(API), env=env4,
    )
    r15b = p_open.returncode == 0 and p_act.returncode == 0
    if r15b:
        data4 = json.loads(PRIVATE4.read_text(encoding="utf-8"))
        rec = {t["task_id"]: t for t in data4["tasks"]}["B02"]
        r15b = (
            rec.get("status") == "staged_pass"
            and rec.get("original_changes_applied") is False
            and rec.get("guarded_action_gates_open") is False
            and rec.get("guarded_action_gates_missing")
            == ["existing_service_cutover_authorized"]
        )
        if not r15b:
            print(f"    B02 record: status={rec.get('status')} "
                  f"oca={rec.get('original_changes_applied')} "
                  f"open={rec.get('guarded_action_gates_open')} "
                  f"missing={rec.get('guarded_action_gates_missing')}")
    else:
        print(f"    open exit={p_open.returncode} {(p_open.stdout + p_open.stderr)[:200]}")
        print(f"    act exit={p_act.returncode} {(p_act.stdout + p_act.stderr)[:200]}")
    print(f"[{'PASS' if r15b else 'FAIL'}] R15b private-prep pass accepted: "
          f"open={p_open.returncode} act={p_act.returncode}")
    results.append(("R15b private-prep pass accepted", r15b))

    ok_all = all(ok for _, ok in results)
    print()
    print("ALL REJECTIONS ENFORCED" if ok_all else "SOME REJECTIONS FAILED")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
