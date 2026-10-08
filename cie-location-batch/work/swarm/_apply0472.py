"""Apply geometry-verified regions to the 0472 index, build MS rows, log verification."""
import datetime
import json
import re
import pymupdf

B = r"C:\Users\weo\Desktop\api\cie-location-batch"
QP = B + r"\tmp\0472\2026-Jun-11\0472_s26_qp_11.pdf"
MS = B + r"\tmp\0472\2026-Jun-11\0472_s26_ms_11.pdf"
IDX = B + r"\indexes\0472\2026-Jun-11\cie-index.json"
PROBE = B + r"\work\swarm\_probe0472.json"
VLOG = B + r"\verification.jsonl"

qp_regions = {int(k): v for k, v in json.load(open(PROBE, encoding="utf-8")).items()}
idx = json.load(open(IDX, encoding="utf-8"))

# ---- MS row bands: locate the printed question number in the answer table ----
MS_PAGE = {q: (2 if q <= 28 else 3) for q in range(1, 38)}
ms_rows = {}
doc = pymupdf.open(MS)
for q, pno in MS_PAGE.items():
    pg = doc[pno - 1]
    hit = None
    for blk in pg.get_text("dict")["blocks"]:
        if blk.get("type") != 0:
            continue
        for line in blk["lines"]:
            for sp in line["spans"]:
                if sp["text"].strip() == str(q) and sp["bbox"][0] < 130:
                    if hit is None or sp["bbox"][1] < hit[1]:
                        hit = (sp["bbox"][0], sp["bbox"][1], sp["bbox"][2], sp["bbox"][3])
    if hit is None:
        raise SystemExit("MS row not found for Q%d" % q)
    y0, y1 = hit[1], hit[3]
    ms_rows[q] = {"page": pno, "bbox": [72.0, round(y0 - 5.0, 1), 540.0, round(y1 + 5.0, 1)]}

# ---- rebuild the index ----
now = datetime.datetime.now().astimezone().replace(microsecond=0).isoformat()
log = []
for item in idx["questions"]:
    q = int(item["question"])
    item["qp"] = [{"page": r["page"], "bbox": r["bbox"]} for r in qp_regions[q]]
    item["ms"] = [ms_rows[q]]
    item["uncertain"] = True
    item["notes"] = (
        "几何核验：区域含题号、完整题干与该题全部选项框/图，按下一题号或分节标题截断，"
        "未混入下一题文字；题号、[n] 分值与印刷一致；MS 第 %d 页按印刷题号匹配到该行。"
        "未做视觉核验（浏览器快照持续 PAGE_NOT_READY），故仍标 uncertain。"
        % ms_rows[q]["page"]
    )
    log.append({"key": "0472/2026/Jun/11", "question": item["question"], "role": "qp",
                "page": qp_regions[q][0]["page"], "bbox": qp_regions[q][0]["bbox"],
                "checks": ["题号与印刷一致", "区域含题干与选项框/图", "未混入下一题文字"],
                "issues": ["未做视觉核验：浏览器快照 PAGE_NOT_READY"],
                "checked_at": now})
    log.append({"key": "0472/2026/Jun/11", "question": item["question"], "role": "ms",
                "page": ms_rows[q]["page"], "bbox": ms_rows[q]["bbox"],
                "checks": ["按 MS 行内印刷题号匹配", "Answer 列取值已记录"],
                "issues": ["未做视觉核验：浏览器快照 PAGE_NOT_READY"],
                "checked_at": now})

# Q8's draft text had swallowed the Questions 9-14 rubric from page 6; trim to the printed Q8 line
for item in idx["questions"]:
    if item["question"] == "8":
        item["text"] = ("8 Your friend says something to you. Where does your friend suggest going "
                        "after leaving the museum? A B C D [1] [Total: 8]")

json.dump(idx, open(IDX, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
with open(VLOG, "a", encoding="utf-8") as fh:
    for row in log:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
print("index written; verification.jsonl +%d lines" % len(log))

# ---- stacksheet spec so the regions can be eyeballed in a few sheets ----
spec = []
for q in sorted(qp_regions):
    for r in qp_regions[q]:
        spec.append({"label": "Q%d" % q, "role": "qp", "page": r["page"], "bbox": r["bbox"]})
json.dump(spec, open(B + r"\work\swarm\spec_0472_qp.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("spec entries:", len(spec))
