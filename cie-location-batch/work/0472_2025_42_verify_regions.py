"""0472/2025/Jun/42: write verification.jsonl records for all 20 regions.

Index sha 8664df919d9620c9b26f3ea8337ec02cc73c070b625fba4ccc9c57c846081ea0.
Region bounds were re-examined this window with span probes:
[5] on QP p2 (y570.5-581.1 x527.5-539.0) and [12] on QP p3
(y525.4-535.9 x521.5-538.7) and both [28] on QP p4 (y219.6-230.2 /
y488.6-499.2 x521.7-539.0) all sit inside the indexed bboxes, and the
lower bounds match the accepted 41 convention (footer row included), so
no fix was needed. Viewer frames: 5 qp-regions-stack (Q1,Q2,Q3,Q3(a),Q3(b))
+ 9 msreg-stack frames covering 15 ms regions; the exact crop images shown
in frame order (all qp first, then all ms) are mapped 1:1 to the index
regions, never by a keyed lookup. One verification record per region.
"""
import hashlib
import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

BR = Path(r"C:/Users/weo/Desktop/api/cie-location-batch")
IDX = BR / "indexes/0472/2025-Jun-42/cie-index.json"
VERIF = BR / "verification.jsonl"
SHEETS = BR / "work/sheets"

index = json.loads(IDX.read_text(encoding="utf-8"))
index_sha = hashlib.sha256(IDX.read_bytes()).hexdigest()
assert index_sha == "8664df919d9620c9b26f3ea8337ec02cc73c070b625fba4ccc9c57c846081ea0", index_sha

# ---- parse viewer frames in order: (label, role, page, bbox) + crop image
cap_re = re.compile(r"<div class=cap>(.*?)</div><img src=\"([^\"]+)\"")
frame_regions = []
frames = (sorted(SHEETS.glob("0472-2025-Jun-42-qp-regions-stack-*.html"))
          + sorted(SHEETS.glob("0472-2025-Jun-42-msreg-stack-*.html")))
assert len(frames) == 14, len(frames)
for f in frames:
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
assert len(frame_regions) == 20, len(frame_regions)

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
assert len(expected) == 20, len(expected)

for fr, (num, role, page, bbox1, bbox_raw) in zip(frame_regions, expected):
    assert fr["role"] == role and fr["page"] == page and fr["bbox"] == bbox1, \
        (fr, num, role, page, bbox1)
    want = ("Q" if role == "qp" else "M") + num
    assert fr["label"] == want, (fr["label"], want)
print("ordered 1:1 match with index: OK")

