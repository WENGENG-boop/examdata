"""Dump sub-letter sequences per parent question for 0472 indexes + the 4 partial volumes."""
import json
import os
import sys
from pathlib import Path

BR = Path(r"C:/Users/weo/Desktop/api/cie-location-batch")
os.chdir(BR)

TARGETS = []
idx_root = BR / "indexes" / "0472"
for d in sorted(idx_root.iterdir()):
    f = d / "cie-index.json"
    if f.is_file():
        TARGETS.append(f)

for f in TARGETS:
    data = json.loads(f.read_bytes().decode("utf-8"))
    kids = {}
    for q in data.get("questions") or []:
        if not isinstance(q, dict):
            continue
        qid = str(q.get("question"))
        parent = q.get("parent")
        if parent:
            kids.setdefault(str(parent), []).append(qid)
    print(f"== {f.parent.name}  qs={len(data.get('questions') or [])}")
    for parent in sorted(kids, key=lambda p: (len(p), p)):
        tokens = []
        for cid in kids[parent]:
            if cid.startswith(parent + "(") and cid.endswith(")"):
                tokens.append(cid[len(parent) + 1:-1])
            else:
                tokens.append("?" + cid)
        print(f"   {parent}: {tokens}")
