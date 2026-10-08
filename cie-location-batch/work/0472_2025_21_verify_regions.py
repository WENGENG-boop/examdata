"""0472/2025/Jun/21: write verification.jsonl records for all 103 regions.

All 103 regions (55 qp + 48 ms) were re-verified visually in the browser after
the index fix (viewer frames c01-c29 rebuilt from the fixed index), and the
whole-paper page frames were checked too. Q1 and Q1(c) share the same bbox on
p4, so frames are matched to index regions by ordered traversal (never by a
keyed dict). Each record maps 1:1 to the exact crop image shown in the viewer
(stack-*.png).
"""
import hashlib
import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

BR = Path(r"C:/Users/weo/Desktop/api/cie-location-batch")
IDX = BR / "indexes/0472/2025-Jun-21/cie-index.json"
VERIF = BR / "verification.jsonl"
SHEETS = BR / "work/sheets"

index = json.loads(IDX.read_text(encoding="utf-8"))
index_sha = hashlib.sha256(IDX.read_bytes()).hexdigest()
assert index_sha == "09a8e7293706306c284d934d428d0065f697d68e60f45be98dd1b0e64f713762", index_sha

# ---- parse viewer frames in order: (label, role, page, bbox) + crop image
cap_re = re.compile(r"<div class=cap>(.*?)</div><img src=\"([^\"]+)\"")
frame_regions = []
frames = sorted(SHEETS.glob("0472-2025-Jun-21-viewer-regions-c*.html"))
assert len(frames) == 29, len(frames)
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
assert len(frame_regions) == 103, len(frame_regions)

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
assert len(expected) == 103, len(expected)

for fr, (num, role, page, bbox1, bbox_raw) in zip(frame_regions, expected):
    assert fr["role"] == role and fr["page"] == page and fr["bbox"] == bbox1, \
        (fr, num, role, page, bbox1)
    want = ("Q" if role == "qp" else "M") + num
    assert fr["label"] == want, (fr["label"], want)
print("ordered 1:1 match with index: OK")

