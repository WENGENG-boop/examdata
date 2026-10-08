# -*- coding: utf-8 -*-
"""Final numbers recompute for the audit answer (read-only). One-off."""
import glob
import json
import os
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
B = r"C:/Users/weo/Desktop/api/cie-location-batch"
SVC = r"C:/Users/weo/Desktop/api/examdata/.pytest_cache/callable-api"

tot_f = tot_b = 0
stages = Counter()
stages_f = Counter()
stages_b = Counter()
cleaned_keys = Counter()
cleaned_dups = []
for line in open(B + "/cleanup.jsonl", encoding="utf-8"):
    line = line.strip()
    if not line:
        continue
    r = json.loads(line)
    st = r.get("stage")
    stages[st] += 1
    f = r.get("deleted")
    if not isinstance(f, int):
        fl = r.get("files")
        f = len(fl) if isinstance(fl, list) else 0
    b = r.get("freed_bytes") if isinstance(r.get("freed_bytes"), int) else 0
    tot_f += f
    tot_b += b
    stages_f[st] += f
    stages_b[st] += b
    if st == "cleaned":
        k = r.get("key")
        if k is None:
            k = "(no key field)"
            print("SAMPLE cleaned rec:", json.dumps(r, ensure_ascii=False)[:400])
        cleaned_keys[k] += 1
        cleaned_dups.append((k, f, r.get("at") or r.get("cleaned_at") or r.get("ts") or "?"))

print("cleanup records:", sum(stages.values()))
print("total deleted files:", tot_f, "| total freed bytes:", f"{tot_b:,}")
print("per-stage recs/files/bytes:")
for st in stages:
    print(f"  {st}: recs={stages[st]} files={stages_f[st]} bytes={stages_b[st]:,}")
print("cleaned records:", sum(cleaned_keys.values()), "| unique cleaned keys:", len(cleaned_keys))
print("dup cleaned keys:", {k: c for k, c in cleaned_keys.items() if c > 1})
for k, f, at in cleaned_dups:
    if cleaned_keys[k] > 1:
        print(f"  dup detail: {k} deleted={f} at={at}")

papers = json.load(open(B + "/papers.json", encoding="utf-8"))
p_cleaned = {k for k, v in papers.items() if isinstance(v, dict) and v.get("stage") == "cleaned"}
print("papers cleaned keys:", len(p_cleaned))
print("cleanup-only keys:", sorted(set(cleaned_keys) - p_cleaned))
print("papers-only keys:", sorted(p_cleaned - set(cleaned_keys)))

res = []
for k in sorted(p_cleaned):
    subj, year, season, paper = k.split("/")
    d = f"{B}/tmp/{subj}/{year}-{season}-{paper}"
    n = 0
    if os.path.isdir(d):
        for dp, dn, fn in os.walk(d):
            n += len(fn)
    if n:
        res.append((k, n))
print("cleaned keys with tmp residue:", res if res else "NONE")

svc = glob.glob(SVC + "/question_indexes/cie/*.json")
print("service indexes:", len(svc))
pdfs = glob.glob(SVC + "/**/*.pdf", recursive=True)
print("service dir PDFs:", len(pdfs))

pilot = r"C:/Users/weo/Desktop/api/cie-index-batch-2026-10-01"
cnt = Counter()
tot = 0
for dp, dn, fn in os.walk(pilot):
    for f in fn:
        cnt[os.path.splitext(f)[1].lower()] += 1
        tot += 1
print("pilot files:", tot, dict(cnt))
