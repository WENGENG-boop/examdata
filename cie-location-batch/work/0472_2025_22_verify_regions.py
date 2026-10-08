"""0472/2025/Jun/22: write verification.jsonl records for all 102 regions.

All 102 regions (54 qp + 48 ms) were re-verified visually in the browser after
the index fixes (fix1: x0/x1/ms bounds + 5(a)-(e) insertion; fix2: Q3 p7 top
71.2 -> 58.6). Viewer frames c01-c27 were rebuilt from the fixed index
(current sha c5789fc260de55b7a2e98c0d370911f2bbdf3c815fb80408aec61174daa85f50),
and c10 was re-checked after fix2 (top now contains the "(d)" label).
Q1 p3 and Q1(c) p3 share the same bbox on p3, so frames are matched to index
regions by ordered traversal (never by a keyed dict). Each record maps 1:1 to
the exact crop image shown in the viewer (stack-*.png).
"""
import hashlib
import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

BR = Path(r"C:/Users/weo/Desktop/api/cie-location-batch")
IDX = BR / "indexes/0472/2025-Jun-22/cie-index.json"
VERIF = BR / "verification.jsonl"
SHEETS = BR / "work/sheets"

index = json.loads(IDX.read_text(encoding="utf-8"))
index_sha = hashlib.sha256(IDX.read_bytes()).hexdigest()
assert index_sha == "c5789fc260de55b7a2e98c0d370911f2bbdf3c815fb80408aec61174daa85f50", index_sha

# ---- parse viewer frames in order: (label, role, page, bbox) + crop image
cap_re = re.compile(r"<div class=cap>(.*?)</div><img src=\"([^\"]+)\"")
frame_regions = []
frames = sorted(SHEETS.glob("0472-2025-Jun-22-viewer-regions-c*.html"))
assert len(frames) == 27, len(frames)
for f in frames:
    html = f.read_text(encoding="utf-8")
    for m in cap_re.finditer(html):
        cap, src = m.group(1).strip(), m.group(2)
        mm = re.match(r"^(\S+)\s+\[(qp|ms) p(\d+)\]\s+\[([\d.,\s]+)\]$", cap)
        assert mm, f"bad caption: {cap!r}"
        label, role, page, nums = mm.group(1), mm.group(2), int(mm.group(3)), mm.group(4)
        bbox = tuple(round(float(x), 1) for x in nums.split(","))
        frame_regions.append({"frame": f.name.split("regions-")[1][:3], "label": label,
                              "role": role, "page": page, "bbox": bbox,
                              "img": BR / src.lstrip("/")})
print(f"parsed frame regions: {len(frame_regions)}")
assert len(frame_regions) == 102, len(frame_regions)

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
assert len(expected) == 102, len(expected)

for fr, (num, role, page, bbox1, bbox_raw) in zip(frame_regions, expected):
    assert fr["role"] == role and fr["page"] == page and fr["bbox"] == bbox1, \
        (fr, num, role, page, bbox1)
    want = ("Q" if role == "qp" else "M") + num
    assert fr["label"] == want, (fr["label"], want)
print("ordered 1:1 match with index: OK")