# ---- observations from the browser re-verification (frames c01-c29)
QP_OBS = {
    "1": ["p2 区域：题号 1 + 指示 'Read the texts. For each question, tick the correct box (A–D).' + (a) School Bookshop 通知框（完整）+ 'What does this notice say?' A–D + [1]；无下一题。",
          "p3 延展区：Alicia/Mike 短信 mockup + 'Mike is texting his sister to …' A–D + [1]；手机框顶部由子题 1(b) 区域完整覆盖，无文字丢失；无下一题。",
          "p4 延展区：(c) 标签 + 邮件 mockup（To: Jon / About: history website / Karim 正文）+ 'What is Karim saying in his email?' A–D + [1] + [Total: 3]；无下一题。"],
    "1(a)": ["(a) 标签 + School Bookshop 通知框（完整外框）+ 'What does this notice say?' A–D + [1]；修复后区域右缘 542.4 已含完整框；无下一题混入。"],
    "1(b)": ["(b) 标签 + 手机 mockup（browser dots 起）+ Alicia 聊天 + Mike 问题 A–D + [1]；无下一题混入。"],
    "1(c)": ["与父题 p4 同范围（同 bbox）：(c) 标签 + 邮件 + 问题 A–D + [1] + [Total: 3]；无下一题混入。"],
    "2": ["p6 区域：题号 2 + 'Read the report...' + 报告 'Camping weekend at Three Trees Campsite' by Gosia Nowak 正文 + (a)(b)(c) 题干与 A–C 选项；无下一题。",
          "p7 延展区：(d)(e)(f)(g) 题干与 A–C 选项 + [Total: 7]；无下一题。"],
    "2(a)": ["(a) When did the family arrive at the campsite? + A–C（in the morning / in the afternoon / in the evening）；无下一题混入。"],
    "2(b)": ["(b) Where was Gosia's tent? + A–C（near the river / among the trees / by the entrance）；无下一题混入。"],
    "2(c)": ["(c) What did Gosia eat for dinner the first night? + A–C（sausages / burgers / sandwiches）；无下一题混入。"],
    "2(d)": ["(d) At the beach, Gosia … + A–C（played a game / caught a fish / had a boat ride）；无下一题混入。"],
    "2(e)": ["(e) How did the family get to the mountains? + A–C（by car / by rail / by bike）；无下一题混入。"],
    "2(f)": ["(f) Gosia took a photo of + A–C（an animal / some trees / a building）；无下一题混入。"],
    "2(g)": ["(g) What did Gosia leave at the campsite? + A–C（her phone / her glasses / her coat）+ [Total: 7]；无下一题混入。"],
    "3": ["p8 区域：题号 3 + 指示 'Read the text, and choose the correct word to fill the gaps (a) to (g)...' + 'Extreme Sports' 正文（含空 (a)(b)(c)）+ 三组 A–D 选项；无下一题。",
          "p9 延展区：(d)–(g) 选项组 + [Total: 7]；无下一题。"],
    "3(a)": ["(a) 空选项组 A–D（contain / choose / include / mean）；无下一题混入。"],
    "3(b)": ["(b) 空选项组 A–D（show / sound / suggest / make）；无下一题混入。"],
    "3(c)": ["(c) 空选项组 A–D（more / enough / many / plenty）；无下一题混入。"],
    "3(d)": ["(d) 空选项组 A–D（condition / ability / situation / value）；无下一题混入。"],
    "3(e)": ["(e) 空选项组 A–D（easily / completely / correctly / clearly）；无下一题混入。"],
    "3(f)": ["(f) 空选项组 A–D（Until / After / Except / Without）；无下一题混入。"],
    "3(g)": ["(g) 空选项组 A–D（develop / suggest / involve / expect）+ [Total: 7]；无下一题混入。"],
    "4": ["p10 区域：题号 4 + 'Read the email, and answer the questions (a–k).' + Ali 邮件正文（Hi Grandma…）+ (a)–(d) 题干；无下一题。",
          "p11 延展区：(e)–(k) 题干 + [2] + [Total: 12]；无下一题。"],
    "4(a)": ["(a) Why didn't Ali's grandmother come to the show?；无下一题混入。"],
    "4(b)": ["(b) Where did the talent show happen?；无下一题混入。"],
    "4(c)": ["(c) How did Ali get to the talent show?；无下一题混入。"],
    "4(d)": ["(d) What time did the talent show start?；无下一题混入。"],
    "4(e)": ["(e) Which student year put on the show?；无下一题混入。"],
    "4(f)": ["(f) What did the students taking part wear?；无下一题混入。"],
    "4(g)": ["(g) What activities did Ali perform in the talent show? Give two details. + [2]；无下一题混入。"],
    "4(h)": ["(h) How did Ali feel during his performance?；无下一题混入。"],
    "4(i)": ["(i) What did the performers find surprising?；无下一题混入。"],
    "4(j)": ["(j) What prize did Ali win?；无下一题混入。"],
    "4(k)": ["(k) Where did Ali's family take him after the talent show? + 剩余空白区与页脚；无下一题。"],
    "5": ["p12 区域：题号 5 + 指示（five people (a–e) 与八个课程广告 1–8 匹配）+ Habiba/Paolo/Izabella/Diego/Christi 五人描述；无下一题。",
          "p13 延展区：八个摄影课程广告 1–8（Image Workshop … Picture Perfect）+ [5]；无下一题。"],
    "5(a)": ["(a) Habiba 描述段落及作答区；无下一题混入。"],
    "5(b)": ["(b) Paolo 描述段落及作答区；无下一题混入。"],
    "5(c)": ["(c) Izabella 描述段落及作答区；无下一题混入。"],
    "5(d)": ["(d) Diego 描述段落及作答区；无下一题混入。"],
    "5(e)": ["(e) Christi 描述段落及作答区；无下一题混入。"],
    "6": ["p14 区域：题号 6 + 'Read the blog, and answer the questions (a–i).' + 'Writing blog' by Siti Tan 正文 + (a)–(d) 题干；无下一题。",
          "p15 延展区：(e)–(i) 题干 + [2] + [2] + [Total: 11]；无下一题。"],
    "6(a)": ["(a) What did Siti write when she was younger?；无下一题混入。"],
    "6(b)": ["(b) How did Siti feel when her teacher finished reading her story to the class?；无下一题混入。"],
    "6(c)": ["(c) Where does Siti find it easiest to write?；无下一题混入。"],
    "6(d)": ["(d) What is Siti's latest story about?；无下一题混入。"],
    "6(e)": ["(e) Why did Siti decide to enter a writing competition? Give two details. + [2]；无下一题混入。"],
    "6(f)": ["(f) What has Siti used to improve her writing skills?；无下一题混入。"],
    "6(g)": ["(g) What problem does Siti have when asking for her parents' opinion?；无下一题混入。"],
    "6(h)": ["(h) What do Siti's friends say about her writing?；无下一题混入。"],
    "6(i)": ["(i) What advice did Siti get from her grandmother about writing? Give two details. + [2]；无下一题混入。"],
}

