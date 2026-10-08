"""0472/2024/Jun/11: fill ms regions + clear uncertain after visual check.

- ms regions from work/specs/0472-ms-regions.json (37 entries, labels "1".."37")
- notes rewritten to record visual verification (2026-10-03, viewer v=4, 26/26 frames)
- atomic replace; prints new sha256
"""
import hashlib
import json
import os
import sys
from pathlib import Path

BR = Path(r"C:/Users/weo/Desktop/api/cie-location-batch")
IDX = BR / "indexes/0472/2024-Jun-11/cie-index.json"
SPEC = BR / "work/specs/0472-ms-regions.json"

index = json.loads(IDX.read_text(encoding="utf-8"))
spec = json.loads(SPEC.read_text(encoding="utf-8"))

ms_map = {}
for entry in spec:
    label = str(entry["label"])
    ms_map.setdefault(label, []).append({"page": entry["page"], "bbox": entry["bbox"]})

# section-first questions: which qp[0] is the shared section instruction region
section_first = {"1": "1–8", "9": "9–14", "15": "15–19", "20": "20–28", "25": "25–28",
                 "29": "29–34", "35": "35–37"}

filled = 0
for q in index["questions"]:
    num = q["question"]
    if num not in ms_map:
        print(f"ERROR: no ms region for question {num}", file=sys.stderr)
        sys.exit(1)
    q["ms"] = ms_map[num]
    q["uncertain"] = False
    if num in section_first:
        q["notes"] = (f"含本节（{section_first[num]}）共同说明区域（qp[0]）；"
                      f"区域/文字/ms 经视觉核验（2026-10-03，viewer v=4 全帧通过）")
    else:
        q["notes"] = "区域/文字/ms 经视觉核验（2026-10-03，viewer v=4 全帧通过）"
    filled += 1

assert filled == 37, filled
assert len(index["questions"]) == 37

tmp = IDX.with_suffix(".json.tmp")
tmp.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
os.replace(tmp, IDX)

sha = hashlib.sha256(IDX.read_bytes()).hexdigest()
print(f"filled ms regions: {filled}; uncertain=false: 37")
print(f"new index sha256: {sha}")
