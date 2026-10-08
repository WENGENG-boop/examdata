# -*- coding: utf-8 -*-
"""build_regions / lead_owner 回归测试（合成数据，不联网、不读 PDF）。

场景一复刻 9396 MS 的真实形状：p7 最后一个标签是 2(b)（y268.8），p8 的第一个标签是
2(c)(ii)（y293.6），p8 顶部 104..291.6 印着 2(b) 的评分说明，属于 2(b) 的续写。

场景二复刻 9713 QP 的真实形状：p4 顶部只有右栏一个孤零零的分数数字 `4`（没有正文），
页首段不建区域 —— 否则取出来是空白条。
"""
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import ocr_index as O

CONTENT = (58.0, 100.0, 750.0, 552.0)
DISP = (0.0, 0.0, 792.0, 612.0)


def line(y0, x0, text, x1=None):
    return {"y0": y0, "y1": y0 + 8.0, "x0": x0, "x1": x1 or (x0 + 74.0), "text": text}


PAGES = {
    7: {"no": 7, "lines": [], "content": CONTENT, "disp": DISP, "rot": 90,
        "derot": None, "bounds": (0.0, 0.0, 612.0, 792.0)},
    8: {"no": 8, "lines": [line(104.0, 120.0, "4 marks for 4 of:"),
                           line(127.6, 120.8, "Max. 3 marks if no practical example is used .")],
        "content": CONTENT, "disp": DISP, "rot": 90,
        "derot": None, "bounds": (0.0, 0.0, 612.0, 792.0)},
}


def ev(page, y0, level, token):
    return {"page": page, "y0": y0, "y1": y0 + 12.0, "x0": 72.0, "level": level,
            "token": token, "text": f"p{page} {token}"}


EVENTS = [
    ev(7, 162.4, 1, "2"),
    ev(7, 162.4, 2, "a"),
    ev(7, 162.4, 3, "ii"),
    ev(7, 268.8, 2, "b"),
    ev(8, 293.6, 1, "2"),
    ev(8, 293.6, 2, "c"),
    ev(8, 293.6, 3, "ii"),
]

questions, dropped, deepest = O.build_hierarchy(EVENTS, "ms")
lead = O.lead_owner(EVENTS, deepest)
print("questions:", sorted(questions))
print("dropped:", dropped)
print("deepest:", deepest)
print("lead:", lead)

assert lead == {8: "2(b)"}, lead

bad = 0


def regions_for(qid, pages=PAGES, events=EVENTS, owner=lead, qs=questions):
    own = {p: next(e["y0"] for e in events if e["page"] == p)
           for p, who in owner.items() if O.is_ancestor(qs, qid, who)}
    return O.build_regions(O.subtree_indexes(qs, qid), events, pages, lead=own)


def check(qid, expected, **kw):
    global bad
    got = [(r["page"], tuple(round(v, 1) for v in r["disp"])) for r in regions_for(qid, **kw)]
    ok = got == expected
    if not ok:
        bad += 1
    print("OK " if ok else "BAD", qid, got, "exp", expected)


# 2(b) 只在 p7 有标签，但要接住 p8 顶部那段（98..291.6），且不能吞掉 2(c)(ii)。
check("2(b)", [(7, (56.0, 266.8, 752.0, 554.0)), (8, (56.0, 98.0, 752.0, 291.6))])
# 父题 2 覆盖 p8 全页（两段合并）。
check("2", [(7, (56.0, 160.4, 752.0, 554.0)), (8, (56.0, 98.0, 752.0, 554.0))])
# 2(c)(ii) 不接页首段。
check("2(c)(ii)", [(8, (56.0, 291.6, 752.0, 554.0))])
check("2(a)(ii)", [(7, (56.0, 160.4, 752.0, 266.8))])

# 场景二：页首段只有分数数字，没有正文 -> 不建区域。
QP_PAGES = {4: {"no": 4, "lines": [line(37.6, 302.8, "4", x1=308.4)],
                "content": (72.4, 37.6, 377.6, 757.6), "disp": (0.0, 0.0, 612.0, 792.0),
                "rot": 0, "derot": None, "bounds": (0.0, 0.0, 612.0, 792.0)}}
QP_EVENTS = [ev(4, 61.2, 1, "3")]
qp_qs, _qp_drop, qp_deepest = O.build_hierarchy(QP_EVENTS, "qp")
print("qp questions:", sorted(qp_qs))
assert O.lead_owner(QP_EVENTS, qp_deepest) == {}, "p4 是首卷第一页，不该有页首段"
check("3", [(4, (70.4, 59.2, 379.6, 759.6))], pages=QP_PAGES, events=QP_EVENTS,
      owner={4: "2"}, qs=qp_qs)

print("bad =", bad)
raise SystemExit(1 if bad else 0)
