# -*- coding: utf-8 -*-
"""0472/2026/Jun/21: generate and append the 43 MS fixes (frame-34 MS text-layer audit)
to work/0472_2026_21_fixes.jsonl.

Rules (from the audit, summary "MS 43 条"):
- all 43 ms regions: x0 76.4->70.8, x1 (472.8|530.4|534.0)->541.2
  (include table left border 72.3-72.8 and right border 539.3-539.7,
   remove clipping of guidance text / footnotes).
- 6 regions whose y1 mixes in the next segment header row: pull y1 back to the
  segment bottom rule: Q1 p6 & 1(c) ->151.5; Q2 p6 & 2(g) ->346.1;
  Q4 p7 & 4(k) ->430.6.

Refuses to run twice (asserts no ms fix already in the file).
Appends in the existing jsonl schema: found_at_frame/question/role/page/
old_bbox/new_bbox/reason/evidence.
"""
import json
import re
from pathlib import Path

BR = Path(r"C:/Users/weo/Desktop/api/cie-location-batch")
IDX = BR / "indexes/0472/2026-Jun-21/cie-index.json"
FIXES = BR / "work/0472_2026_21_fixes.jsonl"

Y1_FIX = {
    "1": (190.4, 151.5, "第二段表头(167.5-179.1)"),
    "1(c)": (190.4, 151.5, "第二段表头(167.5-179.1)"),
    "2": (385.2, 346.1, "第三段表头(362.2-373.8)"),
    "2(g)": (385.2, 346.1, "第三段表头(362.2-373.8)"),
    "4": (471.2, 430.6, "第五段表头(448.7-460.3)"),
    "4(k)": (471.2, 430.6, "第五段表头(448.7-460.3)"),
}
X1_EXTRA = {
    "4(f)": "；另有指引文字 '…as long' 至 x532.0",
    "6(c)": "；另有脚注 '*NB…' 至 x534.7",
    "6(e)": "；文本至 x533.6（距 534.0 仅 0.4pt 紧边距）",
    "6(f)": "；另有脚注 '*NB…' 至 x534.7",
}
EVID = ("MS 文本层审计(帧34触发)：全部43区文本行bbox∩区域核对；表头/页脚/邻题行混入检查；"
        "段底粗线 150.8-151.5/345.4-346.1/430.0-430.6；表格边框 x 72.3-72.8 / 539.3-539.7；"
        "渲染裁剪核对 MS p6-p8")

index = json.loads(IDX.read_text(encoding="utf-8"))

existing = set()
if FIXES.exists():
    for line in FIXES.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        assert rec["role"] != "ms", f"ms fix already present: {rec['question']}"
        q = re.sub(r"^Q(?=\d)", "", rec["question"])
        existing.add((q, rec["role"], rec["page"]))

records = []
for q in index["questions"]:
    name = q["question"]
    for r in q["ms"]:
        x0, y0, x1, y1 = r["bbox"]
        assert x0 == 76.4 and x1 in (472.8, 530.4, 534.0), (name, r["bbox"])
        new_y1 = y1
        ypart = ""
        if name in Y1_FIX:
            oy1, new_y1, hdr = Y1_FIX[name]
            assert y1 == oy1, (name, y1, oy1)
            ypart = f"；y1={y1} 混入{hdr}，收至段底粗线底({new_y1})"
        reason = (f"x0=76.4 切表格左边框(72.3-72.8)；x1={x1} 切表格右边框(539.3-539.7)"
                  f"{X1_EXTRA.get(name, '')}{ypart}")
        records.append({
            "found_at_frame": 34, "question": name, "role": "ms", "page": r["page"],
            "old_bbox": list(r["bbox"]), "new_bbox": [70.8, y0, 541.2, new_y1],
            "reason": reason, "evidence": EVID,
        })

assert len(records) == 43, len(records)
assert sum(1 for r in records if r["new_bbox"][3] != r["old_bbox"][3]) == 6
overlap = {(r["question"], r["role"], r["page"]) for r in records} & existing
assert not overlap, f"overlap with existing fixes: {overlap}"

with FIXES.open("a", encoding="utf-8") as fh:
    for r in records:
        fh.write(json.dumps(r, ensure_ascii=False) + "\n")

total = sum(1 for line in FIXES.read_text(encoding="utf-8").splitlines() if line.strip())
print(f"appended {len(records)} ms fixes; fixes.jsonl now has {total} records")