# ---- observations from the browser re-verification (frames c01-c27)
QP_OBS = {
    "1": ["p2 区域：题号 1 + 指示 'Read the texts. For each question, tick (✓) the correct box (A–D).'；(a) Mr Lim 邮件（To: Class 7 / Subject: Castle Trip）：'Don't worry about sandwiches as we'll give you packed lunches. But because there's a quiz with lots of questions, you'll need a pen. The cold weather has gone, so T-shirts are fine. Mr Lim' + 'Mr Lim's email tells students to' A bring something for lunch. B have something to write with. C think of some questions to ask. D wear some warm clothes. [1]；(b) 'Eastwater Park: Visitor Information' 告示（To keep everyone safe…Maps are available in the visitor centre.）+ 'The notice tells visitors' A where the paths in the park go. B where people can join guided walks. C which paths are used for different activities. D which are the easiest paths for walking. [1]；无下一题。",
          "p3 延展区：(c) 手机消息框 'Hi Alexei / I've chosen a film for us to watch tonight, and dad's making his special pasta – everyone loves it! / Have you played Planet-R? We can if you want to, if we're not tired after the film. / Tomas' + 'Tomas is texting Alexei to' A check what food he likes. B describe what they'll watch later. C ask him to bring a game. D explain the plan for the evening. [1] [Total: 3]；页下方空白；无下一题。"],
    "1(a)": ["(a) 标签 + Mr Lim 邮件（To: Class 7 / Subject: Castle Trip）+ 'Mr Lim's email tells students to' A–D + [1]；下边界止于 (b) 前；无下一题混入。"],
    "1(b)": ["(b) 标签 + 'Eastwater Park: Visitor Information' 告示 + 'The notice tells visitors' A–D + [1] + 页脚；无下一题混入。"],
    "1(c)": ["与父题 p3 同范围（同 bbox）：(c) 标签 + 手机消息框（Tomas/Alexei）+ 'Tomas is texting Alexei to' A–D + [1] + [Total: 3]；下方空白；无下一题混入。"],
    "2": ["p4 区域：题号 2 + 'Read the email. For each question, tick (✓) the correct box (A–C).' + Mark 邮件（To: Franz / Subject: geography project 全文）+ (a) Mark wants to meet on … A Monday. B Wednesday. C Friday. [1]；(b) Where does Mark suggest they should go? A Mark's house. B the library. C a café. [1]；无下一题。",
          "p5 延展区：(c) What does Mark want to put in the project? A a model. B some photos. C a video. [1]；(d) What does Mark still have a problem with? A his phone. B his laptop. C his printer. [1]；(e) The project needs to be at least … A 600 words long. B 700 words long. C 950 words long. [1]；(f) Who does Mark say they could ask for help with the project? A his sister. B his uncle. C his cousin. [1]；(g) What colour paper does Mark want to use? A green. B white. C black. [1] [Total: 7]；页脚+[Turn over；无下一题。"],
    "2(a)": ["(a) Mark wants to meet on … A Monday / B Wednesday / C Friday [1]；无下一题混入。"],
    "2(b)": ["(b) Where does Mark suggest they should go? A Mark's house / B the library / C a café [1] + 页脚；无下一题混入。"],
    "2(c)": ["(c) What does Mark want to put in the project? A a model / B some photos / C a video [1]；无下一题混入。"],
    "2(d)": ["(d) What does Mark still have a problem with? A his phone / B his laptop / C his printer [1]；无下一题混入。"],
    "2(e)": ["(e) The project needs to be at least … A 600 words long / B 700 words long / C 950 words long [1]；无下一题混入。"],
    "2(f)": ["(f) Who does Mark say they could ask for help with the project? A his sister / B his uncle / C his cousin [1]；无下一题混入。"],
    "2(g)": ["(g) What colour paper does Mark want to use? A green / B white / C black [1] [Total: 7] + 页脚 + [Turn over；无下一题混入。"],
    "3": ["p6 区域：题号 3 + 指示 'Read the text, and choose the correct word to fill the gaps (a) to (g). For each question, tick (✓) the correct box (A–D).' + Goldfish 正文（含 (a)–(g) 空）；(a) type/variety/sort/example [1]；(b) Absolutely/Instead/However/Despite [1]；(c) certain/accurate/realistic/possible [1]；页脚；无下一题。",
          "p7 延展区（修复后 [70.4,58.6,542.4,761.6]）：顶部含 (d) 题号；(d) although/whether/unless/after [1]、(e) agrees/depends/carries/holds [1]、(f) still/yet/even/only [1]、(g) unlucky/unusual/unknown/unnecessary [1] [Total: 7] + 页脚 [Turn over]；无下一题混入。"],
    "3(a)": ["(a) 选项组 A–D（type / variety / sort / example）[1]；无下一题混入。"],
    "3(b)": ["(b) 选项组 A–D（Absolutely / Instead / However / Despite）[1]；无下一题混入。"],
    "3(c)": ["(c) 选项组 A–D（certain / accurate / realistic / possible）[1] + 页脚；无下一题混入。"],
    "3(d)": ["(d) 选项组 A–D（although / whether / unless / after）[1]，含 '(d)' 标签；无下一题混入。"],
    "3(e)": ["(e) 选项组 A–D（agrees / depends / carries / holds）[1]；无下一题混入。"],
    "3(f)": ["(f) 选项组 A–D（still / yet / even / only）[1]；无下一题混入。"],
    "3(g)": ["(g) 选项组 A–D（unlucky / unusual / unknown / unnecessary）[1] [Total: 7]；无下一题混入。"],
    "4": ["p8 区域：题号 4 + 'Read the email, and answer the questions (a–k).' + 邮件 To: Leanna / Subject: New Market（Dad and I recently visited a new market…Carrie xx 全文）+ (a) How did Carrie and her dad travel to the market? [1]；(b) What does Carrie say you can see outside the entrance to the market? [1]；(c) Why did Carrie buy some jewellery? [1]；页脚 © UCLES 2025 0472/22/M/J/25；无下一题。",
          "p9 延展区：(d) Which types of music did Carrie enjoy listening to at the market? Give two details. (i)(ii) [2]；(e) What did Carrie and her dad have for lunch? [1]；(f) What did they do straight after lunch? [1]；(g) What was the problem with the skirt Carrie liked? [1]；(h) Why did Carrie's dad want to buy some fruit? [1]；(i) How much did Carrie spend on books? [1]；(j) How long were Carrie and her dad at the market? [1]；(k) When does Carrie suggest she and her friend should visit the market? [1] [Total: 12]；无下一题。"],
    "4(a)": ["(a) How did Carrie and her dad travel to the market?（答案虚线）[1]；无下一题混入。"],
    "4(b)": ["(b) What does Carrie say you can see outside the entrance to the market?（答案虚线）[1]；无下一题混入。"],
    "4(c)": ["(c) Why did Carrie buy some jewellery?（答案虚线）[1] + 页脚；无下一题混入。"],
    "4(d)": ["(d) Which types of music did Carrie enjoy listening to at the market? Give two details. (i)(ii) [2]；无下一题混入。"],
    "4(e)": ["(e) What did Carrie and her dad have for lunch?（答案虚线）[1]；无下一题混入。"],
    "4(f)": ["(f) What did they do straight after lunch?（答案虚线）[1]；无下一题混入。"],
    "4(g)": ["(g) What was the problem with the skirt Carrie liked?（答案虚线）[1]；无下一题混入。"],
    "4(h)": ["(h) Why did Carrie's dad want to buy some fruit?（答案虚线）[1]；无下一题混入。"],
    "4(i)": ["(i) How much did Carrie spend on books?（答案虚线）[1]；无下一题混入。"],
    "4(j)": ["(j) How long were Carrie and her dad at the market?（答案虚线）[1]；无下一题混入。"],
    "4(k)": ["(k) When does Carrie suggest she and her friend should visit the market?（答案虚线）[1] [Total: 12] + 页脚 [Turn over；无下一题。"],
    "5": ["p10 区域：题号 5 + 指示（five people (a–e) 与八个海滩描述 1–8 匹配；'Which beach should each person choose?'；'For each person (a–e), write the correct number (1–8) on the line.'）+ 'Local Beaches' 标题 + 五人描述（a Betty / b Mo / c Mei / d Faisal / e Stella）；页脚；无下一题。",
          "p11 延展区：描述 1 Falton Sands / 2 Lowry Beach / 3 Dursey Beach / 4 Otley Sands / 5 Sunshine Coast / 6 Watersmeet Bay / 7 Penston Beach / 8 Lulcombe Cove；[5]；页脚 [Turn over；无下一题。"],
    "5(a)": ["(a) Betty 描述段落及作答区（swim see beautiful fish / beach umbrella / not by car）；无下一题混入。"],
    "5(b)": ["(b) Mo 描述段落及作答区（cook food / grandmother easy access / local animals）；无下一题混入。"],
    "5(c)": ["(c) Mei 描述段落及作答区（parking / snacks / sailing lesson）；无下一题混入。"],
    "5(d)": ["(d) Faisal 描述段落及作答区（beach ball / sports competition / swimming area for sister）；无下一题混入。"],
    "5(e)": ["(e) Stella 描述段落及作答区（not crowded / sports equipment / organised activities for brother）；无下一题混入。"],
    "6": ["p12 区域：题号 6 + 'Read the blog, and answer the questions (a–i).' + 'Teen Drama': a theatre group for teens / A blog by Ayesha Siddiqui（5 段全文）+ (a) Who recommended the Teen Drama group to Ayesha? [1]；(b) How did Ayesha contact the drama group organiser? [1]；(c) How did she feel before the first drama group session? [1]；(d) What did she find most difficult at first about performing? [1]；页脚；无下一题。",
          "p13 延展区：(e) Why does she listen to music after a performance? [1]；(f) Which type of plays does she like performing in the most? [1]；(g) How is she helping with the preparations for the play Blue Skies? Give two details. (i)(ii)[2]；(h) What is the problem with the clothes she has to wear in Blue Skies? [1]；(i) What have the students decided to buy to thank Sandy? Give two details. (i)(ii)[2] [Total: 11]；无下一题。"],
    "6(a)": ["(a) Who recommended the Teen Drama group to Ayesha?（答案虚线）[1]；无下一题混入。"],
    "6(b)": ["(b) How did Ayesha contact the drama group organiser?（答案虚线）[1]；无下一题混入。"],
    "6(c)": ["(c) How did she feel before the first drama group session?（答案虚线）[1]；无下一题混入。"],
    "6(d)": ["(d) What did she find most difficult at first about performing?（答案虚线）[1] + 页脚；无下一题混入。"],
    "6(e)": ["(e) Why does she listen to music after a performance?（答案虚线）[1]；无下一题混入。"],
    "6(f)": ["(f) Which type of plays does she like performing in the most?（答案虚线）[1]；无下一题混入。"],
    "6(g)": ["(g) How is she helping with the preparations for the play Blue Skies? Give two details. (i)(ii)[2]；无下一题混入。"],
    "6(h)": ["(h) What is the problem with the clothes she has to wear in Blue Skies?（答案虚线）[1]；无下一题混入。"],
    "6(i)": ["(i) What have the students decided to buy to thank Sandy? Give two details. (i)(ii)[2] [Total: 11] + 页脚；无下一题。"],
}

