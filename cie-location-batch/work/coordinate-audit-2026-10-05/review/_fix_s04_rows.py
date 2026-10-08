import json, io, sys

P = "review/obs-s04.jsonl"

# --- tail replacements for the 8 boundary-flagged region lines ---
TAIL = {
 6: ("四边：左/右/上边界完整；下边缘紧贴 1(e) 第 5 点文字，未见该行下边框，疑 1(e) 行在区域下缘被切断（无法确认该行是否还有后续内容）。属评分内容。",
     "四边：左/右/上边界完整；下边缘紧贴 1(e) 第 5 点文字与其下边框。经整页 p9（page_pair seq32）比对，1(e) 为该页评分表末行，其后无更多内容，故文字完整、未截断；仅下缘与表底框线重合、无多余留白。属评分内容。"),
 8: ("四边：左/右/上完整；下边缘紧贴第 5 点文字，未见该行下边框，疑被切断。题号与文件名/索引一致。属评分内容。",
     "四边：左/右/上完整；下边缘紧贴第 5 点文字与下边框。经整页 p9 比对，1(e) 为页末行，文字完整、未截断。题号与文件名/索引一致。属评分内容。"),
 17:("四边：上缘含完整表头，左右完整；下边缘紧贴 2(e) 末行文字，未见该行下边框。属评分内容。",
     "四边：上缘含完整表头，左右完整；下边缘紧贴 2(e) 末行文字/下边框。经整页 p13（page_pair seq34）比对，2(e) 为该页评分表末行，其后无更多内容，文字完整未截断。属评分内容。"),
 20:("四边：左/右/上完整；下边缘紧贴末行文字（红色辅助框下缘），未见该行下边框，无法排除截断。题号与文件名/索引一致。属评分内容。",
     "四边：左/右/上完整；下边缘紧贴末行文字（红色辅助框下缘）。经整页 p13 比对，2(e) 为页末行，文字完整、未截断。题号与文件名/索引一致。属评分内容。"),
 21:("四边：上/左/右完整；下边缘落在紧随其后的表头行内，该表头行被下缘截断。属评分内容。",
     "四边：上/左/右完整；下边缘位于紧随其后的下一张表表头行之下、第 4 题行之上——即本区域在 3(c) 之后多包含了一行下一张表的通用表头 \"Question | Answer | Marks | Guidance\"（该表头完整可见、未被截断），属对下一张表表头的越界包含。属评分内容。"),
 24:("四边：上/左/右完整；下边缘落在该表头行下方，其下内容被截断。题号与文件名/索引一致。属评分内容。",
     "四边：上/左/右完整；下边缘位于紧随其后的下一张表表头行之下（该表头完整可见、未截断），第 4 题行被排除在外——即本区域在 3(c) 之后多包含了一行下一张表的通用表头。题号与文件名/索引一致。属评分内容。"),
 25:("四边：左/右/上完整（Guidance 长句在区域内换行，未丢字）；下边缘紧贴末行 \"Do not accept: graphs showing decreasing distance.\"，未见下边框，无法排除截断。题号与文件名/索引一致。属评分内容。",
     "四边：左/右/上完整（Guidance 长句在区域内换行，未丢字）；下边缘紧贴末行 \"Do not accept: graphs showing decreasing distance.\"，其下可见该行下边框与极窄留白。经整页 p14 比对，第 4 题为该表末行，文字完整未截断。题号与文件名/索引一致。属评分内容。"),
 26:("四边：上/左/右完整；下边缘落在该表头行处。属评分内容。",
     "四边：上/左/右完整；下边缘位于紧随其后的下一张表表头行之下、第 6 题行之上——即本区域在题 5 之后多包含了一行下一张表的通用表头 \"Question | Answer | Marks | Guidance\"（完整可见、未截断），第 6 题行被排除。属评分内容。"),
}

