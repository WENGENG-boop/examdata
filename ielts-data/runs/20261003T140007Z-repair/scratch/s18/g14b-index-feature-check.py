#!/usr/bin/env python
"""G14b: locate pte-4L feature words inside the canonical index; print identity context."""
import json
import re
from pathlib import Path

P = Path("C:/Users/weo/Desktop/api/ielts-data/indexes/rev-8b21015ab64bb73c/questions.json")
PAT = re.compile(r"argus|costwise|holman|743002|electric\s*wire|beach\s*erosion", re.I)

d = json.loads(P.read_text(encoding="utf-8"))
print("top-level:", type(d).__name__)
if isinstance(d, dict):
    print("keys:", list(d.keys()))
    lists = [(k, v) for k, v in d.items() if isinstance(v, list) and len(v) > 5]
    print("list-valued keys:", [(k, len(v)) for k, v in lists])
    items = []
    for k, v in lists:
        items.extend([(f"{k}[{i}]", x) for i, x in enumerate(v) if isinstance(x, dict)])
elif isinstance(d, list):
    items = [(f"[{i}]", x) for i, x in enumerate(d) if isinstance(x, dict)]
else:
    items = []

print("candidate items:", len(items))


def compact(item):
    out = {}
    for k, v in item.items():
        if isinstance(v, (str, int, float, bool)) and len(str(v)) < 140:
            out[k] = v
        elif isinstance(v, dict):
            for k2, v2 in v.items():
                if isinstance(v2, (str, int, float, bool)) and len(str(v2)) < 140:
                    out[f"{k}.{k2}"] = v2
    return out


n_hit = 0
for path, item in items:
    s = json.dumps(item, ensure_ascii=False)
    if PAT.search(s):
        n_hit += 1
        print("=== HIT", path)
        c = compact(item)
        print("   identity:", json.dumps(c, ensure_ascii=False)[:400])
        for m in set(m.group(0).lower() for m in PAT.finditer(s)):
            pass
        for m in PAT.finditer(s):
            a = max(0, m.start() - 60)
            b = min(len(s), m.end() + 60)
            print("   match:", s[a:b].replace("\\n", " ")[:180])
print("hit items:", n_hit)