MS_BLOCK = {
    "1": "MS 区块 1：包含 1(a)–1(c) 三行（B、C、D，各 1 分）；区块完整，无相邻题块混入。",
    "2": "MS 区块 2：包含 2(a)–2(g) 七行（A、B、A、C、B、C、A，各 1 分）；区块完整，无相邻题块混入。",
    "3": "MS 区块 3：包含 3(a)–3(g) 七行（B、C、D、A、B、C、B，各 1 分）；区块完整，无相邻题块混入。",
    "4": "MS 区块 4：包含 4(a)–4(k) 全部答案行（含 4(d)(i)(ii) 两行）；区块完整，无相邻题块混入。",
    "5": "MS 区块 5：包含 5(a)–5(e) 五行（7、1、8、3、5，各 1 分）；区块完整，无相邻题块混入。",
    "6": "MS 区块 6：包含 6(a)–6(i) 全部答案行（含 6(g)(i)(ii)、6(i)(i)(ii)）；区块完整，无相邻题块混入。",
}

MS_ROW = {
    "1(a)": "答案 B；Marks 1。", "1(b)": "答案 C；Marks 1。", "1(c)": "答案 D；Marks 1。",
    "2(a)": "答案 A；Marks 1。", "2(b)": "答案 B；Marks 1。", "2(c)": "答案 A；Marks 1。",
    "2(d)": "答案 C；Marks 1。", "2(e)": "答案 B；Marks 1。", "2(f)": "答案 C；Marks 1。",
    "2(g)": "答案 A；Marks 1。",
    "3(a)": "答案 B；Marks 1。", "3(b)": "答案 C；Marks 1。", "3(c)": "答案 D；Marks 1。",
    "3(d)": "答案 A；Marks 1。", "3(e)": "答案 B；Marks 1。", "3(f)": "答案 C；Marks 1。",
    "3(g)": "答案 B；Marks 1。",
    "4(a)": "答案 (by) train；Marks 1。",
    "4(b)": "答案 (a) statue (of a horse)；Marks 1。",
    "4(c)": "答案 (for her) sister's birthday；Marks 1。",
    "4(d)": "两行：4(d)(i) rock (group) + 4(d)(ii) folk (singer)；各 1 分（共 2 分）。",
    "4(e)": "答案 pizza；Marks 1。",
    "4(f)": "答案 (went to) buy / bought some clothes；Marks 1。",
    "4(g)": "答案 not the right size / the wrong size；Marks 1。",
    "4(h)": "答案 (for a) cake / (to make a) cake；Marks 1。",
    "4(i)": "答案 £3.50；Marks 1。",
    "4(j)": "答案 four hours；Marks 1。",
    "4(k)": "答案 (next) Wednesday；Marks 1。",
    "5(a)": "答案 7；Marks 1。", "5(b)": "答案 1；Marks 1。", "5(c)": "答案 8；Marks 1。",
    "5(d)": "答案 3；Marks 1。", "5(e)": "答案 5；Marks 1。",
    "6(a)": "答案 (class) tutor；Marks 1。",
    "6(b)": "答案 text；Marks 1。",
    "6(c)": "答案 (she) couldn't wait (to get started) / (she was) excited；Marks 1。",
    "6(d)": "答案 (knowing) where to stand (on the stage)；Marks 1。",
    "6(e)": "答案 (It / music) relaxes (her)；Marks 1。",
    "6(f)": "答案 (plays) set in the past；Marks 1。",
    "6(g)": "两行：6(g)(i) painting (the) scenery + 6(g)(ii) putting up posters（accept 'Nobody else wanted to put up posters'）；各 1 分（共 2 分）。",
    "6(h)": "答案 (hard to) take off quickly；Marks 1。",
    "6(i)": "两行：6(i)(i) (play / theatre) tickets + 6(i)(ii) chocolates；各 1 分（共 2 分）。",
}
MERGED = {"4(d)", "6(g)", "6(i)"}

now = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%dT%H:%M:%S+0800")
records = []

for fr, (num, role, page, _b1, bbox_raw) in zip(frame_regions, expected):
    img = fr["img"]
    if role == "qp":
        obs = QP_OBS[num]
        assert len(obs) == sum(1 for q in index["questions"] if q["question"] == num
                               for _ in q["qp"]), (num, len(obs))
        idx_within = sum(1 for q in index["questions"] if q["question"] == num
                         for _ in q["qp"]) - 1
        # find position of this region among the question's qp regions
        n = 0
        for q in index["questions"]:
            if q["question"] == num:
                for r in q["qp"]:
                    if r["page"] == page and tuple(round(float(x), 1) for x in r["bbox"]) == _b1:
                        idx_within = n
                    n += 1
        observed = obs[idx_within]
    else:
        if num in MS_BLOCK:
            observed = MS_BLOCK[num]
        else:
            tail = "两行区块完整（题号/答案/分值/guidance），无相邻行混入。" if num in MERGED \
                else "整行完整（题号/答案/分值/guidance），无相邻行混入。"
            observed = f"MS 行 {num}：{MS_ROW[num]}{tail}"
    records.append({
        "key": "0472/2025/Jun/22",
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

assert len(records) == 102, len(records)
assert sum(1 for r in records if r["role"] == "qp") == 54
assert sum(1 for r in records if r["role"] == "ms") == 48
assert len({(r["question"], r["role"], r["page"], tuple(r["bbox"])) for r in records}) == 102

with VERIF.open("a", encoding="utf-8") as fh:
    for r in records:
        fh.write(json.dumps(r, ensure_ascii=False) + "\n")

print(f"appended {len(records)} verification records (54 qp + 48 ms)")
print(f"index_sha256: {index_sha}")
print(f"checked_at: {now}")
