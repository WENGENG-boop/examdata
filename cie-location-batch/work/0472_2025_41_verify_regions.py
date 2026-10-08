"""0472/2025/Jun/41: write verification.jsonl records for all 20 regions.

The index was fixed (ms bounds widened to [x0, 56.0, x1, 730.0], two stray
strips removed, shared-table notes added for Q3/Q3(a)/Q3(b)); current sha
aba160178b183ae9770f981e7af96ca4205327929c23b1ee4e71f02a088263e4.
Viewer frames were rebuilt from the fixed index: 5 qp-regions-stack frames
(Q1,Q2,Q3,Q3(a),Q3(b)) + 9 msreg-stack frames covering 15 ms regions.
All 19 frames were verified visually in the browser; this script maps each
of the 20 regions 1:1 to the exact crop image shown (stack-*.png) in frame
order (all qp first, then all ms), never by a keyed lookup, and appends one
verification record per region.
"""
import hashlib
import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

BR = Path(r"C:/Users/weo/Desktop/api/cie-location-batch")
IDX = BR / "indexes/0472/2025-Jun-41/cie-index.json"
VERIF = BR / "verification.jsonl"
SHEETS = BR / "work/sheets"

index = json.loads(IDX.read_text(encoding="utf-8"))
index_sha = hashlib.sha256(IDX.read_bytes()).hexdigest()
assert index_sha == "aba160178b183ae9770f981e7af96ca4205327929c23b1ee4e71f02a088263e4", index_sha

# ---- parse viewer frames in order: (label, role, page, bbox) + crop image
cap_re = re.compile(r"<div class=cap>(.*?)</div><img src=\"([^\"]+)\"")
frame_regions = []
frames = (sorted(SHEETS.glob("0472-2025-Jun-41-qp-regions-stack-*.html"))
          + sorted(SHEETS.glob("0472-2025-Jun-41-msreg-stack-*.html")))
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