NEWISSUES = {
 6: ["下边缘与 1(e) 行下边框/末行文字重合、无留白；经整页 p9 比对确认 1(e) 为页末行，内容完整未截断（边界贴合偏紧，非内容缺失）"],
 8: ["下边缘与末行文字/下边框重合、无留白；经整页 p9 比对确认内容完整未截断"],
 17:["下边缘与 2(e) 行下边框/末行文字重合、无留白；经整页 p13 比对确认 2(e) 为页末行，内容完整未截断"],
 20:["下边缘与末行文字/红色辅助框下缘重合、无留白；经整页 p13 比对确认内容完整未截断"],
 21:["下缘越过 3(c) 行、多包含紧随其后的下一张表通用表头行（\"Question | Answer | Marks | Guidance\"，完整未截断）；表头非 question 3 内容，属轻微越界包含"],
 24:["下缘越过 3(c) 行、多包含紧随其后的下一张表通用表头行（完整未截断）；属轻微越界包含"],
 25:["下边缘紧贴末行文字、留白极窄；经整页 p14 比对确认第 4 题内容完整未截断"],
 26:["下缘越过题 5 行、多包含紧随其后的下一张表通用表头行（完整未截断）；表头非题 5 内容，属轻微越界包含"],
}

lines = [l for l in io.open(P, encoding="utf-8").read().split("\n") if l.strip()]
objs = [json.loads(l) for l in lines]

byseq = {}
for o in objs:
    byseq[o["seq"]] = o

for seq, (old, new) in TAIL.items():
    o = byseq[seq]
    assert old in o["observed"], ("tail not found for seq", seq)
    o["observed"] = o["observed"].replace(old, new)
    o["issues"] = NEWISSUES[seq]

