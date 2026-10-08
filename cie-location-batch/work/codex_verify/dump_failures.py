import json, sys, os
from collections import Counter

BASE = os.path.dirname(os.path.abspath(__file__))
SLUGS = ["0413-2026-Jun-11", "0509-2026-Jun-11", "8386-2026-Jun-11",
         "9709-2024-Jun-11", "9715-2023-Nov-21", "9396-2023-Nov-11"]

def fail(r):
    if r.get("issues"):
        return True
    ch = r.get("checks") or {}
    if not ch:
        return True
    return not all(bool(v) for v in ch.values())

for slug in SLUGS:
    p = os.path.join(BASE, slug + "-records.json")
    if not os.path.exists(p):
        print(f"== {slug}: records missing ==")
        continue
    recs = json.load(open(p, encoding="utf-8"))
    bad = [r for r in recs if fail(r)]
    print(f"== {slug}: {len(recs)} records, {len(bad)} failing ==")
    for r in bad:
        cx = r.get("codex") or {}
        qn = cx.get("question_numbers") or []
        print(json.dumps({
            "q": r.get("question"), "role": r.get("role"), "page": r.get("page"),
            "bbox": [round(x,1) for x in r.get("bbox", [])],
            "checks": r.get("checks"), "issues": r.get("issues"),
            "cx_qn": qn, "cx_edge": cx.get("edge_cut"),
            "cx_observed": (cx.get("observed") or "")[:110],
            "cx_head": (cx.get("text_head") or "")[:70],
        }, ensure_ascii=False))
    print()
