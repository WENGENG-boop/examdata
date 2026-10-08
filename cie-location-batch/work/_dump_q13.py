# -*- coding: utf-8 -*-
"""Dump Q1/Q3/Q4/Q6 current index state (regions + text head) for the two remaining 0472 22-volumes."""
import json
import sys

sys.path.insert(0, "tools")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import batchlib as B

KEYS = ["0472/2025/Jun/22", "0472/2026/Jun/22"]
WANT = ("1", "3", "4", "6")

for key in KEYS:
    subj, year, season, paper = key.split("/")
    path = B.index_dir(subj, int(year), season, paper) / "cie-index.json"
    data = json.loads(path.read_bytes().decode("utf-8"))
    print(f"===== {key} =====")
    for q in data.get("questions") or []:
        qid = str(q.get("question"))
        if not any(qid == w or qid.startswith(w + "(") for w in WANT):
            continue
        qp = "; ".join(f"p{r['page']}:[{','.join(str(round(x, 1)) for x in r['bbox'])}]"
                       for r in (q.get("qp") or []))
        ms = "; ".join(f"p{r['page']}:[{','.join(str(round(x, 1)) for x in r['bbox'])}]"
                       for r in (q.get("ms") or []))
        text = (q.get("text") or "").replace("\n", " ")[:52]
        print(f"  {qid!r} par={q.get('parent')!r} unc={q.get('uncertain')}")
        print(f"     qp={qp} | ms={ms}")
        print(f"     {text}")