# --- append page_pair lines 28..35 ---
pairs = [
 (28,"pairs/8386_2026_Jun_12/ms-pair-01-02.png",[1,2],
  "左页 p1、右页 p2，图顶各有小字标签 \"8386 2026 Jun 12 ms p1\" / \"8386 2026 Jun 12 ms p2\"。p1 为封面页：\"Cambridge International AS Level\"、\"SPORT & PHYSICAL EDUCATION\"、\"8386/12\"、\"MARK SCHEME\"、\"Maximum Mark: 70\"、\"Published\"、\"May/June 2026\"、\"This document consists of 15 printed pages.\"、\"[Turn over\"、\"© Cambridge University Press & Assessment 2026\"；注意 p1 的文字在本渲染中整体旋转约 90°（竖排），与右页 p2 的正立方向不同。p2 为 \"General marking principles\" 页：页眉 \"8386/12 | Cambridge International AS Level – Mark Scheme | PUBLISHED | May/June 2026\"，正文为 1–6 条通用评分原则（含 \"Examiners must award marks for each response in line with…\"、\"Examiners must use the full range of marks…\"），页脚 \"© Cambridge University Press & Assessment 2026\"、\"Page 2 of 15\"。两页均无题号（封面页与通用原则页），故索引中 p1、p2 无 region 条目属正常。",
  ["p1（封面）文字在本渲染中整体旋转约 90°（竖排），与 p2 正立不一致；或源于原件封面朝向差异或渲染旋转，建议核实"]),
 (29,"pairs/8386_2026_Jun_12/ms-pair-03-04.png",[3,4],
  "左页 p3、右页 p4，两页均正立、无旋转。p3 = \"Science-Specific Marking Principles\"：页眉 \"8386/12 | Cambridge International AS Level – Mark Scheme | PUBLISHED | May/June 2026\"，表内条目 1 \"Examiners should consider the context and scientific use of any keywords…\"、2 \"The examiner should not choose between contradictory statements…\"、3 \"Although spellings do not have to be correct…\"、4 \"The error carried forward (ecf) principle…\"、5 \"'List rule' guidance\"（含 n responses 的 5 个 bullet）；页脚 \"Page 3 of 15\"。p4 为续表：条目 6 \"Calculation specific guidance\"、7 \"Guidance for chemical equations\"；页脚 \"Page 4 of 15\"。两页均无题号，故索引中 p3、p4 无 region 条目属正常。",
  []),
 (30,"pairs/8386_2026_Jun_12/ms-pair-05-06.png",[5,6],
  "左页 p5、右页 p6，两页均正立。p5 = \"Annotations guidance for centres\"：页眉 \"8386/12 | Cambridge International AS Level – Mark Scheme | PUBLISHED | May/June 2026\"，正文说明段落 + \"Annotations\" 表（Annotation | Meaning），行含 \"correct point or mark awarded\"、\"incorrect point or mark not awarded\"、\"information missing or insufficient for credit\"、\"contradiction in response, mark not awarded\"、\"benefit of the doubt given\"、\"error carried forward applied\"、\"point has been noted, but no credit has been given / or blank page seen\"、\"response is too vague or there is insufficient detail in response\"、\"linked consideration of points\"；页脚 \"© Cambridge University Press & Assessment 2026\"、\"Page 5 of 15\"。p6 = 该表续表：\"Annotation | Meaning\" 表头 + \"linked consideration of points\"、\"repetition in response\"；页脚 \"Page 6 of 15\"。两页均无题号，故索引中 p5、p6 无 region 条目属正常。",
  []),
 (31,"pairs/8386_2026_Jun_12/ms-pair-07-08.png",[7,8],
  "左页 p7、右页 p8，两页均正立，均含表头 \"Question | Answer | Marks | Guidance\"。p7 含题号 \"1(a)\"（分值 6；答案 6 点，含 \"(articulating bones) humerus AND radius AND ulna;\"、\"(main agonist) triceps brachii;\"、\"(main agonist) rectus femoris;\"；Guidance \"Ignore patella.\"、\"Do not accept: ambiguous spellings.\" 等）与 \"1(b)\"（分值 3；1–7 点 + \"Accept other appropriate strategies.\"；Guidance \"Practice alone = TV.\"、\"Control anxiety = TV.\"）；页脚 \"Page 7 of 15\"。p8 仅含题号 \"1(c)\"（分值 5；1–12 点，含 \"motor programmes for goalkeeping skills are seen as a generalised series of movements;\"、末行 \"The response must be applied to goalkeeping skills for credit.\"；Guidance \"Use of part / whole practice = TV.\" 等）；页脚 \"Page 8 of 15\"。与索引对照：p7 有 1(a)/1(b)（对应 region seq1–3）、p8 仅有 1(c)（对应 region seq4–5），一致；p8 仅一个 part，故 question 级与 part 级 bbox 必然重合。",
  []),
 (32,"pairs/8386_2026_Jun_12/ms-pair-09-10.png",[9,10],
  "左页 p9、右页 p10，两页均正立，均含表头。p9 含 \"1(d)\"（分值 4；4 点，含 \"(weight) pulls the ball downwards OR acts downwards / towards the ground;\"、\"(friction) acts in the opposite direction…\"；Guidance \"(Air resistance) acts against the ball = BOD 2.\" 等）与 \"1(e)\"（分值 4；\"(Newton's first law)\" 1–2、\"(Newton's third law)\" 3–5，末点 \"5 … which is equal AND opposite to the action force;\"；Guidance \"Do not accept: ball will have constant motion.\"、\"Goalkeeper's kick applies a force to the ball = BOD 3.\"）；1(e) 为 p9 评分表末行；页脚 \"Page 9 of 15\"。p10 含 \"1(f)\"（分值 3；\"height of release;\" 等）与 \"1(g)\"（分值 5；\"boundaries / pitch size / pitch markings;\" 等）；页脚 \"Page 10 of 15\"。与索引对照：p9 有 1(d)/1(e)（对应 region seq6–8）、p10 有 1(f)/1(g)（对应 region seq9–11），一致；并据此确认 1(e) 为 p9 末行、其文字完整（region seq6/seq8 下缘未截断）。",
  []),
 (33,"pairs/8386_2026_Jun_12/ms-pair-11-12.png",[11,12],
  "左页 p11、右页 p12，两页均正立，均含表头。p11 仅含 \"1(h)\"（分值 5；1–16 点，含 \"(economic status) cheap to play OR minimal equipment needed;\"、\"16 high levels of investment (in grass-roots football);\"、末行 \"Accept other appropriate explanations.\"；Guidance \"It can be played anywhere / many clubs / leagues / competitions = BOD 8.\"）；页脚 \"Page 11 of 15\"。p12 含 \"2(a)\"（分值 4；\"(footwear, sub-max. 2 marks)\"、\"(clothing, sub-max. 2 marks)\"）与 \"2(b)\"（分值 5；1–6 点 + \"Accept other appropriate suggestions.\"）；页脚 \"Page 12 of 15\"。与索引对照：p11 仅 1(h)（对应 region seq12–13）、p12 有 2(a)/2(b)（对应 region seq14–16），一致；p11 仅一个 part，故 question 级与 part 级 bbox 必然重合。",
  []),
 (34,"pairs/8386_2026_Jun_12/ms-pair-13-14.png",[13,14],
  "左页 p13、右页 p14，两页均正立。p13 含表头与 \"2(c)\"（分值 3）、\"2(d)\"（分值 4；\"(intrinsic, sub-max. 2 marks)\"、\"(extrinsic, sub-max. 2 marks)\"）、\"2(e)\"（分值 4；\"(tidal volume) decreases;\"、\"(expiratory reserve volume) increases;\"）；2(e) 为 p13 评分表末行；页脚 \"Page 13 of 15\"。p14 含 \"3(a)\"（Answer \"68;\"，分值 1，Guidance 空白）、\"3(b)\"（分值 2，\"(answer) 58.8;\"）、\"3(c)\"（分值 3，\"(answer) 3.4;\"、\"(units) kilogram(s) metres per second;\"），随后为下一张表的表头 \"Question | Answer | Marks | Guidance\" 与题号 \"4\"（分值 3；\"(rest) horizontal line on graph from 0 to 2 seconds;\"、\"Do not accept: graphs showing decreasing distance.\"）；页脚 \"Page 14 of 15\"。与索引对照：p13 有 2(c)/2(d)/2(e)（对应 region seq17–20）、p14 有 3(a)/3(b)/3(c)（seq21–24）与题 4（seq25），一致；并据此确认 2(e) 为 p13 末行、3(c) 之后确实接下一张表表头再是第 4 题。",
  []),
 (35,"pairs/8386_2026_Jun_12/ms-pair-15-15.png",[15],
  "单页 p15（左=右同页），正立。含表头与题号 \"5\"（分值 4；\"1 mark for:\" + \"and 3 marks for any 3 of:\"，1–9 点，含 \"(autonomic nervous system) determines the firing rate of sinoatrial node…\"、\"(sympathetic nervous system)\" 4–6、\"(parasympathetic nervous system)\" 7–9 \"… role of acetylcholine;\"；Guidance \"Ignore adrenaline.\"、\"Accept: release of (nor)epinephrine for 5.\"），随后为下一张表的表头 \"Question | Answer | Marks | Guidance\" 与题号 \"6\"（分值 2；1 \"(positive) a (learned) skill enhances the learning of another skill…\"、2 \"(bilateral)…\"，末行 \"Accept suitable alternative descriptions.\"；Guidance \"Learning a skill has a positive effect on learning another skill = TV.\" 等）；页脚 \"Page 15 of 15\"。与索引对照：p15 有题 5（region seq26）与题 6（region seq27），一致；并确认题 5 之后接下一张表表头再是题 6。",
  []),
]

for seq, f, pages, obs, iss in pairs:
    objs.append({
        "kind": "page_pair",
        "seq": seq,
        "file": f,
        "pages": pages,
        "role": "ms",
        "observed": obs,
        "checks": {"content_complete": True, "boundary_checked": True, "role_matches": True},
        "issues": iss,
    })

out = "\n".join(json.dumps(o, ensure_ascii=False) for o in objs) + "\n"
with io.open(P, "w", encoding="utf-8", newline="\n") as fh:
    fh.write(out)

print("wrote", len(objs), "records")
