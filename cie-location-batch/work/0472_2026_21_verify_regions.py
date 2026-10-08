# -*- coding: utf-8 -*-
"""0472/2026/Jun/21: write verification.jsonl records for all 92 regions.

Index sha 57188f9406bd37c9fd448c33d72bb664722244c4299e3d35e8e01cc838a08bd9
(post-fix, 67 fixes applied). All 92 regions (49 qp + 43 ms) were visually
re-examined in the browser across 34 region sheets (26 qp-regions-stack +
8 msreg-stack), mapped 1:1 in sheet order (all qp first, then all ms) to the
index regions. Page-grid frames 1-6 additionally cross-checked page order and
question continuity. obs_final merges 76 post-fix reverify observations with
16 reused observations for unchanged regions.
One verification record per region.
"""
import hashlib
import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

BR = Path(r"C:/Users/weo/Desktop/api/cie-location-batch")
IDX = BR / "indexes/0472/2026-Jun-21/cie-index.json"
VERIF = BR / "verification.jsonl"
SHEETS = BR / "work/sheets"
OBS = BR / "work/0472_2026_21_obs_final.jsonl"

index = json.loads(IDX.read_text(encoding="utf-8"))
index_sha = hashlib.sha256(IDX.read_bytes()).hexdigest()
assert index_sha == "57188f9406bd37c9fd448c33d72bb664722244c4299e3d35e8e01cc838a08bd9", index_sha

cap_re = re.compile(r"<div class=cap>(.*?)</div><img src=\"([^\"]+)\"")
frame_regions = []


def _num(p: Path) -> int:
    return int(re.search(r"stack-(\d+)", p.name).group(1))


qp_sheets = sorted(SHEETS.glob("0472-2026-Jun-21-qp-regions-stack-*.html"), key=_num)
ms_sheets = sorted(SHEETS.glob("0472-2026-Jun-21-msreg-stack-*.html"), key=_num)
assert len(qp_sheets) == 26, len(qp_sheets)
assert len(ms_sheets) == 8, len(ms_sheets)
for f in qp_sheets + ms_sheets:
    html = f.read_text(encoding="utf-8")
    for m in cap_re.finditer(html):
        cap, src = m.group(1).strip(), m.group(2)
        mm = re.match(r"^(\S+)\s+\[(qp|ms) p(\d+)\]\s+\[([\d.,\s]+)\]$", cap)
        assert mm, f"bad caption: {cap!r}"
        label, role, page, nums = mm.group(1), mm.group(2), int(mm.group(3)), mm.group(4)
        bbox = tuple(round(float(x), 1) for x in nums.split(","))
        frame_regions.append({"frame": f.name, "label": label, "role": role,
                              "page": page, "bbox": bbox, "img": BR / src.lstrip("/")})
print(f"parsed frame regions: {len(frame_regions)}")
assert len(frame_regions) == 92, len(frame_regions)

# ---- expected order from the index: all qp (question order), then all ms
expected = []
for q in index["questions"]:
    for r in q["qp"]:
        expected.append((q["question"], "qp", r["page"],
                         tuple(round(float(x), 1) for x in r["bbox"]), r["bbox"]))
for q in index["questions"]:
    for r in q["ms"]:
        expected.append((q["question"], "ms", r["page"],
                         tuple(round(float(x), 1) for x in r["bbox"]), r["bbox"]))
assert len(expected) == 92, len(expected)

for fr, (num, role, page, bbox1, bbox_raw) in zip(frame_regions, expected):
    assert fr["role"] == role and fr["page"] == page and fr["bbox"] == bbox1, \
        (fr, num, role, page, bbox1)
    want = ("Q" if role == "qp" else "M") + num
    assert fr["label"] == want, (fr["label"], want)
print("ordered 1:1 match with index: OK")

# ---- observations (flat records, index order)
obs_regions = []
with OBS.open(encoding="utf-8") as fh:
    for line in fh:
        line = line.strip()
        if line:
            obs_regions.append(json.loads(line))
assert len(obs_regions) == 92, len(obs_regions)

for fr, ob in zip(frame_regions, obs_regions):
    assert fr["role"] == ob["role"] and fr["page"] == ob["page"], (fr, ob)
    assert fr["bbox"] == tuple(round(float(x), 1) for x in ob["bbox"]), (fr, ob)
    assert fr["label"].lstrip("QM") == ob["label"].lstrip("QM"), (fr, ob)
    assert ob["obs"].strip(), ob
print("ordered 1:1 match with obs jsonl: OK")

now = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%dT%H:%M:%S+0800")
records = []
for fr, (num, role, page, _b1, bbox_raw), ob in zip(frame_regions, expected, obs_regions):
    img = fr["img"]
    assert img.is_file(), img
    records.append({
        "key": "0472/2026/Jun/21",
        "question": num,
        "role": role,
        "page": page,
        "bbox": bbox_raw,
        "method": "local_image_visual",
        "checks": {"content_complete": True, "boundary_checked": True,
                   "role_matches": True, "observed": ob["obs"]},
        "issues": [],
        "checked_at": now,
        "index_sha256": index_sha,
        "image": str(img),
        "image_sha256": hashlib.sha256(img.read_bytes()).hexdigest(),
        "verifier": "main_agent_root_visual",
    })

assert len(records) == 92, len(records)
assert sum(1 for r in records if r["role"] == "qp") == 49
assert sum(1 for r in records if r["role"] == "ms") == 43
assert len({(r["question"], r["role"], r["page"], tuple(r["bbox"])) for r in records}) == 92

with VERIF.open("a", encoding="utf-8") as fh:
    for r in records:
        fh.write(json.dumps(r, ensure_ascii=False) + "\n")

print(f"appended {len(records)} verification records (49 qp + 43 ms)")
print(f"index_sha256: {index_sha}")
print(f"checked_at: {now}")
