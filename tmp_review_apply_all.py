"""Batch apply review decisions for all subjects that have decision files.

Runs `python -m examdata.tagging review-apply --subject <slug> --decisions <dir> --write --json`
for each subject under .data/tagging/review-export/*/decisions/ that has *.jsonl files.
Prints a compact summary and saves per-subject JSON to tmp_ra_apply_<slug>.json.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(".data/tagging/review-export")
PY = str(pathlib.Path(".venv/Scripts/python.exe").resolve())

total = {"decisions": 0, "kept": 0, "changed": 0, "dropped": 0, "errors": 0}
failures: list[str] = []

for d in sorted(ROOT.iterdir()):
    dec = d / "decisions"
    if not dec.is_dir():
        continue
    files = sorted(dec.glob("*.jsonl"))
    if not files:
        continue
    slug = d.name
    p = subprocess.run(
        [PY, "-m", "examdata.tagging", "review-apply",
         "--subject", slug, "--decisions", str(dec), "--write", "--json"],
        capture_output=True, text=True, encoding="utf-8",
    )
    out = (p.stdout or "").strip()
    try:
        data = json.loads(out)
    except Exception:
        data = None
    if data is None:
        failures.append(f"{slug}: rc={p.returncode} stdout_tail={out[-300:]!r} stderr_tail={(p.stderr or '').strip()[-300:]!r}")
        print(f"{slug}\tFILES={len(files)}\tPARSE_FAIL\trc={p.returncode}")
        continue
    (pathlib.Path(f"tmp_ra_apply_{slug}.json")).write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    errs = data.get("errors") or []
    for k in ("decisions", "kept", "changed", "dropped"):
        total[k] += int(data.get(k) or 0)
    total["errors"] += len(errs)
    print(f"{slug}\tFILES={len(files)}\tdec={data.get('decisions')}\tkeep={data.get('kept')}\tchg={data.get('changed')}\tdrop={data.get('dropped')}\terrors={len(errs)}\trc={p.returncode}")
    for e in errs[:5]:
        print(f"    ERR: {e}")
    if p.returncode not in (0, 1):
        failures.append(f"{slug}: rc={p.returncode} stderr_tail={(p.stderr or '').strip()[-300:]!r}")

print("\nTOTAL\t" + json.dumps(total, ensure_ascii=False))
if failures:
    print("FAILURES:")
    for f in failures:
        print("  -", f)
else:
    print("FAILURES: none")
