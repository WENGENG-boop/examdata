"""0472/2024/Jun/11: write verification.jsonl records for all 81 regions.

Regions were visually checked via viewer v=4 frames (26 frames, all passed):
- 44 qp regions (37 questions + 7 section-intro ctx regions)
- 37 ms regions (one per question)
Each record maps to the exact crop image shown in the viewer (stack-*.png).
"""
import hashlib
import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

BR = Path(r"C:/Users/weo/Desktop/api/cie-location-batch")
IDX = BR / "indexes/0472/2024-Jun-11/cie-index.json"
VERIF = BR / "verification.jsonl"
SHEETS = BR / "work/sheets"

index = json.loads(IDX.read_text(encoding="utf-8"))
index_sha = hashlib.sha256(IDX.read_bytes()).hexdigest()

# ---- parse stack HTMLs: (role, page, bbox) -> crop image path
cap_re = re.compile(r"<div class=cap>(.*?)</div><img src=\"([^\"]+)\"")
crop_map = {}
for f in sorted(SHEETS.glob("0472-2024-Jun-11-qp-regions-stack-*.html")) + \
         sorted(SHEETS.glob("0472-2024-Jun-11-msreg-stack-*.html")):
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
        crop_map[key] = (label, BR / src.lstrip("/").replace("/", "\\"))

print(f"parsed crops: {len(crop_map)}")

# ---- observations from visual check (frame log 0472-viewer-check.txt)
QP_OBS = {
    "1": "Q1 'You are in a supermarket with a friend... What does your friend want?' + A–D + [1]",
    "2": "Q2 'Where is your friend going?' + A–D + [1]",
    "3": "Q3 'What is cheaper than usual today?' + A–D + [1]",
    "4": "Q4 'What can customers try for free at the supermarket?' + A–D + [1]",
    "5": "Q5 'What time does the supermarket close?' (clock images 6:30/7:15/8:45/9:00) + A–D + [1]",
    "6": "Q6 'Where does your friend want to go after leaving the supermarket?' + A–D + [1]",
    "7": "Q7 'How much does your shopping cost?' (£8.30/£14.70/£22.60/£31.50) + A–D + [1]",
    "8": "Q8 'What is the weather like?' + A–D + [1]",
    "9": "Q9 'The new art course starts on: March/April/May/June' + A–D + [1]",
    "10": "Q10 'The topic of the first class is painting' + A–D + [1]",
    "11": "Q11 'The course includes a trip to' + A–D + [1]",
    "12": "Q12 'Students who are interested in doing the course should meet' + A–D + [1]",
    "13": "Q13 'Students should bring' + A–D + [1]",
    "14": "Q14 'At the end of the course, students get a free' + A–D + [1]",
    "15": "Q15 'now.com' answer line + [1]",
    "16": "Q16 'FR Events' answer line + [1]",
    "17": "Q17 'Real Life' answer line + [1]",
    "18": "Q18 'happening.net' answer line + [1]",
    "19": "Q19 'Up To Date' answer line + [1]",
    "20": "Q20 'How many times per year does Olga go on holiday now?' A once B twice C three times + [1]",
    "21": "Q21 'Olga usually spends her holiday' seaside/mountains/lake + [1]",
    "22": "Q22 'How does Olga usually travel when she goes on holiday?' car/plane/train + [1]",
    "23": "Q23 'How does Olga usually feel on the journey?' nervous/excited/tired + [1]",
    "24": "Q24 'In the future, Olga would like to go on holiday to' + [1]",
    "25": "Q25 'What does Aleksander enjoy most about his holiday?' + [1]",
    "26": "Q26 'Aleksander usually goes on holiday with' + [1]",
    "27": "Q27 'Aleksander usually goes on holiday for' + [1]",
    "28": "Q28 'What did Aleksander bring back from his last holiday as a souvenir?' + [1]",
    "29": "Q29 'Julia decided to start working at the café because' + A–D + [1]",
    "30": "Q30 'What mistake did Julia make on her first day of work?' + A–D + [1]",
    "31": "Q31 'What surprises Julia about some customers?' + A–D + [1]",
    "32": "Q32 'Julia says that the chef at the café is' + A–D + [1]",
    "33": "Q33 'During her breaks, Julia usually' + A–D + [1]",
    "34": "Q34 'What does Julia enjoy doing most at the café?' + A–D + [1]",
    "35": "Q35 A–E five statements (Morio Kawasaki) + [2]",
    "36": "Q36 A–E five statements + [2]",
    "37": "Q37 A–E five statements + [2]",
}
CTX_OBS = {
    "1": "Questions 1–8 节说明（short recordings 指示，3 行）完整",
    "9": "Questions 9–14 节说明（weekend art course announcement 指示）完整",
    "15": "Questions 15–19 节说明 + Information A–F + Website 标题完整",
    "20": "Questions 20–28 节说明 + Part 1 指示（Olga/Aleksander 访谈）完整",
    "25": "Part 2 指示（Aleksander 访谈）完整",
    "29": "Questions 29–34 节说明（Julia/Theo café 对话指示）完整",
    "35": "Questions 35–37 节说明（Morio Kawasaki 访谈、choose two A–E）完整",
}
MS_ANS = {"1": "C", "2": "A", "3": "B", "4": "D", "5": "D", "6": "A", "7": "B", "8": "C",
          "9": "C", "10": "A", "11": "B", "12": "B", "13": "A", "14": "D", "15": "F",
          "16": "C", "17": "A", "18": "E", "19": "B", "20": "C", "21": "A", "22": "B",
          "23": "C", "24": "C", "25": "B", "26": "A", "27": "C", "28": "B", "29": "B",
          "30": "D", "31": "B", "32": "A", "33": "C", "34": "A", "35": "D, E", "36": "B, E",
          "37": "A, D"}

now = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%dT%H:%M:%S+0800")
records = []
missing = []

for q in index["questions"]:
    num = q["question"]
    marks = q["marks"]
    for i, region in enumerate(q["qp"]):
        key = ("qp", region["page"], tuple(round(float(x), 1) for x in region["bbox"]))
        if key not in crop_map:
            missing.append((num, "qp", i))
            continue
        label, img = crop_map[key]
        is_ctx = (i == 0 and label == f"{num}-ctx")
        obs = CTX_OBS[num] if is_ctx else QP_OBS[num]
        if is_ctx:
            obs = f"[节说明区域] {obs}"
        else:
            obs = f"题号 {num}、题干、选项、分值齐全；边界无下一题混入。{obs}"
        records.append({
            "key": "0472/2024/Jun/11",
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
        label, img = crop_map[key]
        obs = (f"MS 行 {num}：答案 {MS_ANS[num]}；Marks {marks}。"
               f"整行完整（题号/答案/分值），无相邻行混入。")
        records.append({
            "key": "0472/2024/Jun/11",
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

with VERIF.open("a", encoding="utf-8") as fh:
    for r in records:
        fh.write(json.dumps(r, ensure_ascii=False) + "\n")

print(f"appended {len(records)} verification records (44 qp + 37 ms)")
print(f"index_sha256: {index_sha}")
