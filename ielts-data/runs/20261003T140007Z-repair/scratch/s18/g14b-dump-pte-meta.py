#!/usr/bin/env python
"""G14b: dump practicepteonline raw metas + pte JSON source fields for identity analysis."""
import json
import sys
from pathlib import Path

ROOT = Path("C:/Users/weo/Desktop/api")
RAW = ROOT / "ielts-data/raw/practicepteonline"
COMP = ROOT / "tmp_audit_ielts/completeness_20261003"
OUT = ROOT / "ielts-data/runs/20261003T140007Z-repair/scratch/s18"

# 1) metas
rows = []
for f in sorted(RAW.glob("*.meta.json")):
    m = json.loads(f.read_text(encoding="utf-8"))
    rows.append([
        f.name.split(".")[0][:16],
        str(m.get("book")), str(m.get("test")), str(m.get("variant")), str(m.get("skill")),
        str(m.get("slug")), str(m.get("raw_index")), str(m.get("source_page_id")),
    ])
hdr = "hash16\tbook\ttest\tvariant\tskill\tslug\traw_index\tpage_id"
lines = [hdr] + ["\t".join(r) for r in rows]
(OUT / "g14b-pte-meta.tsv").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"metas: {len(rows)} -> g14b-pte-meta.tsv")

# summarize by skill and by (book,test)
from collections import Counter
c_skill = Counter((r[4]) for r in rows)
print("by skill:", dict(c_skill))

# 2) pte json sources
src_lines = []
for f in sorted(COMP.glob("pte-*.json")):
    j = json.loads(f.read_text(encoding="utf-8"))
    def find(d, keys):
        out = {}
        if isinstance(d, dict):
            for k, v in d.items():
                if isinstance(v, (dict, list)):
                    out.update(find(v, keys))
                elif any(s in k.lower() for s in keys):
                    out[k] = v
        elif isinstance(d, list):
            for v in d[:3]:
                out.update(find(v, keys))
        return out
    info = find(j, ["slug", "url", "page_id", "source", "count"])
    src_lines.append(f"== {f.name}")
    src_lines.append(json.dumps(info, ensure_ascii=False, sort_keys=True))
(OUT / "g14b-pte-sources.txt").write_text("\n".join(src_lines) + "\n", encoding="utf-8")
print(f"pte jsons: {len(list(COMP.glob('pte-*.json')))} -> g14b-pte-sources.txt")
