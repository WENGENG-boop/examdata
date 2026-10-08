#!/usr/bin/env python
"""Coordinator wave verification (read-only against frozen inputs).

Run after each W-package agent reports, before accepting its claims:

  <py> -B tools/coordinator_verify.py <label> [candidate-dir]

Checks, all against the LIVE candidate (default `<run>/candidates/closure-v1`):
  1. full pytest suite (run/tests, exact W3 command discipline) -> exit + tail;
  2. hygiene: any __pycache__ / .pytest_cache under the run root;
  3. frozen inputs recheck: parent tree digest (historical), parent manifest
     sha256, formal execution-ledger sha256 - compared to the recorded pins;
  4. candidate digests: posix-v1 + historical, file count.

Writes only under `<run>/evidence/verify/<label>-<stamp>/`. Never touches the
frozen parent or the ledger (it only hashes them). NOT for use with
`closure_provenance.py main()`, which performs the phase-0 copy step.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import datetime

RUN = pathlib.Path(__file__).resolve().parents[1]
TOOLS = RUN / "tools"
PY = pathlib.Path("C:/Users/weo/Desktop/api/examdata/.venv/Scripts/python.exe")

EXPECT_PARENT_DIGEST = "8171cf1c67c7891fc4c3354a482fb65600886aa0b5b88f9a1a546333c738fa48"
EXPECT_PARENT_FILES = 222
EXPECT_PARENT_MANIFEST_SHA = "920f41c1b98199b087a4a8c7dea918c23d0f8144afdfebb87bfb2b2e9bcec9ce"
EXPECT_LEDGER_SHA = "6d4449d3997b437fd3ea3a1fe7925fc78a7c0adbe0a5d3b793d6a8063101b4ba"


def sha256_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_closure_provenance():
    spec = importlib.util.spec_from_file_location(
        "closure_provenance", TOOLS / "closure_provenance.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    label = sys.argv[1]
    cand = pathlib.Path(sys.argv[2]).resolve() if len(sys.argv) > 2 \
        else RUN / "candidates" / "closure-v1"
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = RUN / "evidence" / "verify" / f"{label}-{stamp}"
    out.mkdir(parents=True, exist_ok=True)
    summary: dict = {"label": label, "candidate": str(cand), "stamp": stamp}

    # 1. full suite -----------------------------------------------------------
    env = dict(os.environ)
    env.pop("EXAMDATA_INTEGRATION_STAGING_ROOT", None)
    env["PYTHONPATH"] = str(cand / "src")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["B07R2_EXPECT_CANDIDATE_ROOT"] = str(cand)
    basetemp = RUN / "tmp" / f"verify-{label}-{stamp}"
    proc = subprocess.run(
        [str(PY), "-B", "-m", "pytest", "-c", "pytest.ini", ".",
         "-p", "no:cacheprovider", "--basetemp", str(basetemp), "-q", "-rs"],
        cwd=str(RUN / "tests"), env=env, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=900)
    log = out / "full_suite.txt"
    log.write_text((proc.stdout or "") + (proc.stderr or ""), encoding="utf-8")
    tail = [ln for ln in (proc.stdout or "").strip().splitlines() if ln.strip()][-3:]
    summary["full_suite_exit"] = proc.returncode
    summary["full_suite_tail"] = tail
    print(f"[1] full suite exit={proc.returncode} :: {tail[-1] if tail else '?'}")

    # 2. hygiene --------------------------------------------------------------
    bad: list[str] = []
    for dirpath, dirnames, _files in os.walk(RUN):
        for name in list(dirnames):
            if name in ("__pycache__", ".pytest_cache"):
                bad.append(str(pathlib.Path(dirpath) / name))
    (out / "hygiene.txt").write_text("\n".join(bad) + ("\n" if bad else ""),
                                     encoding="utf-8")
    summary["pycache_dirs"] = bad
    print(f"[2] pycache/pytest_cache dirs under run root: {len(bad)}")

    # 3. frozen inputs recheck ------------------------------------------------
    mod = load_closure_provenance()
    frozen: dict = {}
    parent_rows = mod.tree_entries(mod.PARENT, exclude=("B07R2_CANDIDATE_MANIFEST.json",))
    parent_hist = mod.digest(parent_rows, "historical")
    frozen["parent_historical"] = parent_hist["sha256"]
    frozen["parent_files"] = parent_hist["files"]
    frozen["parent_manifest_sha256"] = sha256_file(mod.MANIFEST)
    frozen["ledger_sha256"] = sha256_file(mod.LEDGER)
    ok = (parent_hist["sha256"] == EXPECT_PARENT_DIGEST
          and parent_hist["files"] == EXPECT_PARENT_FILES
          and frozen["parent_manifest_sha256"] == EXPECT_PARENT_MANIFEST_SHA
          and frozen["ledger_sha256"] == EXPECT_LEDGER_SHA)
    frozen["match"] = ok
    summary["frozen"] = frozen
    print(f"[3] frozen inputs match: {ok} "
          f"(parent={parent_hist['sha256'][:16]} files={parent_hist['files']}, "
          f"ledger={frozen['ledger_sha256'][:16]})")

    # 4. candidate digests ----------------------------------------------------
    if cand.is_dir():
        cand_rows = mod.tree_entries(cand, exclude=("B07R2_CANDIDATE_MANIFEST.json",))
        summary["candidate_posix_v1"] = mod.digest(cand_rows, "posix-v1")
        summary["candidate_historical"] = mod.digest(cand_rows, "historical")
        c = summary["candidate_posix_v1"]
        print(f"[4] candidate posix-v1={c['sha256'][:16]} files={c['files']}")
    else:
        summary["candidate_posix_v1"] = None
        print(f"[4] candidate dir missing: {cand}")

    (out / "summary.json").write_text(json.dumps(summary, indent=2),
                                      encoding="utf-8")
    print(f"evidence: {out}")
    return 0 if (summary["full_suite_exit"] == 0 and ok and not bad) else 1


if __name__ == "__main__":
    raise SystemExit(main())