MS_BLOCK = {
    "1": "MS 区块 1：包含 1(a)–1(c) 三行（B、C、D，各 1 分）；区块完整，无相邻题块混入。",
    "2": "MS 区块 2：包含 2(a)–2(g) 七行（B、B、A、C、B、C、B，各 1 分）；区块完整，无相邻题块混入。",
    "3": "MS 区块 3：包含 3(a)–3(g) 七行（C、B、D、A、D、A、C，各 1 分）；区块完整，无相邻题块混入。",
    "4": "MS 区块 4：包含 4(a)–4(k) 全部答案行（含 4(g)(i)(ii) 两行）；区块完整，无相邻题块混入。",
    "5": "MS 区块 5：包含 5(a)–5(e) 五行（4、8、1、6、2，各 1 分）；区块完整，无相邻题块混入。",
    "6": "MS 区块 6：包含 6(a)–6(i) 全部答案行（含 6(e)(i)(ii)、6(i)(i)(ii)）；区块完整，无相邻题块混入。",
}

MS_ROW = {
    "1(a)": "答案 B；Marks 1。", "1(b)": "答案 C；Marks 1。", "1(c)": "答案 D；Marks 1。",
    "2(a)": "答案 B；Marks 1。", "2(b)": "答案 B；Marks 1。", "2(c)": "答案 A；Marks 1。",
    "2(d)": "答案 C；Marks 1。", "2(e)": "答案 B；Marks 1。", "2(f)": "答案 C；Marks 1。",
    "2(g)": "答案 B；Marks 1。",
    "3(a)": "答案 C；Marks 1。", "3(b)": "答案 B；Marks 1。", "3(c)": "答案 D；Marks 1。",
    "3(d)": "答案 A；Marks 1。", "3(e)": "答案 D；Marks 1。", "3(f)": "答案 A；Marks 1。",
    "3(g)": "答案 C；Marks 1。",
    "4(a)": "答案 (She was on) holiday；Marks 1。",
    "4(b)": "答案 town theatre；Marks 1。",
    "4(c)": "答案 (by) walking / (he) walked / (on) foot；Marks 1。",
    "4(d)": "答案 7(.00)；Marks 1。",
    "4(e)": "答案 (Year) 9；Marks 1。",
    "4(f)": "答案 (special) costumes (instead of school uniform)；Marks 1。",
    "4(g)": "两行：4(g)(i) (played his) violin + 4(g)(ii) sang / a song / singing (in his group)；各 1 分（共 2 分）。",
    "4(h)": "答案 excited；Marks 1。",
    "4(i)": "答案 (the) audience (sometimes) sang (along with them)；Marks 1。",
    "4(j)": "答案 book；Marks 1。",
    "4(k)": "答案 café；Marks 1。",
    "5(a)": "答案 4；Marks 1。", "5(b)": "答案 8；Marks 1。", "5(c)": "答案 1；Marks 1。",
    "5(d)": "答案 6；Marks 1。", "5(e)": "答案 2；Marks 1。",
    "6(a)": "答案 (little) poems；Marks 1。",
    "6(b)": "答案 (really) proud；Marks 1。",
    "6(c)": "答案 noisy café（含 accept：somewhere that is noisy 等）；Marks 1。",
    "6(d)": "答案 (the) environment；Marks 1。",
    "6(e)": "两行：6(e)(i) (she wants) to know what people think about it / her story（2 分）+ 6(e)(ii) (she would love) to have it / her story printed (online)（accept 行）；共 2 分。",
    "6(f)": "答案 website (for young writers)；Marks 1。",
    "6(g)": "答案 they think everything (she writes) is fantastic（accept：they're not critical enough）；Marks 1。",
    "6(h)": "答案 she spends too much time (writing) / they complain about the time she spends (writing)；Marks 1。",
    "6(i)": "两行：6(i)(i) write (something) every day + 6(i)(ii) write about something you've / she has experienced / that has happened to you / her；各 1 分（共 2 分）。",
}
MERGED = {"4(g)", "6(e)", "6(i)"}

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
        "key": "0472/2025/Jun/21",
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

assert len(records) == 103, len(records)
assert sum(1 for r in records if r["role"] == "qp") == 55
assert sum(1 for r in records if r["role"] == "ms") == 48
assert len({(r["question"], r["role"], r["page"], tuple(r["bbox"])) for r in records}) == 103

with VERIF.open("a", encoding="utf-8") as fh:
    for r in records:
        fh.write(json.dumps(r, ensure_ascii=False) + "\n")

print(f"appended {len(records)} verification records (55 qp + 48 ms)")
print(f"index_sha256: {index_sha}")
print(f"checked_at: {now}")
