"""B02 rehearsal validation: run the runtime probe from several working directories.

The probe is launched as a subprocess whose environment is deliberately stripped
of the two crutches this rehearsal must not rely on:

* ``PYTHONPATH`` is removed -- the candidate ``src/`` tree is put on the import
  path by the probe itself;
* ``EXAMDATA_INTEGRATION_STAGING_ROOT`` is removed -- the candidate root is
  supplied only through the explicit product variable
  ``EXAMDATA_INTEGRATION_ROOT``.

The same probe runs from three working directories -- the workspace root, the
private tmp directory, and a directory whose name contains spaces and non-ASCII
characters -- and the component-discovery result must be identical in all three.

Writes evidence into a *new* directory under
``docs/integration/execution/evidence/B02/b02-rehearsal-20261006/``. Frozen
historical evidence (``evidence/B01/**``, ``evidence/R0104/**``,
``runtime/phase-b/**``, ``runtime/r0104-repair-20261006/**``) is never touched.
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[3]        # C:/Users/weo/Desktop/api
RUN_DIR = pathlib.Path(__file__).resolve().parent
RUN_ID = "b02-rehearsal-20261006"
DESTINATION = "b02-shared-config-v1"
CANDIDATE = ROOT / "integration-staging" / "runtime" / RUN_ID / "candidates" / DESTINATION
EVIDENCE = ROOT / "docs" / "integration" / "execution" / "evidence" / "B02" / RUN_ID
TMP_DIR = RUN_DIR / "evidence" / "tmp"
SPACED_CWD = TMP_DIR / "cwd with spaces \u00fcn\u00efcode"
PY = ROOT / "examdata" / ".venv" / "Scripts" / "python.exe"

PROBE = "b02_runtime_probe.py"


def probe_env() -> dict:
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env.pop("EXAMDATA_INTEGRATION_STAGING_ROOT", None)
    env["B02_CANDIDATE_ROOT"] = str(CANDIDATE)
    env["B02_WORKSPACE_ROOT"] = str(ROOT)
    env["B02_TMP_DIR"] = str(TMP_DIR)
    env["EXAMDATA_INTEGRATION_ROOT"] = str(CANDIDATE)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def run_probe(cwd: pathlib.Path) -> dict:
    path = RUN_DIR / PROBE
    env = probe_env()
    proc = subprocess.run([str(PY), str(path)], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=env, cwd=str(cwd),
                          timeout=900)
    out = (proc.stdout or "").strip()
    try:
        parsed = json.loads(out) if out else None
    except json.JSONDecodeError:
        parsed = None
    return {
        "cwd": str(cwd),
        "exit_code": proc.returncode,
        "report": parsed,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "env_pythonpath": env.get("PYTHONPATH"),
        "env_staging_override": env.get("EXAMDATA_INTEGRATION_STAGING_ROOT"),
        "env_root": env.get("EXAMDATA_INTEGRATION_ROOT"),
    }


def discovery_of(report: dict | None) -> dict | None:
    if not report:
        return None
    found = report.get("discovery", {}).get("from_candidate_cwd")
    if not found:
        return None
    return {k: found.get(k) for k in ("ids", "problems", "entry_path")}


SKIP_DIRS = {"__pycache__", ".pytest_cache"}


def digest_of(base: pathlib.Path, exclude: tuple[str, ...] = ()) -> dict:
    """Independent re-implementation of the candidate tree digest.

    Deliberately not imported from the builder: the point is to reproduce the
    recorded value a second time, so that the rollback guard ("delete only if the
    tree still matches") is checkable rather than merely asserted.
    """
    entries: list[tuple[str, str]] = []
    for p in sorted(base.rglob("*")):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.is_file():
            rel = p.relative_to(base).as_posix()
            if rel in exclude:
                continue
            entries.append((rel, hashlib.sha256(p.read_bytes()).hexdigest()))
    digest = hashlib.sha256()
    for rel, h in entries:
        digest.update(f"{rel}\0{h}\n".encode("utf-8"))
    return {"files": len(entries), "sha256": digest.hexdigest()}


def digest_reproducibility() -> dict:
    manifest_path = CANDIDATE / "B02_CANDIDATE_MANIFEST.json"
    raw = manifest_path.read_bytes()
    manifest = json.loads(raw.decode("utf-8"))
    recorded = manifest["candidate_tree"]
    recomputed = digest_of(CANDIDATE, tuple(recorded.get("excludes", [])))
    return {
        "recorded": recorded,
        "recomputed": recomputed,
        "files_match": recomputed["files"] == recorded["files"],
        "sha256_match": recomputed["sha256"] == recorded["sha256"],
        "manifest_sha256": hashlib.sha256(raw).hexdigest(),
    }


def main() -> int:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    SPACED_CWD.mkdir(parents=True, exist_ok=True)

    if not CANDIDATE.is_dir():
        print(json.dumps({"verdict": "candidate_missing", "candidate": str(CANDIDATE)},
                         ensure_ascii=True, indent=2))
        return 1

    cwds = (ROOT, TMP_DIR, SPACED_CWD)
    results: list[dict] = []
    findings: list[dict] = []
    transcript: list[str] = []

    for cwd in cwds:
        result = run_probe(cwd)
        results.append(result)
        tag = f"cwd={cwd}"
        transcript.append(f"===== {tag} =====")
        transcript.append(f"$ cd {cwd} && {PY} {RUN_DIR / PROBE}")
        transcript.append("env PYTHONPATH=<unset> EXAMDATA_INTEGRATION_STAGING_ROOT=<unset> "
                          f"EXAMDATA_INTEGRATION_ROOT={CANDIDATE}")
        transcript.append(f"[exit {result['exit_code']}]")
        transcript.append("--- stdout ---")
        transcript.append((result["stdout"] or "").rstrip("\n"))
        transcript.append("--- stderr ---")
        transcript.append((result["stderr"] or "").rstrip("\n"))
        transcript.append("")
        if result["exit_code"] != 0:
            findings.append({
                "id": "B02-PROBE-FAIL",
                "severity": "blocker",
                "cwd": str(cwd),
                "summary": f"{PROBE} exited {result['exit_code']}",
                "failed_checks": (result["report"] or {}).get("failed"),
                "stderr_tail": (result["stderr"] or "")[-600:],
            })
        if result["env_pythonpath"] is not None:
            findings.append({"id": "B02-PYTHONPATH-STAGED", "severity": "blocker",
                             "summary": "PYTHONPATH leaked into the probe environment",
                             "value": result["env_pythonpath"]})
        if result["env_staging_override"] is not None:
            findings.append({"id": "B02-STAGING-OVERRIDE-STAGED", "severity": "blocker",
                             "summary": "staging-root override leaked into the probe environment",
                             "value": result["env_staging_override"]})

    discovered = [discovery_of(r["report"]) for r in results]
    identical = len({json.dumps(d, sort_keys=True) for d in discovered}) == 1 \
        and all(d is not None for d in discovered)
    if not identical:
        findings.append({"id": "B02-DISCOVERY-CWD-DEPENDENT", "severity": "blocker",
                         "summary": "component discovery differs across working directories",
                         "discovery": discovered})

    probe_dirs = sorted({(r["report"] or {}).get("discovery", {}).get("from_candidate_cwd", {})
                         .get("cwd") for r in results if r["report"]})

    digest_check = digest_reproducibility()
    if not (digest_check["files_match"] and digest_check["sha256_match"]):
        findings.append({"id": "B02-DIGEST-NOT-REPRODUCIBLE", "severity": "blocker",
                         "summary": "the candidate tree digest in the manifest is not "
                         "reproducible from the tree on disk, so the rollback guard would "
                         "never match",
                         "recorded": digest_check["recorded"],
                         "recomputed": digest_check["recomputed"]})

    summary = {
        "schema": "examdata.integration.b02_rehearsal_validation/1",
        "run_id": RUN_ID,
        "packet": "B02",
        "candidate": str(CANDIDATE),
        "probe": PROBE,
        "runs": [
            {"cwd": r["cwd"], "exit_code": r["exit_code"],
             "checks": (r["report"] or {}).get("counts", {}).get("checks"),
             "checks_failed": (r["report"] or {}).get("counts", {}).get("checks_failed"),
             "ok": (r["report"] or {}).get("ok")}
            for r in results
        ],
        "discovery_identical_across_cwds": identical,
        "discovery": discovered[0] if identical else discovered,
        "in_process_cwds": probe_dirs,
        "candidate_tree_digest_reproducible": {
            "files_match": digest_check["files_match"],
            "sha256_match": digest_check["sha256_match"],
            "recorded": digest_check["recorded"],
            "recomputed": digest_check["recomputed"],
            "candidate_manifest_sha256": digest_check["manifest_sha256"],
        },
        "findings": findings,
        "not_run": [
            {"check": "real legacy Node gateway execution (ielts-api / toefl-api)",
             "reason": "gate original_paths_released is closed"},
            {"check": "real Node component execution",
             "reason": "gate original_paths_released is closed; synthetic fixture only"},
            {"check": "real database schema / data-root migration",
             "reason": "gate real_data_write_authorized is closed; schema and data roots unchanged"},
        ],
        "verdict": "b02_rehearsal_valid_private_only" if not findings else "b02_rehearsal_not_valid",
        "note": ("private candidate only; not merged, not deployed; the original tree was "
                 "neither read, imported nor written; frozen evidence under evidence/B01/**, "
                 "evidence/R0104/** and runtime/phase-b/** was not touched"),
    }
    (EVIDENCE / "B02_LAYOUT_VALIDATION.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (EVIDENCE / "b02_validation_run.txt").write_text(
        "\n".join(transcript) + "\n", encoding="utf-8")
    for index, result in enumerate(results, start=1):
        (EVIDENCE / f"probe_cwd{index}.json").write_text(
            json.dumps({"cwd": result["cwd"], "exit_code": result["exit_code"],
                        "report": result["report"], "stderr": result["stderr"]},
                       ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({"evidence": str(EVIDENCE), "verdict": summary["verdict"],
                      "findings": [f["id"] for f in findings],
                      "runs": summary["runs"],
                      "discovery_identical_across_cwds": identical,
                      "candidate_tree_digest_reproducible":
                          summary["candidate_tree_digest_reproducible"]["sha256_match"]},
                     ensure_ascii=True, indent=2))
    return 0 if not findings else 1


if __name__ == "__main__":
    raise SystemExit(main())
