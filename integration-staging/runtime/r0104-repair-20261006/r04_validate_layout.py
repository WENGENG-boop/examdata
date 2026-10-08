"""R04 layout validation: run the import + resource probes against both candidates.

Runs the probes as subprocesses whose environment is deliberately stripped of the
two crutches R04 is about:

* ``PYTHONPATH`` is removed -- the candidate ``src/`` tree is put on the import
  path by the probe itself;
* ``EXAMDATA_INTEGRATION_STAGING_ROOT`` is removed -- the candidate root is
  supplied only through the explicit product variable
  ``EXAMDATA_INTEGRATION_ROOT``.

Both candidate destinations are exercised: an arbitrary directory name and a
directory name containing spaces and non-ASCII characters.

Writes evidence into a *new* directory under
``docs/integration/execution/evidence/R0104/r0104-repair-20261006/``. Frozen
historical evidence (``evidence/B01/**``, ``runtime/phase-b/**``) is never
touched.
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[3]        # C:/Users/weo/Desktop/api
RUN_DIR = pathlib.Path(__file__).resolve().parent
RUN_ID = "r0104-repair-20261006"
CANDIDATES = ROOT / "integration-staging" / "runtime" / RUN_ID / "candidates"
EVIDENCE = ROOT / "docs" / "integration" / "execution" / "evidence" / "R0104" / RUN_ID
TMP_DIR = RUN_DIR / "evidence" / "tmp"
PY = ROOT / "examdata" / ".venv" / "Scripts" / "python.exe"
ORIGINAL_APP_CODE = ROOT / "examdata" / "src"

DESTINATIONS = (
    "r04-target-layout-v2",
    "R04 \u76ee\u6807 layout \u00fcn\u00efcode",
)

PROBES = ("r04_import_probe.py", "r04_resource_probe.py")


def slug(destination: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in destination)


def probe_env(candidate: pathlib.Path) -> dict:
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env.pop("EXAMDATA_INTEGRATION_STAGING_ROOT", None)
    env["R04_CANDIDATE_ROOT"] = str(candidate)
    env["R04_WORKSPACE_ROOT"] = str(ROOT)
    env["R04_TMP_DIR"] = str(TMP_DIR)
    env["EXAMDATA_INTEGRATION_ROOT"] = str(candidate)
    env["EXAMDATA_INTEGRATION_ORIGINAL_APP_CODE"] = str(ORIGINAL_APP_CODE)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def run_probe(script: str, candidate: pathlib.Path) -> dict:
    path = RUN_DIR / script
    env = probe_env(candidate)
    proc = subprocess.run([str(PY), str(path)], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=env, cwd=str(ROOT),
                          timeout=900)
    out = (proc.stdout or "").strip()
    try:
        parsed = json.loads(out) if out else None
    except json.JSONDecodeError:
        parsed = None
    return {
        "script": script,
        "candidate": str(candidate),
        "exit_code": proc.returncode,
        "report": parsed,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "env_pythonpath": env.get("PYTHONPATH"),
        "env_staging_override": env.get("EXAMDATA_INTEGRATION_STAGING_ROOT"),
        "env_root": env.get("EXAMDATA_INTEGRATION_ROOT"),
        "env_original": env.get("EXAMDATA_INTEGRATION_ORIGINAL_APP_CODE"),
    }


def main() -> int:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    TMP_DIR.mkdir(parents=True, exist_ok=True)

    results: list[dict] = []
    findings: list[dict] = []
    transcript: list[str] = []

    for destination in DESTINATIONS:
        candidate = CANDIDATES / destination
        if not candidate.is_dir():
            findings.append({"id": "R04-MISSING-CANDIDATE", "severity": "blocker",
                             "candidate": str(candidate),
                             "summary": "candidate tree is missing; run r04_build_candidate.py"})
            continue
        for script in PROBES:
            result = run_probe(script, candidate)
            results.append(result)
            tag = f"{slug(destination)}::{script}"
            transcript.append(f"===== {tag} =====")
            transcript.append(f"$ cd {ROOT} && {PY} {RUN_DIR / script}")
            transcript.append(f"env PYTHONPATH=<unset> EXAMDATA_INTEGRATION_STAGING_ROOT=<unset> "
                              f"EXAMDATA_INTEGRATION_ROOT={candidate}")
            transcript.append(f"[exit {result['exit_code']}]")
            transcript.append("--- stdout ---")
            transcript.append(result["stdout"].rstrip("\n"))
            transcript.append("--- stderr ---")
            transcript.append(result["stderr"].rstrip("\n"))
            transcript.append("")
            (EVIDENCE / f"probe_{slug(destination)}__{script}.json").write_text(
                json.dumps({"exit_code": result["exit_code"], "report": result["report"],
                            "stderr": result["stderr"]}, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8")
            if result["exit_code"] != 0:
                findings.append({
                    "id": f"R04-PROBE-FAIL-{slug(destination)}-{script}",
                    "severity": "blocker",
                    "candidate": str(candidate),
                    "script": script,
                    "summary": f"{script} exited {result['exit_code']}",
                    "failed_checks": (result["report"] or {}).get("failed"),
                    "errors": (result["report"] or {}).get("errors"),
                    "stderr_tail": result["stderr"][-600:],
                })
            if result["env_pythonpath"] is not None:
                findings.append({"id": "R04-PYTHONPATH-STAGED", "severity": "blocker",
                                 "summary": "PYTHONPATH leaked into the probe environment",
                                 "value": result["env_pythonpath"]})
            if result["env_staging_override"] is not None:
                findings.append({"id": "R04-STAGING-OVERRIDE-STAGED", "severity": "blocker",
                                 "summary": "staging-root override leaked into the probe environment",
                                 "value": result["env_staging_override"]})

    summary: dict = {
        "schema": "examdata.integration.r04_layout_validation/1",
        "run_id": RUN_ID,
        "finding": "R04",
        "probes": [
            {"candidate": r["candidate"], "script": r["script"], "exit_code": r["exit_code"],
             "counts": (r["report"] or {}).get("counts"),
             "ok": (r["report"] or {}).get("ok")}
            for r in results
        ],
        "findings": findings,
        "not_run": [
            {"check": "real Node component execution",
             "reason": "gate original_paths_released is closed; synthetic fixture only"},
            {"check": "real original source / database validation",
             "reason": "gate original_paths_released is closed; no original path is read"},
        ],
        "verdict": "target_layout_valid_private_only" if not findings else "target_layout_not_valid",
        "note": ("private candidate only; not merged, not deployed; the original tree was "
                 "neither imported nor written; frozen evidence under evidence/B01/** and "
                 "runtime/phase-b/** was not touched"),
    }
    (EVIDENCE / "R04_LAYOUT_VALIDATION.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (EVIDENCE / "r04_layout_validation_run.txt").write_text(
        "\n".join(transcript) + "\n", encoding="utf-8")

    print(json.dumps({"evidence": str(EVIDENCE), "verdict": summary["verdict"],
                      "findings": [f["id"] for f in findings],
                      "probes": summary["probes"]}, ensure_ascii=True, indent=2))
    return 0 if not findings else 1


if __name__ == "__main__":
    raise SystemExit(main())
