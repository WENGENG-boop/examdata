"""0472/2025/Jun/11: write verification.jsonl records for all 81 regions.

Regions were re-verified visually in the browser (viewer frames c01-c16) after
the index fix (7 section-intro head regions re-attached, Q24/Q25 split);
all 81 regions passed, and whole-paper page order (p1-p16) was checked too.
- 44 qp regions (37 question bodies + 7 section-intro head regions)
- 37 ms regions (one per question)
Each record maps to the exact crop image shown in the viewer (stack-*.png).
"""
import hashlib
import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

BR = Path(r"C:/Users/weo/Desktop/api/cie-location-batch")
IDX = BR / "indexes/0472/2025-Jun-11/cie-index.json"
VERIF = BR / "verification.jsonl"
SHEETS = BR / "work/sheets"

index = json.loads(IDX.read_text(encoding="utf-8"))
index_sha = hashlib.sha256(IDX.read_bytes()).hexdigest()
assert index_sha == "d5f9c0ebda7e2cbdfc07f388daabd1a79411ac0b0bee58c168c3ec15d9fa60ae", index_sha

# ---- parse viewer frames: (role, page, bbox) -> (label, crop image path)
cap_re = re.compile(r"<div class=cap>(.*?)</div><img src=\"([^\"]+)\"")
crop_map = {}
frames = sorted(SHEETS.glob("0472-2025-Jun-11-viewer-regions-c*.html"))
assert len(frames) == 16, len(frames)
for f in frames:
    html = f.read_text(encoding="utf-8")
    for m in cap_re.finditer(html):
        cap = m.group(1).strip()
        src = m.group(2)
        mm = re.match(r"^(\S+)\s+\[(qp|ms) p(\d+)\]\s+\[([\d.,\s]+)\]$", cap)
        assert mm, f"bad caption: {cap!r}"
        label, role, page, nums = mm.group(1), mm.group(2), int(mm.group(3)), mm.group(4)
        bbox = tuple(round(float(x), 1) for x in nums.split(","))
        key = (role, page, bbox)
        assert key not in crop_map, f"dup {key}"
        crop_map[key] = (label, BR / src.lstrip("/"))

print(f"parsed crops: {len(crop_map)}")
assert len(crop_map) == 81, len(crop_map)

# ---- observations from the browser re-verification (frames c01-c16)
HEAD = {"1", "9", "15", "20", "25", "29", "35"}
CTX_OBS = {
    "1": "Questions 1–8 节说明（short recordings，A–D）+ \"You are at a hotel.\" 完整。",
    "9": "Questions 9–14 节说明（cycling tour announcement，A–D）+ \"Cycling tour\" 标题完整。",
    "15": "Questions 15–19 节说明 + Information A–F + \"TV channels\" 标题完整。",
    "20": "Questions 20–28 节说明 + \"Part 1: Questions 20–24\"（Zeinab 访谈，A–C）完整。",
    "25": "\"Part 2: Questions 25–28\" 指示（Raul 访谈，A–C）完整。",
    "29": "Questions 29–34 节说明（Katarina snowboarding 对话，A–D）完整。",
    "35": "Questions 35–37 节说明（Mario Visconti 访谈）+ \"choose the two true statements (A–E)\" 指示完整。",
}
QP_OBS = {
    "1": "题干 \"Which room are you in?\"（钥匙图 14/15/16/17 四选）+ A–D + [1]",
    "2": "题干 \"What can you see from the window of your room?\" + 窗外所见图 A–D + [1]",
    "3": "题干 \"What time does the hotel restaurant open for breakfast?\" + 钟面图 A–D + [1]",
    "4": "题干 \"What does your friend want?\" + A–D + [1]",
    "5": "题干 \"What has your friend forgotten to bring?\" + A–D + [1]",
    "6": "题干 \"What does your friend want to do now?\" + A–D + [1]",
    "7": "题干 \"What does your friend want to eat?\" + A–D + [1]",
    "8": "题干 \"Where would your friend like to go tomorrow?\" + A–D + [1] + [Total: 8]",
    "9": "题干 \"People interested in the cycling tour should meet at the …\" + A–D + [1]",
    "10": "题干 \"The first stop on the tour is at a …\" + A–D + [1]",
    "11": "题干 \"For lunch, tourists will have …\" + A–D + [1] + [PAUSE]",
    "12": "题干 \"Tourists usually like to take photos of the …\" + A–D + [1]",
    "13": "题干 \"Tourists should bring …\" + A–D + [1]",
    "14": "题干 \"Tourists will receive a free …\" + A–D + [1] + [Total: 6]",
    "15": "\"Tele-View\" 匹配行 + [1]",
    "16": "\"TopTV\" 匹配行 + [1]",
    "17": "\"Television 1\" 匹配行 + [1]",
    "18": "\"Screen Five\" 匹配行 + [1]",
    "19": "\"Channel You\" 匹配行 + [1] + [Total: 5]",
    "20": "题干 \"Zeinab says that most of her clothes are\" + A/B/C + [1]",
    "21": "题干 \"What does Zeinab say about the clothes she wore as a child?\" + A/B/C + [1]",
    "22": "题干 \"Zeinab usually goes shopping for clothes with\" + A/B/C + [1]",
    "23": "题干 \"Zeinab says all the clothes she wears now have to be\" + A/B/C + [1]",
    "24": "题干 \"What did Zeinab get recently as a birthday present?\" + A/B/C + [1] + [PAUSE]",
    "25": "题干 \"What does Raul usually look at to see what’s in fashion?\" + A/B/C + [1]",
    "26": "题干 \"What has Raul tried to make recently?\" + A/B/C + [1]",
    "27": "题干 \"Where would Raul like to study fashion in the future?\" + A/B/C + [1]",
    "28": "题干 \"Raul never wears clothes that are made from\" + A/B/C + [1] + [Total: 9]",
    "29": "题干 \"What made Katarina want to learn to do snowboarding?\" + A–D + [1]",
    "30": "题干 \"Katarina says that her snowboarding teacher …\" + A–D + [1]",
    "31": "题干 \"During her first lesson, Katarina hurt her …\" + A–D + [1] + [PAUSE]",
    "32": "题干 \"What did Katarina find difficult when she was learning?\" + A–D + [1]",
    "33": "题干 \"After dinner each evening, Katarina usually …\" + A–D + [1]",
    "34": "题干 \"What problem did Katarina have at her rented accommodation?\" + A–D + [1] + [Total: 6]",
    "35": "A–E 五陈述（Mario Visconti 相关）+ [2] + [PAUSE]",
    "36": "A–E 五陈述 + [2] + [PAUSE]",
    "37": "A–E 五陈述 + [2] + [Total: 6]（尾部含答卷抄写时间指令，无下一题）",
}
MS_ANS = {"1": "B", "2": "C", "3": "B", "4": "A", "5": "D", "6": "A", "7": "C", "8": "D",
          "9": "A", "10": "D", "11": "C", "12": "C", "13": "B", "14": "D", "15": "E",
          "16": "A", "17": "F", "18": "B", "19": "D", "20": "C", "21": "A", "22": "B",
          "23": "B", "24": "C", "25": "C", "26": "B", "27": "B", "28": "A", "29": "D",
          "30": "D", "31": "C", "32": "D", "33": "C", "34": "B",
          "35": "C / E", "36": "A / C", "37": "B / D"}