# ---- expected order from the fixed index: all qp (question order), then all ms
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
    "QP p2 区域：题号 1 + 'You are Maria Lopez. You are taking part in a music competition at your school and you need to use the school music room to practise. Complete this booking form.' + booking form 表（Name | Maria Lopez；The day you want to use the music room each week | 答题虚线；The musical instrument you play | 答题虚线）+ 'Now give more information about the musical instrument you play.' + 'Write about:' 三条（why you like playing this instrument / how often you practise this instrument / how long you have played this instrument.）+ 'Write 20–30 words.' + 答题虚线四条 + [5]；页脚 © UCLES 2025 0472/41/M/J/25；无下一题混入。",
    # 2 Q2 qp p3
    "QP p3 区域：题号 2 + 'Favourite place' + 四条 bullet（Describe your favourite place. / Why is this your favourite place? / When do you most like to go to this place? / Who will you take with you when you next visit this place? Explain why.）+ 'Write 80–90 words.' + 答题虚线 + [12]（右下）；页脚 © UCLES 2025 0472/41/M/J/25 [Turn over；无下一题混入。",
    # 3 Q3 qp p4
    "QP p4 区域：题号 3 + 'Answer Question 3(a) or Question 3(b). Write 130–140 words.' + (a) Taking photographs 全块（引入语 + 5 条 bullet + [28]）+ OR + (b) Gifts 全块（引入语 + 5 条 bullet + [28]）+ 答题虚线 + 页脚 © UCLES 2025 0472/41/M/J/25；无下一题混入。",
    # 4 Q3(a) qp p4
    "QP p4 子区域：(a) 'Taking photographs' 标题 + 引入语 'An international website wants articles about the photographs teenagers take. Write an article about the photographs you take.' + 5 条 bullet（Say what type of photographs you most like to take. / Explain why you like taking these types of photographs. / Describe the last photograph you took. / Explain why you think many young people take a lot of photographs. / Say whether you think the photographs you take will be important for people in the future.）+ [28] + 底边含 OR 分隔行；未混入 (b) 内容。",
    # 5 Q3(b) qp p4
    "QP p4 子区域：(b) 'Gifts' 标题 + 引入语 'Somebody recently bought you a gift. Write an email to your friend to tell them about it.' + 5 条 bullet（Describe the gift you received. / Say who gave you this gift and why. / Describe how you felt about the gift. / Say what you are going to do with the gift. / Explain whether you prefer to receive money or a particular gift.）+ [28] + 答题虚线 + 页脚 © UCLES 2025 0472/41/M/J/25；未混入 (a) 内容。",
    # 6 M1 ms p6
    "MS p6 区域：题号 1 行 + Expected 表（Gap 1 'The day you want to use the music room each week.' 1 分 / Gap 2 'The musical instrument you play' 1 分 / Gap 3(i) 'Why you like playing this instrument' 1 分 / Gap 3(ii) 'How often you practise this instrument' 1 分 / Gap 3(iii) 'How long you have played this instrument' 1 分）+ 右侧总分 5；顶部为内容首行（不含通用表头），底部无下一题混入。",
    # 7 M2 ms p7
    "MS p7 区域：题号 2 行 + 'Favourite place' + 要点 1–5（Describe your favourite place. / Why is this your favourite place? / When do you most like to go to this place? / Who will you take with you when you next visit this place? / Explain why?）+ 'Write 80–90 words in English.' + 'Read the whole answer and award a mark out of 12 using the table below.' + 右侧 12；无下一题混入。",
    # 8 M2 ms p8
    "MS p8 区域：'Marks | Descriptor' 表头 + 全部等级行（10–12 Band 5 / 7–9 Band 4 / 4–6 Band 3 / 1–3 Band 2 / 0 Band 1 'No creditable content.'）完整；无下一题混入。",
    # 9 M3 ms p9
    "MS p9 区域：指令行 'Answer Question 3(a) or Question 3(b). Write 130–140 words in English.' + 3(a) 块（'Taking photographs'、引入语、要点 1–5、'Read the whole answer, award a mark from each of the three tables below and add up the total. Marks are available for: task completion (maximum 10 marks) / range (maximum 10 marks) / accuracy (maximum 8 marks).'）+ OR + 3(b) 块（'Gifts'、引入语、要点 1–5、同 Read the whole answer…）；右侧各 28；无下一题混入。",
    # 10 M3 ms p10
    "MS p10 区域：'Task completion' 表（Marks | Descriptor 表头 + 9–10 Band 5 / 7–8 Band 4 / 5–6 Band 3 / 3–4 Band 2 / 1–2 Band 1 / 0 'No creditable response.'）完整；为 3(a)/3(b) 共用表；无下一题混入。",
    # 11 M3 ms p11
    "MS p11 区域：'Range' 表（Marks | Descriptor 表头 + 全部等级行）完整；为 3(a)/3(b) 共用表；无下一题混入。",
    # 12 M3 ms p12
    "MS p12 区域：'Accuracy' 表（Marks | Descriptor 表头 + 全部等级行）完整；为 3(a)/3(b) 共用表；无下一题混入。",
    # 13 M3(a) ms p9
    "MS p9 子区域（3(a) 行条带）：'3(a)' 标签 + 'Taking photographs' 块（引入语、要点 1–5、'Read the whole answer…' task completion (maximum 10 marks) / range (maximum 10 marks) / accuracy (maximum 8 marks).）+ 右侧 28；未混入 3(b) 的 Gifts 块。",
    # 14 M3(a) ms p10
    "MS p10 区域（3(a) 与 3(b) 共用同一表区域）：'Task completion' 表完整（Marks | Descriptor + 全部等级行）。",
    # 15 M3(a) ms p11
    "MS p11 区域（3(a) 与 3(b) 共用同一表区域）：'Range' 表完整（Marks | Descriptor + 全部等级行）。",
    # 16 M3(a) ms p12
    "MS p12 区域（3(a) 与 3(b) 共用同一表区域）：'Accuracy' 表完整（Marks | Descriptor + 全部等级行）。",
    # 17 M3(b) ms p9
    "MS p9 子区域（3(b) 行条带）：'3(b)' 标签 + OR + 'Gifts' 块（引入语、要点 1–5、'Read the whole answer…'）+ 右侧 28；未混入 3(a) 的 Taking photographs 块。",
    # 18 M3(b) ms p10
    "MS p10 区域（3(b) 与 3(a) 共用同一表区域）：'Task completion' 表完整（Marks | Descriptor + 全部等级行）。",
    # 19 M3(b) ms p11
    "MS p11 区域（3(b) 与 3(a) 共用同一表区域）：'Range' 表完整（Marks | Descriptor + 全部等级行）。",
    # 20 M3(b) ms p12
    "MS p12 区域（3(b) 与 3(a) 共用同一表区域）：'Accuracy' 表完整（Marks | Descriptor + 全部等级行）。",
]
assert len(OBS) == 20, len(OBS)

now = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%dT%H:%M:%S+0800")
records = []
for fr, (num, role, page, _b1, bbox_raw), observed in zip(frame_regions, expected, OBS):
    img = fr["img"]
    assert img.is_file(), img
    records.append({
        "key": "0472/2025/Jun/41",
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
