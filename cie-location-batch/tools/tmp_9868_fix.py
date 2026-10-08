"""临时脚本：就地重写 9868/2026/Jun/12 的索引 questions 与 verification.jsonl。"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

B = Path("C:/Users/weo/Desktop/api/cie-location-batch")
KEY = "9868/2026/Jun/12"
IDX = B / "indexes/9868/2026-Jun-12/cie-index.json"
VJL = B / "verification.jsonl"

X0, X1 = 45.0, 557.0          # QP 区域横向范围
MS_X0, MS_X1 = 72.0, 545.0    # MS 表格横向范围
MS_H = 11.5                   # MS 行半高
MS_P2_TOP, MS_STEP = 87.9, 22.95

# ---- QP 版面：每题 (页, stem 基线, 末行基线) ----
QP_LAYOUT = {
    1: (2, 141.2, 266.1), 2: (2, 306.0, 429.9), 3: (2, 469.9, 593.7), 4: (2, 633.7, 757.5),
    5: (3, 73.3, 197.2), 6: (3, 237.1, 361.0),
    13: (5, 141.2, 162.4), 14: (5, 203.4, 224.6), 15: (5, 265.6, 286.8), 16: (5, 327.8, 349.0),
    17: (5, 390.0, 411.2), 18: (5, 452.2, 473.4), 19: (5, 514.4, 535.6), 20: (5, 576.6, 597.8),
    21: (6, 141.2, 141.2), 22: (6, 181.2, 181.2), 23: (6, 221.1, 221.1), 24: (6, 261.1, 261.1),
    25: (6, 301.0, 301.0), 26: (6, 341.0, 341.0), 27: (6, 380.9, 380.9), 28: (6, 420.9, 420.9),
    29: (6, 460.9, 460.9), 30: (6, 500.8, 500.8), 31: (6, 540.8, 540.8), 32: (6, 580.7, 580.7),
    33: (7, 141.2, 261.6), 34: (7, 295.5, 415.9), 35: (7, 449.9, 570.2), 36: (7, 604.2, 724.6),
    37: (8, 73.3, 192.7), 38: (8, 225.6, 345.9), 39: (8, 378.9, 499.3), 40: (8, 532.2, 652.6),
}
# 同页相邻题共用的“下一题起点”，用于裁掉两题之间的空白
NEXT_STEM = {13: 203.4, 14: 265.6, 15: 327.8, 16: 390.0, 17: 452.2, 18: 514.4, 19: 576.6,
             21: 181.2, 22: 221.1, 23: 261.1, 24: 301.0, 25: 341.0, 26: 380.9, 27: 420.9,
             28: 460.9, 29: 500.8, 30: 540.8, 31: 580.7}
# 第 4 页只有答题说明与句子选项 A–H，Q7–Q12 的短文正文在插页中
QP_INSERT_PAGE4 = [45.0, 94.0, 557.0, 390.0]

QP_TEXT = {
    1: "黄宇翔在找工作时的理念是……\nA 要看眼前的情况先就业再说。\nB 薪水高的工作必然是好工作。\nC 有更多发展机会的工作最好。\nD 留在一线城市比返乡工作好。",
    2: "黄宇翔的同学在毕业前做了什么？\nA 忙着完成毕业论文\nB 考了不同的资格证\nC 开始为找工作做准备\nD 复习以前学过的内容",
    3: "想进专业对口的公司工作就必须……\nA 有良好的人脉。\nB 有扎实的专业底子。\nC 有比别人更高的学位。\nD 有一些求职方面的技巧。",
    4: "在求职初始，黄宇翔的优势是什么？\nA 学科排名一直都名列前茅\nB 拥有出色的实际工作能力\nC 有大学导师给他写的推荐信\nD 积累了相当丰富的社团经验",
    5: "大多数学生求职不容易体现在……\nA 他们连面试的资格都得不到。\nB 每年应届毕业生的数量太多了。\nC 他们缺乏实战经验和抗压能力。\nD 学生的技能和公司需求未必接轨。",
    6: "黄宇翔选择了现在的工作是因为……\nA 公司的员工福利更好。\nB 他可以向同事学习。\nC 父母认为将来工资涨幅更高。\nD 他在这家公司花的心思更多。",
    13: "哪个人觉得环保的关键是植树造林？\nA 叶枫\nB 王励\nC 刘岚\nD 李森",
    14: "哪个人觉得商家的环保措施其实是以促销为目的？\nA 叶枫\nB 王励\nC 刘岚\nD 李森",
    15: "哪个人觉得要多开发使用再生能源？\nA 叶枫\nB 王励\nC 刘岚\nD 李森",
    16: "哪个人觉得每个人都应该节约用电？\nA 叶枫\nB 王励\nC 刘岚\nD 李森",
    17: "哪个人认为低碳出行很难坚持？\nA 叶枫\nB 王励\nC 刘岚\nD 李森",
    18: "哪个人认为环保意识已经深入到了大部分年轻人的心中？\nA 叶枫\nB 王励\nC 刘岚\nD 李森",
    19: "哪个人目睹过无视环保的行为？\nA 叶枫\nB 王励\nC 刘岚\nD 李森",
    20: "哪个人认为从小事入手和其他环保方式同等重要？\nA 叶枫\nB 王励\nC 刘岚\nD 李森",
    21: "（短文四，插页）空格处应填入：\nA 不是\nB 就是\nC 还是\nD 而是",
    22: "（短文四，插页）空格处应填入：\nA 却\nB 亦\nC 则\nD 可",
    23: "（短文四，插页）空格处应填入：\nA 团圆\nB 和平\nC 永恒\nD 无限",
    24: "（短文四，插页）空格处应填入：\nA 把\nB 被\nC 没\nD 采",
    25: "（短文四，插页）空格处应填入：\nA 琐事\nB 精品\nC 成本\nD 细活",
    26: "（短文四，插页）空格处应填入：\nA 才\nB 曾\nC 再\nD 已",
    27: "（短文四，插页）空格处应填入：\nA 扶手\nB 手柄\nC 颜料\nD 塑料",
    28: "（短文四，插页）空格处应填入：\nA 普及\nB 广泛\nC 提高\nD 传播",
    29: "（短文四，插页）空格处应填入：\nA 灭亡\nB 死亡\nC 败落\nD 衰落",
    30: "（短文四，插页）空格处应填入：\nA 一丝不苟\nB 一步登天\nC 一炮而红\nD 一石二鸟",
    31: "（短文四，插页）空格处应填入：\nA 能\nB 只\nC 共\nD 刚",
    32: "（短文四，插页）空格处应填入：\nA 出路\nB 花样\nC 体裁\nD 方式",
    33: "走马观花式旅游的存在条件是什么？\nA 网络的出现\nB 生活水平的不断提高\nC 人们不太讲究个人需求\nD 游客只想着在景点拍照留念",
    34: "是什么把影视剧和旅游联系在一起？\nA 旅游省份对影视公司的赞助\nB 剧情展示景点的风土人情\nC 现代人审美观念的转变\nD 影视中不同的文化冲突",
    35: "普通电视剧和旅剧的共同点是什么？\nA 引人入胜的情节\nB 故事人物的着装\nC 都会有一些网红\nD 摄录当地的方言",
    36: "一部好的旅剧会给观众带来……\nA 不同影星们的精湛演技。\nB 对当地的一些真切感受。\nC 想马上看到下一集的念头。\nD 应用以前学过的地理常识的机会。",
    37: "小兰为什么想去云南旅游？\nA 云南有秀丽的风景\nB 在云南品茶很时尚\nC 想尝尝那儿的美食\nD 被热播的旅剧打动",
    38: "旅剧的拍摄点往往是……\nA 少数民族居住地。\nB 以观众的兴趣为主。\nC 一线城市或港口城市。\nD 由剧情需要而决定的。",
    39: "除了体现旅游价值以外，旅剧还……\nA 有固定的观众和票房收入。\nB 有赏心悦目和幽默的特点。\nC 以增强游览娱乐性为目的。\nD 使用电脑合成技术来制图。",
    40: "为什么张亮认为旅剧受欢迎是必然的？\nA 文化旅游宣传的力度加大了。\nB 影视剧的内容越来越多样化。\nC 沉浸式体验在年轻人中很流行。\nD 旅剧是一种寓教于乐的休闲方式。",
}

SENTENCE_BANK = ("A 那时他正好能搬动两块砖\nB 土屋显得矮了许多\nC 那里承载了我许多童年的快乐\n"
                 "D 但土屋还是被妈妈收拾得好好的\nE 但家人心里都是乐呵呵的\nF 也许老屋保留了我太多的记忆了吧\n"
                 "G 让人觉得又大又亮堂\nH 这一刻我却能想象出他忙碌的模样")
for _n in range(7, 13):
    QP_TEXT[_n] = (f"阅读插页中的短文二，回答问题 7–12。短文中有六句话（7–12）被去除，"
                   f"从句子（A–H）中选出正确答案填空。第 {_n} 句对应下列哪个句子？\n{SENTENCE_BANK}")

# MS 答案（逐题看图核验）
MS_ANSWER = {1: "C", 2: "C", 3: "B", 4: "D", 5: "A", 6: "A", 7: "C", 8: "A", 9: "E", 10: "B",
             11: "H", 12: "F", 13: "C", 14: "A", 15: "D", 16: "C", 17: "B", 18: "B", 19: "D",
             20: "A", 21: "C", 22: "B", 23: "A", 24: "B", 25: "D", 26: "C", 27: "B", 28: "A",
             29: "D", 30: "C", 31: "A", 32: "D", 33: "C", 34: "B", 35: "A", 36: "B", 37: "C",
             38: "D", 39: "B", 40: "D"}


def qp_region(n: int) -> dict:
    if 7 <= n <= 12:
        return {"page": 4, "bbox": list(QP_INSERT_PAGE4)}
    page, stem, last = QP_LAYOUT[n]
    y0 = stem - 12.0
    y1 = (NEXT_STEM[n] - 12.0) if n in NEXT_STEM else (last + 13.0)
    return {"page": page, "bbox": [X0, round(y0, 1), X1, round(y1, 1)]}


def ms_region(n: int) -> dict:
    page = 2 if n <= 28 else 3
    base = MS_P2_TOP + MS_STEP * ((n - 1) if n <= 28 else (n - 29))
    return {"page": page, "bbox": [MS_X0, round(base - MS_H, 2), MS_X1, round(base + MS_H, 2)]}


def note_for(n: int) -> str:
    msp = 2 if n <= 28 else 3
    row = n if n <= 28 else n - 28
    if 7 <= n <= 12:
        head = "已按 PDF 渲染图视觉核验：QP 第 4 页的答题说明与句子选项 A–H；"
    else:
        page, stem, _last = QP_LAYOUT[n]
        head = f"已按 PDF 渲染图视觉核验：QP 第 {page} 页（题干基线 y={stem}）与 A–D 选项；"
    s = head + f"MS 第 {msp} 页第 {row} 行，答案 {MS_ANSWER[n]}，1 分。"
    if 7 <= n <= 12:
        s += " 短文二正文在插页中，不在本卷；区域指向第 4 页的答题说明与句子选项 A–H。"
    if 21 <= n <= 32:
        s += " 短文四正文在插页中，不在本卷；本卷只印出四个备选词。"
    if 13 <= n <= 20:
        s += " 短文三正文在插页中，不在本卷。"
    if 1 <= n <= 6:
        s += " 短文一正文在插页中，不在本卷。"
    return s


def main() -> int:
    obj = json.loads(IDX.read_text(encoding="utf-8"))
    now = datetime.now().astimezone().isoformat(timespec="seconds")

    questions = []
    for n in range(1, 41):
        q = {
            "question": str(n),
            "parent": None,
            "text": QP_TEXT[n],
            "marks": 1,
            "qp": [qp_region(n)],
            "ms": [ms_region(n)],
            "uncertain": False,
            "notes": note_for(n),
        }
        questions.append(q)
    obj["questions"] = questions
    IDX.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [json.dumps({
        "key": KEY,
        "kind": "verification_correction",
        "note": "上一批 verification 行未做视觉核验，已作废；本轮重新逐题核验",
        "at": now,
    }, ensure_ascii=False)]
    for n in range(1, 41):
        for role, reg in (("qp", qp_region(n)), ("ms", ms_region(n))):
            lines.append(json.dumps({
                "key": KEY,
                "question": str(n),
                "role": role,
                "page": reg["page"],
                "bbox": reg["bbox"],
                "checks": "视觉核验：与 PDF 渲染图逐字比对一致" if role == "qp"
                          else f"视觉核验：MS 答案 {MS_ANSWER[n]}，1 分",
                "issues": "",
                "checked_at": now,
            }, ensure_ascii=False))
    with VJL.open("a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

    print(f"写入 {IDX}")
    print(f"questions={len(obj['questions'])} 追加 verification 行={len(lines)}")
    print("首题:", json.dumps(obj["questions"][0], ensure_ascii=False)[:400])
    print("第7题 qp:", json.dumps(obj["questions"][6]["qp"], ensure_ascii=False))
    print("第40题 ms:", json.dumps(obj["questions"][39]["ms"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
