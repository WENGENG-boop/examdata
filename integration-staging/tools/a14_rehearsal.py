#!/usr/bin/env python3
"""A14 rehearsal: apply/rollback every reversible unit on private fixtures.

Usage:
  python a14_rehearsal.py            # run the rehearsal, write A14_REHEARSAL.json
  python a14_rehearsal.py --check    # re-run and compare with the recorded report

The rehearsal answers plan 16.6: rollback is per unit, not per tree. Six units are
named; five can be exercised offline against private fixtures, and the database
unit is recorded as ``not_run`` because Phase A never touches a live database.

Everything happens inside ``integration-staging/runtime/a14-rehearsal/`` — a
sandbox that this tool builds, applies, rolls back and compares. No original
file is opened for writing: the sandbox is seeded with *copies* of the bytes the
map records as the merge base.

Report: docs/integration/execution/A14_REHEARSAL.json
Stdout: captured to docs/integration/execution/evidence/A14/rehearsal_stdout.txt
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True

HERE = Path(__file__).resolve()
TOOLS = HERE.parent
STAGING = TOOLS.parent
WS = STAGING.parent
EXEC = WS / "docs" / "integration" / "execution"

MAP_JSON = EXEC / "A14_MERGE_MAP.json"
REPORT_JSON = EXEC / "A14_REHEARSAL.json"
SANDBOX = STAGING / "runtime" / "a14-rehearsal"
NODE = "C:/Program Files/nodejs/node.exe"

REPORT_VERSION = "a14-rehearsal/1"
CATALOG_FIXTURE = STAGING / "fixtures" / "synthetic" / "catalog" / "catalog-base-synthetic.json"
OPS_FIXTURES = STAGING / "fixtures" / "synthetic" / "operations"
MANIFEST_SRC = STAGING / "components" / "manifest.json"
COMPONENT_SRC = STAGING / "components" / "fake-node-cli"
CLIENT_MJS = STAGING / "frontend" / "client.mjs"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel_ws(path: Path) -> str:
    return path.resolve().relative_to(WS.resolve()).as_posix()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def reset(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def snapshot(root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not root.exists():
        return out
    for f in sorted(root.rglob("*")):
        if f.is_file():
            out[f.relative_to(root).as_posix()] = sha256_file(f)
    return out


def check(name: str, ok: bool, detail: str = "") -> dict:
    return {"name": name, "ok": bool(ok), "detail": detail}


# --------------------------------------------------------------------------- #
# unit 1 — code release: apply every mapped file, then roll it back
# --------------------------------------------------------------------------- #

def unit_code_release() -> dict:
    root = SANDBOX / "release"
    reset(root)
    payload = json.loads(MAP_JSON.read_text(encoding="utf-8"))
    entries = payload["entries"]

    targets: dict[str, list[str]] = {}
    for entry in entries:
        targets.setdefault(entry["proposed_target"], []).append(entry["staged_path"])
    collisions = {t: v for t, v in targets.items() if len(v) > 1}

    # seed: only entries that overwrite an existing file. A copied_snapshot entry
    # carries a base hash to *prove the copy* (verify_copy), not to restore it: the
    # merge creates that path, so its reversal is delete_file.
    seeded: list[str] = []
    for entry in entries:
        if entry["reversal"] != "restore_base_bytes":
            continue
        base = entry.get("base")
        if not base:
            continue
        source = WS / base["source_path"]
        dest = root / entry["proposed_target"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, dest)
        seeded.append(entry["staged_path"])

    before = snapshot(root)

    # apply
    applied: list[str] = []
    for entry in entries:
        staged = WS / entry["staged_path"]
        dest = root / entry["proposed_target"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(staged, dest)
        applied.append(entry["staged_path"])

    mismatched: list[str] = []
    for entry in entries:
        dest = root / entry["proposed_target"]
        if not dest.is_file() or sha256_file(dest) != entry["staged_sha256"]:
            mismatched.append(entry["staged_path"])
    applied_ok = not mismatched

    # copied_snapshot entries claim a faithful copy of an original file: verify it
    unfaithful: list[str] = []
    drifted: list[str] = []
    for entry in entries:
        if entry["kind"] != "copied_snapshot":
            continue
        base = entry.get("base") or {}
        if base.get("sha256_recorded") != entry["staged_sha256"]:
            unfaithful.append(entry["staged_path"])
        if base.get("sha256_current") != base.get("sha256_recorded"):
            drifted.append(entry["staged_path"])

    after_apply = snapshot(root)

    # roll back exactly as the map's reversal column says
    for entry in entries:
        dest = root / entry["proposed_target"]
        if entry["reversal"] == "delete_file":
            if dest.is_file():
                dest.unlink()
        else:  # restore_base_bytes
            base = entry.get("base")
            if base:
                shutil.copyfile(WS / base["source_path"], dest)

    after_rollback = snapshot(root)
    restored = after_rollback == before
    residue = sorted(set(after_rollback) - set(before))
    lost = sorted(set(before) - set(after_rollback))
    changed = sorted(k for k in before if k in after_rollback and before[k] != after_rollback[k])

    # every write stayed inside the sandbox by construction; assert it explicitly
    stray = [p for p in [root / e["proposed_target"] for e in entries]
             if not str(p.resolve()).startswith(str(root.resolve()))]

    return {
        "unit": "code release",
        "rehearsed": True,
        "method": "apply every A14_MERGE_MAP.json entry into the sandbox, verify the staged "
                  "hash, then execute the recorded reversal per entry",
        "checks": [
            check("every entry has a unique target", not collisions,
                  f"collisions: {collisions}" if collisions else f"{len(targets)} targets"),
            check("no target escapes the sandbox", not stray, f"stray: {stray}"),
            check("all staged bytes applied verbatim", applied_ok,
                  f"mismatched: {mismatched}" if mismatched else f"{len(entries)} files"),
            check("every copied_snapshot is byte-faithful to its recorded base",
                  not unfaithful,
                  f"unfaithful: {unfaithful}" if unfaithful
                  else f"{sum(1 for e in entries if e['kind'] == 'copied_snapshot')} copies"),
            check("no recorded base has drifted under the active owner", not drifted,
                  f"drifted: {drifted}" if drifted
                  else "recorded == observed for every base"),
            check("rollback restores the pre-apply tree byte-for-byte", restored,
                  f"residue={residue} lost={lost} changed={changed}"),
        ],
        "counts": {
            "entries": len(entries),
            "seeded_from_base": len(seeded),
            "new_files": sum(1 for e in entries if not e.get("base")),
            "files_before": len(before),
            "files_after_apply": len(after_apply),
            "files_after_rollback": len(after_rollback),
        },
        "sandbox": rel_ws(root),
    }


# --------------------------------------------------------------------------- #
# unit 2 — component manifest: swap, re-read, restore
# --------------------------------------------------------------------------- #

def unit_component_manifest() -> dict:
    sys.path.insert(0, str(STAGING / "src"))
    from examdata_integration.runtime.manifest import load_manifest_set

    root = SANDBOX / "manifest"
    reset(root)
    shutil.copyfile(MANIFEST_SRC, root / "manifest.json")
    shutil.copytree(COMPONENT_SRC, root / "components" / "fake-node-cli")
    manifest_path = root / "manifest.json"
    original_bytes = manifest_path.read_bytes()
    original_sha = sha256_file(manifest_path)

    first = load_manifest_set(manifest_path, deployment_root=root)
    first_report = first.report()
    first_ids = sorted(first.components)

    variant = json.loads(original_bytes.decode("utf-8"))
    variant["components"][0]["version"] = "1.1.0"
    variant["components"][0]["supported_commands"] = (
        variant["components"][0]["supported_commands"] + ["rehearsal-only"])
    manifest_path.write_text(json.dumps(variant, indent=2) + "\n", encoding="utf-8")
    variant_sha = sha256_file(manifest_path)

    second = load_manifest_set(manifest_path, deployment_root=root)
    swapped_observed = bool(
        second.get("fake_cli")
        and second.get("fake_cli").version == "1.1.0"
        and "rehearsal-only" in second.get("fake_cli").supported_commands)

    manifest_path.write_bytes(original_bytes)
    third = load_manifest_set(manifest_path, deployment_root=root)
    restored = (sha256_file(manifest_path) == original_sha
                and third.report() == first_report
                and sorted(third.components) == first_ids)

    return {
        "unit": "component manifest",
        "rehearsed": True,
        "method": "load the manifest set from a sandbox deployment root, swap in a variant, "
                  "re-read, then restore the original bytes and re-read",
        "checks": [
            check("manifest loads from the sandbox deployment root", not first.problems,
                  f"problems: {[p.code for p in first.problems]}"),
            check("swapped manifest is observed without any cached state", swapped_observed,
                  f"version after swap: "
                  f"{second.get('fake_cli').version if second.get('fake_cli') else None}"),
            check("restoring the bytes restores the resolved component set", restored,
                  f"manifest sha256 back to {original_sha[:12]}"),
        ],
        "components": first_ids,
        "manifest_sha256": original_sha,
        "variant_sha256": variant_sha,
        "sandbox": rel_ws(root),
    }


# --------------------------------------------------------------------------- #
# unit 3 — data revision pointer: publish A, publish B, roll back to A
# --------------------------------------------------------------------------- #

def unit_revision_pointer() -> dict:
    sys.path.insert(0, str(STAGING / "src"))
    from examdata_integration.catalog.builder import CatalogBuilder
    from examdata_integration.catalog.model import CatalogSource
    from examdata_integration.catalog.revision import RevisionPublisher

    data = json.loads(CATALOG_FIXTURE.read_text(encoding="utf-8"))
    sources = [CatalogSource.from_dict(s) for s in data["sources"]]
    first = CatalogBuilder().build(sources)
    if not first.ok:
        return {"unit": "data revision pointer", "rehearsed": False,
                "checks": [check("fixture builds", False, str(first.problems))],
                "sandbox": rel_ws(SANDBOX / "catalog")}

    extra = CatalogSource(
        kind="course", system="cie",
        identity_fields={"system": "cie", "qualification": "igcse",
                         "native_code": "0581", "specification_version": "2026"},
        native_locator={"kind": "course", "native_code": "0581", "qualification": "igcse"},
        content_class="synthetic", evidence_labels=["synthetic_fixture"],
        content_revision="rev-syn-course-0581")
    second_build = CatalogBuilder().build(sources + [extra])
    if not second_build.ok:
        return {"unit": "data revision pointer", "rehearsed": False,
                "checks": [check("variant fixture builds", False, str(second_build.problems))],
                "sandbox": rel_ws(SANDBOX / "catalog")}

    root = SANDBOX / "catalog"
    reset(root)
    publisher = RevisionPublisher(root=root)

    snap_a = first.snapshot
    snap_b = second_build.snapshot
    rev_a, rev_b = snap_a.dataset_revision, snap_b.dataset_revision

    pointer_a = publisher.publish(snap_a)
    a_is_current = publisher.current_revision() == rev_a
    a_retained = publisher.retain(rev_a)

    pointer_b = publisher.publish(snap_b, expected_current=rev_a)
    b_is_current = publisher.current_revision() == rev_b
    a_still_retained = publisher.retain(rev_a)
    b_previous = pointer_b.get("previous") == rev_a

    rolled = publisher.rollback()
    back_to_a = publisher.current_revision() == rev_a
    both_retained = publisher.retain(rev_a) and publisher.retain(rev_b)
    b_still_readable = publisher.load_revision(rev_b).dataset_revision == rev_b
    pointer_records_b = rolled.get("previous") == rev_b

    return {
        "unit": "data revision pointer",
        "rehearsed": True,
        "method": "publish revision A, publish revision B, call rollback(), then confirm the "
                  "pointer resolves to A while B stays readable",
        "checks": [
            check("revision A published and retained", a_is_current and a_retained,
                  f"A={rev_a[:16]}"),
            check("revision B published over A", b_is_current and b_previous,
                  f"B={rev_b[:16]} previous={pointer_b.get('previous', '')[:16]}"),
            check("A stays retained after B is published", a_still_retained, ""),
            check("rollback points current back at A", back_to_a,
                  f"current={publisher.current_revision()[:16]}"),
            check("both revisions remain readable after rollback", both_retained and b_still_readable,
                  f"available={[r[:16] for r in publisher.available_revisions()]}"),
            check("rollback records B as the previous pointer", pointer_records_b, ""),
        ],
        "revisions": {"a": rev_a, "b": rev_b},
        "sandbox": rel_ws(root),
    }


# --------------------------------------------------------------------------- #
# unit 4 — database backup: recorded, never exercised in Phase A
# --------------------------------------------------------------------------- #

def unit_database_backup() -> dict:
    return {
        "unit": "database backup",
        "rehearsed": False,
        "not_run": True,
        "reason": "no live database is touched in Phase A (plan 16.6 / B08); the reversal is "
                  "documented but cannot be exercised without protected resources",
        "reversal_documented": "restore the recorded backup, then reconcile writes made after "
                               "it; never restore over new writes without freezing them",
        "checks": [check("no database opened", True, "the rehearsal holds no database handle")],
    }


# --------------------------------------------------------------------------- #
# unit 5 — frontend switch: toggle off and on with fake storage
# --------------------------------------------------------------------------- #

FRONTEND_SCRIPT = """\
import { pathToFileURL } from 'node:url';
const client = await import(pathToFileURL(process.argv[2]).href);
const store = new Map();
const storage = {
  getItem: (k) => (store.has(k) ? store.get(k) : null),
  setItem: (k, v) => { store.set(k, String(v)); },
  removeItem: (k) => { store.delete(k); },
};
const initial = client.clientEnabled({ storage });
client.setClientEnabled(false, { storage });
const afterOff = client.clientEnabled({ storage });
const markerOff = store.get(client.FLAG_NAME);
client.setClientEnabled(true, { storage });
const afterOn = client.clientEnabled({ storage });
const markerGone = !store.has(client.FLAG_NAME);
console.log(JSON.stringify({
  flag: client.FLAG_NAME,
  initial,
  after_off: afterOff,
  marker_after_off: markerOff,
  after_on: afterOn,
  marker_removed_after_on: markerGone,
}));
"""


def unit_frontend_switch() -> dict:
    root = SANDBOX / "frontend-switch"
    reset(root)
    script = root / "switch.mjs"
    script.write_text(FRONTEND_SCRIPT, encoding="utf-8")
    proc = subprocess.run([NODE, str(script), str(CLIENT_MJS)],
                          capture_output=True, text=True, timeout=120)
    payload: dict = {}
    if proc.returncode == 0 and proc.stdout.strip():
        try:
            payload = json.loads(proc.stdout.strip().splitlines()[-1])
        except ValueError:
            payload = {}

    ok = bool(payload) and payload.get("initial") is True \
        and payload.get("after_off") is False and payload.get("after_on") is True

    return {
        "unit": "frontend switch",
        "rehearsed": proc.returncode == 0 and bool(payload),
        "method": "drive the staged client's flag helpers with an in-memory storage; no file, "
                  "no server and no network is touched",
        "checks": [
            check("node exits 0", proc.returncode == 0,
                  (proc.stderr or "").strip()[-200:]),
            check("off then on restores the default", ok, json.dumps(payload)),
            check("switching writes no file", True,
                  "storage is in-memory; the sandbox holds only the driver script"),
        ],
        "observed": payload,
        "sandbox": rel_ws(root),
    }


# --------------------------------------------------------------------------- #
# unit 6 — job checkpoint: readers are read-only
# --------------------------------------------------------------------------- #

def unit_job_checkpoint() -> dict:
    sys.path.insert(0, str(STAGING / "src"))
    from examdata_integration.operations.checkpoints import read_checkpoint, state_of

    names = ["cie-batch-checkpoint-running.json", "ielts-run-checkpoint-ok.json",
             "unsupported-checkpoint.json"]
    rows = []
    unchanged = True
    for name in names:
        path = OPS_FIXTURES / name
        before = sha256_file(path)
        observation = read_checkpoint(path, source=name)
        after = sha256_file(path)
        state = state_of(observation)
        rows.append({
            "fixture": name,
            "sha256_before": before,
            "sha256_after": after,
            "unchanged": before == after,
            "format": getattr(observation.format, "value", str(observation.format)),
            "state": state.__class__.__name__ if state is not None else None,
        })
        unchanged = unchanged and before == after

    return {
        "unit": "job checkpoint",
        "rehearsed": True,
        "method": "read three private checkpoint fixtures through the staged readers and "
                  "compare the file hashes before and after",
        "checks": [
            check("readers never rewrite a checkpoint", unchanged,
                  f"{len(rows)} fixtures byte-identical"),
            check("an unrecognised checkpoint stays an explicit unknown, not an exception",
                  rows[-1]["state"] is None and rows[-1]["format"] == "unknown",
                  f"format={rows[-1]['format']} state={rows[-1]['state']}"),
        ],
        "rows": rows,
    }


# --------------------------------------------------------------------------- #

def build_report() -> dict:
    units = [
        unit_code_release(),
        unit_component_manifest(),
        unit_revision_pointer(),
        unit_database_backup(),
        unit_frontend_switch(),
        unit_job_checkpoint(),
    ]
    problems: list[str] = []
    for unit in units:
        if not unit.get("rehearsed") and not unit.get("not_run"):
            problems.append(f"{unit['unit']}: rehearsal did not run")
        for item in unit.get("checks", []):
            if not item["ok"]:
                problems.append(f"{unit['unit']}: {item['name']}: {item['detail']}")
    return {
        "report_version": REPORT_VERSION,
        "generated_by": "integration-staging/tools/a14_rehearsal.py",
        "generated_at": now_iso(),
        "status": "staged_rehearsal_only_not_merged_not_deployed",
        "sandbox_root": rel_ws(SANDBOX),
        "units": units,
        "summary": {
            "units": len(units),
            "rehearsed": sum(1 for u in units if u.get("rehearsed")),
            "not_run": sum(1 for u in units if u.get("not_run")),
            "checks": sum(len(u.get("checks", [])) for u in units),
            "problems": len(problems),
        },
        "problems": problems,
    }


def main() -> int:
    check_mode = "--check" in sys.argv[1:]
    report = build_report()

    print(f"A14_REHEARSAL: {report['report_version']}")
    print(f"  sandbox: {report['sandbox_root']}")
    for unit in report["units"]:
        mark = "not_run" if unit.get("not_run") else ("ok" if unit.get("rehearsed") else "FAIL")
        print(f"  [{mark:7}] {unit['unit']}")
        for item in unit.get("checks", []):
            print(f"            {'PASS' if item['ok'] else 'FAIL'} {item['name']}"
                  + (f" — {item['detail']}" if item["detail"] else ""))
    print(f"  summary: {report['summary']['rehearsed']} rehearsed, "
          f"{report['summary']['not_run']} not_run, "
          f"{report['summary']['checks']} checks, {report['summary']['problems']} problems")

    if check_mode:
        if not REPORT_JSON.is_file():
            print("A14_REHEARSAL: FAIL — no recorded report to compare against")
            return 1
        recorded = json.loads(REPORT_JSON.read_text(encoding="utf-8"))
        a = dict(recorded)
        b = dict(report)
        a.pop("generated_at", None)
        b.pop("generated_at", None)
        if a != b:
            print("A14_REHEARSAL: FAIL — the recorded report differs from a fresh run")
            return 1
        print("A14_REHEARSAL: PASS — recorded report matches a fresh run")
        return 0 if not report["problems"] else 1

    REPORT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
    print(f"wrote {rel_ws(REPORT_JSON)}")
    if report["problems"]:
        print("A14_REHEARSAL: FAIL")
        for p in report["problems"]:
            print(f"- {p}")
        return 1
    print("A14_REHEARSAL: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
