"""Dump detailed Q4/Q6 entries (text + regions) for 0472 papers to determine real sub-lettering."""
import json
import os
import sys
from pathlib import Path

BR = Path(r"C:/Users/weo/Desktop/api/cie-location-batch")
os.chdir(BR)

def dump(fname, prefix):
    f = BR / "indexes" / "0472" / fname / "cie-index.json"
    data = json.loads(f.read_bytes().decode("utf-8"))
    print(f"\n===== {fname} =====")
    for q in data.get("questions") or []:
        qid = str(q.get("question"))
        if qid.startswith(prefix):
            text = (q.get("text") or "").replace("\n", " ")[:90]
            marks = q.get("marks")
            qp = q.get("qp") or []
            ms = q.get("ms") or []
            unc = q.get("uncertain")
            notes = (q.get("notes") or "").replace("\n", " ")[:80]
            regions = "; ".join(f"p{r['page']}:{r['bbox']}" for r in qp[:4])
            msreg = "; ".join(f"p{r['page']}:{r['bbox']}" for r in ms[:3])
            print(f"  {qid!r} parent={q.get('parent')!r} marks={marks} unc={unc}")
            print(f"      text={text!r}")
            print(f"      qp={regions} | ms={msreg}")
            if notes:
                print(f"      notes={notes!r}")

dump("2025-Jun-22", "4")
dump("2025-Jun-22", "6")
