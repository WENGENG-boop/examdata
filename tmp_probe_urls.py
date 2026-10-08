"""Bounded probe: sample QP/MS URLs from the servlet for style analysis.

Writes JSON to tmp_edxprobe/urls.json for follow-up curl tests.
"""
import json
import collections
from pathlib import Path

from examdata.core.fetch import Fetcher
from examdata.adapters.edexcel import servlet

fetcher = Fetcher()
records = servlet.fetch_records(fetcher, ["Pearson-UK:Specification-Code/ial18-biology"])
print("total records:", len(records))

qp_ms = []
for rec in records:
    cats = rec.get("category") or []
    raw = None
    for c in cats:
        if c.startswith("Pearson-UK:Document-Type/"):
            raw = c.split("/", 1)[1]
    if raw in {"Question-paper", "Mark-scheme", "Mark-Scheme"}:
        qp_ms.append(rec)
print("qp/ms records:", len(qp_ms))

styles = collections.Counter()
spaced = []
dashed = []
for rec in qp_ms:
    url = rec["url"]
    if "International Advanced Level" in url:
        styles["spaced-family"] += 1
        spaced.append(rec)
    elif "International-Advanced-Level" in url:
        styles["dashed-family"] += 1
        dashed.append(rec)
    else:
        styles["other"] += 1
        spaced.append(rec)
print("styles:", dict(styles))

# also check any other spaces in paths
other_space = [r["url"] for r in qp_ms if " " in r["url"] and "International Advanced Level" not in r["url"]]
print("other-space urls:", len(other_space))
for u in other_space[:5]:
    print("   ", u)

# sample up to 6 spaced + 2 dashed across distinct series
def series_of(rec):
    for c in rec.get("category") or []:
        if c.startswith("Pearson-UK:Exam-Series/"):
            return c.split("/", 1)[1]
    return "?"

seen = set()
sample = []
for rec in spaced:
    s = series_of(rec)
    if s in seen:
        continue
    seen.add(s)
    sample.append(rec)
    if len(sample) >= 6:
        break
sample2 = []
seen2 = set()
for rec in dashed:
    s = series_of(rec)
    if s in seen2:
        continue
    seen2.add(s)
    sample2.append(rec)
    if len(sample2) >= 2:
        break

out = {
    "spaced": [{"url": r["url"], "series": series_of(r), "objectID": r.get("objectID")} for r in sample],
    "dashed": [{"url": r["url"], "series": series_of(r), "objectID": r.get("objectID")} for r in sample2],
}
Path("tmp_edxprobe").mkdir(exist_ok=True)
Path("tmp_edxprobe/urls.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
print("wrote tmp_edxprobe/urls.json")
for group in ("spaced", "dashed"):
    for item in out[group]:
        print(group, item["series"], item["url"])
