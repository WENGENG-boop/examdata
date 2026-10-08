# -*- coding: utf-8 -*-
"""Read-only audit: for every key with a permanent index, report gate state,
verification stats, stage, and local original presence. One-off, no writes."""
import json
import sys
from pathlib import Path

sys.path.insert(0, "tools")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import batchlib as B
import paperlib as P
import cleanup_paper as C
import import_index as I

rows = []
indexes_root = B.BATCH_ROOT / "indexes"
for path in sorted(indexes_root.rglob("cie-index.json")):
    rel = path.relative_to(indexes_root)
    subject = rel.parts[0]
    stem = rel.parts[1]
    year, season, paper = stem.split("-")
    key = f"{subject}/{year}/{season}/{paper}"
    entry = P.load_paper(key) or {}
    problems, info = C.check_conditions(key)
    v = info.get("verification", {})
    qp = I.locate_pdf(key, "qp")
    ms = I.locate_pdf(key, "ms")
    tmp = P.paper_tmp(key)
    nfiles = 0
    npng = 0
    if tmp.is_dir():
        for p in tmp.rglob("*"):
            if p.is_file():
                nfiles += 1
                if p.suffix.lower() == ".png":
                    npng += 1
    rows.append({
        "key": key,
        "stage": entry.get("stage") or info.get("stage"),
        "gate_problems": len(problems),
        "problems": problems,
        "regions": v.get("regions"),
        "verified": v.get("verified"),
        "failed": v.get("failed"),
        "missing": v.get("missing"),
        "self_unverified": v.get("self_declared_unverified"),
        "numbering": v.get("numbering"),
        "qp_pdf": bool(qp), "ms_pdf": bool(ms),
        "tmp_files": nfiles, "tmp_pngs": npng,
    })

print(f"TOTAL indexed keys: {len(rows)}")
clean_gate = [r for r in rows if r["gate_problems"] == 0]
print(f"gate pass: {len(clean_gate)}")
print()
print("=== gate FAIL (need work) ===")
for r in rows:
    if r["gate_problems"] == 0:
        continue
    n = r["numbering"] or {}
    print(f"{r['key']}  stage={r['stage']}  regions={r['regions']} verified={r['verified']} "
          f"failed={r['failed']} missing={r['missing']} self_unv={r['self_unverified']} "
          f"qp={r['qp_pdf']} ms={r['ms_pdf']} tmp_files={r['tmp_files']} pngs={r['tmp_pngs']}")
    for p in r["problems"]:
        print(f"    ! {p[:220]}")
print()
print("=== gate PASS but PDFs remain (cleanup not done) ===")
for r in rows:
    if r["gate_problems"] == 0 and (r["qp_pdf"] or r["ms_pdf"]):
        print(f"{r['key']} stage={r['stage']} qp={r['qp_pdf']} ms={r['ms_pdf']} tmp_files={r['tmp_files']}")
print()
print("=== gate PASS, no PDFs, tmp leftovers ===")
for r in rows:
    if r["gate_problems"] == 0 and not (r["qp_pdf"] or r["ms_pdf"]) and r["tmp_files"]:
        print(f"{r['key']} stage={r['stage']} tmp_files={r['tmp_files']} pngs={r['tmp_pngs']}")

out = B.BATCH_ROOT / "work" / "_pending_audit_out.json"
out.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"\nwritten {out}")