# ---- observations from the browser visual re-verification (frame order)
OBS = [
    # 1 Q1 qp p2
    "QP p2 区域：题号 1 + 'You are Sara Johnson. Your school is planning a cooking competition and you would like to take part. Complete the form.' + 表单表（Name | Sara Johnson；Class | 6A；What you will cook | 答题虚线；How long it will take | 答题虚线）+ 'Now give more information about the cooking you do.' + 'Write about:' 三条（how often you cook / why you enjoy cooking / what you find difficult about cooking.）+ 'Write 20–30 words.' + 答题虚线 ×4 + [5]（右对齐于最后虚线下方 y570.5-581.1 x527.5-539.0，已探针确认在区域内）+ 区域下界含页脚行（与 41 同约定）；无下一题混入。",
    # 2 Q2 qp p3
    "QP p3 区域：题号 2 + 'School library' + 5 条 bullet（Describe your school library. / How often do you use the school library? / What do you usually do in the school library? / What do you like most about the school library? / How could the school improve the library in the future?）+ 'Write 80–90 words.' + 答题虚线 ×16 + [12]（右对齐于最后虚线行右端 y525.4-535.9 x521.5-538.7，已探针确认在区域内）+ 页脚 [Turn over；无下一题混入。",
    # 3 Q3 qp p4
    "QP p4 区域：题号 3 + 'Answer Question 3(a) or Question 3(b).' + 'Write 130–140 words.' + (a) A day trip 全块（引入语 + 5 条 bullet + [28]）+ OR + (b) Charity work 全块（引入语 + 5 条 bullet + [28]）+ 答题线 + 页脚 © UCLES 2025 0472/42/M/J/25；无下一题混入。",
    # 4 Q3(a) qp p4
    "QP p4 子区域：(a) 'A day trip' 标题 + 引入语 'You recently went on a day trip. Write an email to your friend about this.' + 5 条 bullet（Explain why you decided to go on a day trip / Describe the place you visited on the day trip / Say how you travelled to this place / Explain whether or not you think it is important to visit different places / Say where you plan to go on your next day trip and why.）+ [28]（y219.6-230.2 x521.7-539.0）+ 底边含 OR 分隔行；未混入 (b) 内容。",
    # 5 Q3(b) qp p4
    "QP p4 子区域：(b) 'Charity work' 标题 + 引入语 'You have started working as a volunteer at a local charity shop. Write an article for your school magazine.' + 5 条 bullet（Say when you started working at the charity shop. / Explain why you started working at the charity shop / Describe what you do to help at the charity shop / Explain whether or not you think it is important for young people to give up their time to help others / Say what other charity work you might like to do in the future）+ [28]（y488.6-499.2 x521.7-539.0）+ 答题线 + 页脚 © UCLES 2025 0472/42/M/J/25；未混入 (a) 内容。",
    # 6 M1 ms p6
    "MS p6 区域：题号 1 行 + 'You are Sarah Johnson. Your school is planning a cooking competition and you would like to take part, Complete the form.' + Expected 表（Gap 1 'What to cook' 1 分 / Gap 2 'How long it will take' 1 分 / Gap 3i 'How often you cook' 1 分 / Gap 3ii 'Why you enjoy cooking' 1 分 / Gap 3iii 'What you find difficult about cooking' 1 分）+ 右侧总分 5；顶部为内容首行，底部无下一题混入。",
    # 7 M2 ms p7
    "MS p7 区域：题号 2 行 + 'School library' + 要点 1–5（Describe your school library / How often do you use the school library? / What do you usually do in the school library? / What do you like most about the school library? / How could the school improve the library in the future??）+ 'Write 80–90 words in English.' + 'Read the whole answer and award a mark out of 12 using the table below.' + 右侧 12；无下一题混入。",
    # 8 M2 ms p8
    "MS p8 区域：'Marks | Descriptor' 表（10–12 Band 5 / 7–9 Band 4 / 4–6 Band 3 / 1–3 Band 2 / 0 Band 1 'No creditable content.'）完整；无下一题混入。",
    # 9 M3 ms p9
    "MS p9 区域：指令行 'Answer Question 3(a) or Question 3(b). Write 130–140 words in English.' + 3(a) 块（'A day trip'、引入语、要点 1–5、'Read the whole answer, award a mark from each of the three tables below and add up the total. Marks are available for: task completion (maximum 10 marks) / range (maximum 10 marks) / accuracy (maximum 8 marks).'）+ OR + 3(b) 块（'Charity work'、引入语、要点 1–5、同 Read the whole answer…）；右侧各 28；无下一题混入。",
    # 10 M3 ms p10
    "MS p10 区域：'Task completion' 表（Marks | Descriptor 表头 + 9–10 Band 5 / 7–8 Band 4 / 5–6 Band 3 / 3–4 Band 2 / 1–2 Band 1 / 0 'No creditable response.'）完整；为 3/3(a)/3(b) 共用表；无下一题混入。",
    # 11 M3 ms p11
    "MS p11 区域：'Range' 表（Marks | Descriptor + 全部等级行）完整；为共用表；无下一题混入。",
    # 12 M3 ms p12
    "MS p12 区域：'Accuracy' 表（Marks | Descriptor + 全部等级行）完整；为共用表；无下一题混入。",
    # 13 M3(a) ms p9
    "MS p9 子区域（3(a) 行条带）：'3(a)' 标签 + 'A day trip' 块（引入语 'You recently went on a day trip. Write an email to your friend about this.'、要点 1–5、'Read the whole answer…' 三表说明）+ 右侧 28；未混入 3(b) 的 Charity work 块。",
    # 14 M3(a) ms p10
    "MS p10 区域（3(a) 与 3/3(b) 共用同一表区域）：'Task completion' 表完整（Marks | Descriptor + 全部等级行）。",
    # 15 M3(a) ms p11
    "MS p11 区域（共用）：'Range' 表完整（Marks | Descriptor + 全部等级行）。",
    # 16 M3(a) ms p12
    "MS p12 区域（共用）：'Accuracy' 表完整（Marks | Descriptor + 全部等级行）。",
    # 17 M3(b) ms p9
    "MS p9 子区域（3(b) 行条带）：'3(b)' 标签 + OR + 'Charity work' 块（引入语 'You have started working as a volunteer at a local charity shop. Write an article for your school magazine.'、要点 1–5、'Read the whole answer…'）+ 右侧 28；未混入 3(a) 的 A day trip 块。",
    # 18 M3(b) ms p10
    "MS p10 区域（共用）：'Task completion' 表完整。",
    # 19 M3(b) ms p11
    "MS p11 区域（共用）：'Range' 表完整。",
    # 20 M3(b) ms p12
    "MS p12 区域（共用）：'Accuracy' 表完整。",
]
assert len(OBS) == 20, len(OBS)

now = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%dT%H:%M:%S+0800")
records = []
for fr, (num, role, page, _b1, bbox_raw), observed in zip(frame_regions, expected, OBS):
    img = fr["img"]
    assert img.is_file(), img
    records.append({
        "key": "0472/2025/Jun/42",
        "question": num,
        "role": role,
        "page": page,
        "bbox": bbox_raw,
        "method": "local_image_visual",
        "checks": {"content_complete": True, "boundary_checked": True,
                   "role_matches": True, "observed": observed},
        "issues": [],
        "checked_at": now,
        "index_sha256": index_sha,
        "image": str(img),
        "image_sha256": hashlib.sha256(img.read_bytes()).hexdigest(),
        "verifier": "main_agent_root_visual",
    })

assert len(records) == 20, len(records)
assert sum(1 for r in records if r["role"] == "qp") == 5
assert sum(1 for r in records if r["role"] == "ms") == 15
assert len({(r["question"], r["role"], r["page"], tuple(r["bbox"])) for r in records}) == 20

with VERIF.open("a", encoding="utf-8") as fh:
    for r in records:
        fh.write(json.dumps(r, ensure_ascii=False) + "\n")

print(f"appended {len(records)} verification records (5 qp + 15 ms)")
print(f"index_sha256: {index_sha}")
print(f"checked_at: {now}")
