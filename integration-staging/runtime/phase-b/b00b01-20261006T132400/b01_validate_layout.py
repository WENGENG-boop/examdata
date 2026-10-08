"""B01 layout/resource validation against the private candidate (F03).

Runs the import probe as a subprocess whose only import root is the private
candidate `src/` tree (no staging PYTHONPATH, no EXAMDATA_INTEGRATION_STAGING_ROOT
override), then checks the resource layout and the guard behaviour. Emits
B01_LAYOUT_VALIDATION.json into the B01 evidence directory.

Findings are recorded honestly: a module that fails to import in the target layout
is reported as a finding, not hidden.
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[4]  # C:/Users/weo/Desktop/api
RUN_DIR = pathlib.Path(__file__).resolve().parent
RUN_ID = "b00b01-20261006T132400"
PRIVATE = ROOT / "integration-staging/runtime/phase-b" / RUN_ID / "private"
PKG_SRC = PRIVATE / "src"
PROBE = RUN_DIR / "b01_import_probe.py"
OUT_DIR = ROOT / "docs/integration/execution/evidence/B01" / RUN_ID
PY = ROOT / "examdata/.venv/Scripts/python.exe"


def run_probe() -> tuple[int, dict | None, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(PKG_SRC)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["B01_PRIVATE_ROOT"] = str(PRIVATE)
    env.pop("EXAMDATA_INTEGRATION_STAGING_ROOT", None)
    p = subprocess.run([str(PY), str(PROBE)], capture_output=True, text=True,
                       env=env, cwd=str(ROOT))
    out = p.stdout.strip()
    try:
        parsed = json.loads(out) if out else None
    except json.JSONDecodeError:
        parsed = None
    transcript = (f"$ PYTHONPATH={PKG_SRC} {PY} {PROBE}\n"
                  f"[exit {p.returncode}]\n--- stdout ---\n{p.stdout}\n"
                  f"--- stderr ---\n{p.stderr}\n")
    return p.returncode, parsed, transcript


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rc, probe, transcript = run_probe()

    # Resource layout: every contracts/schema JSON must load.
    schema_dir = PRIVATE / "contracts/schema"
    schema_files = sorted(schema_dir.glob("*.json")) if schema_dir.is_dir() else []
    schema_ok, schema_bad = 0, []
    for s in schema_files:
        try:
            json.loads(s.read_text(encoding="utf-8"))
            schema_ok += 1
        except Exception as exc:
            schema_bad.append({"file": s.name, "error": f"{type(exc).__name__}: {exc}"})

    findings = []
    if probe is None:
        findings.append({
            "id": "F03-PROBE",
            "severity": "blocker",
            "summary": "import probe did not return JSON",
            "detail": transcript[-800:],
        })
        counts = {}
    else:
        counts = probe["counts"]
        # Finding: product code depending on the staging guard's root heuristic.
        guard_dep = [m for m, err in probe["errors"].items()
                     if "STAGING_ROOT" in err or "integration-staging" in err]
        if guard_dep:
            findings.append({
                "id": "F03-GUARD-DEP",
                "severity": "high",
                "summary": ("product modules import the staging harness guard "
                            "(`..testing.guards`), whose root heuristic requires the "
                            "tree be named 'integration-staging'; at the target "
                            "layout it raises and the import fails"),
                "modules": guard_dep,
                "detail": {m: probe["errors"][m] for m in guard_dep},
                "fix": ("in the target layout the path-root computation must move out "
                        "of the test-only guard into a product-safe module; the guard "
                        "keeps the isolation rule but is not imported by product code"),
            })
        if probe["outside_private"]:
            findings.append({
                "id": "F03-OUTSIDE",
                "severity": "blocker",
                "summary": "some imported modules resolved outside the private tree",
                "modules": probe["outside_private"],
            })
        if counts.get("errors"):
            findings.append({
                "id": "F03-IMPORT-ERRORS",
                "severity": "high",
                "summary": f"{counts['errors']} module(s) failed to import in the target layout",
                "errors": probe["errors"],
            })
    if schema_bad:
        findings.append({"id": "F03-SCHEMA", "severity": "blocker",
                         "summary": "contracts/schema JSON failed to load",
                         "detail": schema_bad})

    report = {
        "schema": "examdata.integration.b01_layout_validation/1",
        "run_id": RUN_ID,
        "private_root": str(PRIVATE),
        "probe_exit_code": rc,
        "probe_counts": counts,
        "examdata_within_private": probe.get("examdata_within_private") if probe else None,
        "schema_files": len(schema_files),
        "schema_loaded_ok": schema_ok,
        "findings": findings,
        "verdict": ("layout_not_yet_valid" if findings else "layout_valid_private_only"),
        "note": ("private candidate only; not merged, not deployed; the original tree "
                 "was neither imported nor written"),
    }
    out = OUT_DIR / "B01_LAYOUT_VALIDATION.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT_DIR / "b01_layout_validation_run.txt").write_text(transcript, encoding="utf-8")

    print(json.dumps({"out": str(out), "probe_exit": rc, "counts": counts,
                      "findings": [f["id"] for f in findings],
                      "verdict": report["verdict"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