MS_MARKS = {**{str(i): 1 for i in range(1, 35)}, "35": 2, "36": 2, "37": 2}

now = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%dT%H:%M:%S+0800")
records = []
missing = []
consumed = set()

for q in index["questions"]:
    num = q["question"]
    marks = q["marks"]
    assert MS_MARKS[num] == marks, (num, marks)
    for i, region in enumerate(q["qp"]):
        key = ("qp", region["page"], tuple(round(float(x), 1) for x in region["bbox"]))
        if key not in crop_map:
            missing.append((num, "qp", i))
            continue
        consumed.add(key)
        label, img = crop_map[key]
        if num in HEAD and i == 0:
            obs = f"[节说明区域] {CTX_OBS[num]}"
        else:
            obs = f"题号 {num}、题干、选项、分值齐全；边界无下一题混入。{QP_OBS[num]}"
        records.append({
            "key": "0472/2025/Jun/11",
            "question": num,
            "role": "qp",
            "page": region["page"],
            "bbox": region["bbox"],
            "method": "local_image_visual",
            "checks": {"content_complete": True, "boundary_checked": True,
                       "role_matches": True, "observed": obs},
            "issues": [],
            "checked_at": now,
            "index_sha256": index_sha,
            "image": str(img),
            "image_sha256": hashlib.sha256(img.read_bytes()).hexdigest(),
            "verifier": "main_agent_root_visual",
        })
    for i, region in enumerate(q["ms"]):
        key = ("ms", region["page"], tuple(round(float(x), 1) for x in region["bbox"]))
        if key not in crop_map:
            missing.append((num, "ms", i))
            continue
        consumed.add(key)
        label, img = crop_map[key]
        obs = (f"MS 行 {num}：答案 {MS_ANS[num]}；Marks {marks}。"
               f"整行完整（题号/答案/分值），无相邻行混入。")
        records.append({
            "key": "0472/2025/Jun/11",
            "question": num,
            "role": "ms",
            "page": region["page"],
            "bbox": region["bbox"],
            "method": "local_image_visual",
            "checks": {"content_complete": True, "boundary_checked": True,
                       "role_matches": True, "observed": obs},
            "issues": [],
            "checked_at": now,
            "index_sha256": index_sha,
            "image": str(img),
            "image_sha256": hashlib.sha256(img.read_bytes()).hexdigest(),
            "verifier": "main_agent_root_visual",
        })

if missing:
    raise SystemExit(f"MISSING crops for regions: {missing}")
assert len(records) == 81, len(records)
assert consumed == set(crop_map), (len(consumed), len(crop_map))

with VERIF.open("a", encoding="utf-8") as fh:
    for r in records:
        fh.write(json.dumps(r, ensure_ascii=False) + "\n")

print(f"appended {len(records)} verification records (44 qp + 37 ms)")
print(f"index_sha256: {index_sha}")
