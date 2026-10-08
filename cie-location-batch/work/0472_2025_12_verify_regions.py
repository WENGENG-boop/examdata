"""0472/2025/Jun/12: write verification.jsonl records for all 81 regions.

Regions were re-verified visually in the browser (viewer frames c01-c16) after
the index fix; all 81 regions passed, and whole-paper page order (qp p1-p16,
ms p1-p3) was checked too.
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
IDX = BR / "indexes/0472/2025-Jun-12/cie-index.json"
VERIF = BR / "verification.jsonl"
SHEETS = BR / "work/sheets"

index = json.loads(IDX.read_text(encoding="utf-8"))
index_sha = hashlib.sha256(IDX.read_bytes()).hexdigest()
assert index_sha == "dd3755ab0d87c73c816fce9e08f583262fad206647af405b60b457da3c4cd04a", index_sha

# ---- parse viewer frames: (role, page, bbox) -> (label, crop image path)
cap_re = re.compile(r"<div class=cap>(.*?)</div><img src=\"([^\"]+)\"")
crop_map = {}
frames = sorted(SHEETS.glob("0472-2025-Jun-12-viewer-regions-c*.html"))
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
    "1": "Questions 1–8 节说明（short recordings，A–D）+ \"You are at a large cinema.\" 完整。",
    "9": "Questions 9–14 节说明（castle tour 公告，A–D）+ \"Castle tour\" 标题完整。",
    "15": "Questions 15–19 节说明（Sergio/Asha 音乐网站对话）+ Information A–F + \"Music website\" 表头完整。",
    "20": "Questions 20–28 节说明 + \"Part 1: Questions 20–24\"（Nino 访谈，A–C）完整。",
    "25": "\"Part 2: Questions 25–28\" 指示（Safiya 访谈，A–C）完整。",
    "29": "Questions 29–34 节说明（Harry 帆船课程对话，A–D）完整。",
    "35": "Questions 35–37 节说明（Donna Wellbeck 访谈）+ \"choose the two true statements (A–E)\" 指示完整。",
}
QP_OBS = {
    "1": "题干 \"Which film does your friend want to see?\" + 电影图 A–D + [1]",
    "2": "题干 \"What time does the film start?\" + 钟面图 A–D + [1]",
    "3": "题干 \"How much do your tickets cost?\" + 票价图（£11-00/£12-10/£13-20/£14-90）A–D + [1]",
    "4": "题干 \"What does your friend want to drink?\" + 饮料图 A–D + [1]",
    "5": "题干 \"Who is your friend going to ring?\" + 人脸图 A–D + [1]",
    "6": "题干 \"What did your friend forget in the cinema?\" + 物品图 A–D + [1]",
    "7": "题干 \"What does your friend need to buy?\" + 物品图 A–D + [1]",
    "8": "题干 \"What does your friend want to do with you this evening?\" + A–D + [1] + [Total: 8]",
    "9": "题干 \"Tourists can leave their bags in a room next to the …\" + A–D + [1]",
    "10": "题干 \"The first room the tour will visit is the …\" + A–D + [1]",
    "11": "题干 \"In the castle hall, tourists will be able to see …\" + A–D + [1] + [PAUSE]",
    "12": "题干 \"Tourists must not take photos of the …\" + A–D + [1]",
    "13": "题干 \"In the castle gardens, tourists will be able to see …\" + A–D + [1]",
    "14": "题干 \"In the gift shop today, there is a discount on …\" + A–D + [1] + [Total: 6]",
    "15": "\"15 SoundWeb\" 匹配行 + [1]",
    "16": "\"16 TopNote\" 匹配行 + [1]",
    "17": "\"17 ListenNow\" 匹配行 + [1]",
    "18": "\"18 SongShop\" 匹配行 + [1]",
    "19": "\"19 TuneBase\" 匹配行 + [1] + [Total: 5]",
    "20": "题干 \"How often does Nino go to his grandparents’ house?\" + A/B/C + [1]",
    "21": "题干 \"What does Nino say about going to the countryside with his family?\" + A/B/C + [1]",
    "22": "题干 \"When visiting the capital city, Nino enjoys spending his time …\" + A/B/C + [1]",
    "23": "题干 \"How does Nino’s family usually travel when they go on holiday?\" + A/B/C + [1]",
    "24": "题干 \"Nino prefers to spend his holiday …\" + A/B/C + [1] + [PAUSE]",
    "25": "题干 \"Why does Safiya enjoy visiting a local lake?\" + A/B/C + [1]",
    "26": "题干 \"Who does Safiya visit every week?\" + A/B/C + [1]",
    "27": "题干 \"What did Safiya do last weekend?\" + A/B/C + [1]",
    "28": "题干 \"In the future, Safiya would like to go to …\" + A/B/C + [1] + [Total: 9]",
    "29": "题干 \"What made Harry want to learn to sail?\" + A–D + [1]",
    "30": "题干 \"Harry says that the staff on the sailing course …\" + A–D + [1]",
    "31": "题干 \"During his first sailing lesson, Harry …\" + A–D + [1] + [PAUSE]",
    "32": "题干 \"What did Harry find most difficult about sailing?\" + A–D + [1]",
    "33": "题干 \"During break times on the course, Harry usually …\" + A–D + [1]",
    "34": "题干 \"Harry celebrated passing the course by …\" + A–D + [1] + [Total: 6]",
    "35": "A–E 五陈述（Donna Wellbeck 相关）+ [2] + [PAUSE]",
    "36": "A–E 五陈述 + [2] + [PAUSE]",
    "37": "A–E 五陈述 + [2] + [Total: 6]（尾部含答卷抄写时间指令，无下一题）",
}
MS_ANS = {"1": "D", "2": "B", "3": "C", "4": "A", "5": "B", "6": "A", "7": "D", "8": "C",
          "9": "B", "10": "C", "11": "D", "12": "A", "13": "B", "14": "C", "15": "E",
          "16": "A", "17": "F", "18": "C", "19": "D", "20": "C", "21": "B", "22": "A",
          "23": "B", "24": "A", "25": "C", "26": "A", "27": "B", "28": "C", "29": "B",
          "30": "D", "31": "A", "32": "C", "33": "B", "34": "A",
          "35": "A / C", "36": "B / D", "37": "A / E"}
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
            "key": "0472/2025/Jun/12",
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
            "key": "0472/2025/Jun/12",
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
