"""空 MS 逐条分类（v4）：不依赖旧的几何覆盖判定，直接查 MS 原件文字层里是否存在该题的题号行。

分类：
  parse_omission   原件 MS 里存在该题题号行（→ 索引漏建区域，附可用的 row 区间）
  parent_aggregate 原件里没有该题题号行，但其父题有 → 归入父题聚合区
  no_ms_row        原件里既无该题题号行、也无父题题号行 → 需人工判断（共用区域/真实无独立评分/来源问题）

用法: classify_empty_ms_v4.py [--json OUT]
"""
import json
import os
import re
import sys
from pathlib import Path

import pymupdf

A = os.path.dirname(os.path.abspath(__file__))
BATCH = os.path.dirname(os.path.dirname(A))
sys.path.insert(0, A)
from ms_row_audit import pdf_for, index_path, to_display, text_rows  # noqa: E402

LABEL_X_MAX = 118.0     # 显示坐标下题号列右界（Answer 列内部编号从 x=120 起，必须排除）
TOP_PAD = 1.5
BOT_PAD = 2.0
PART = re.compile(r"\(?([a-z]|[ivx]+)\)?|[0-9]+")


def parts(q):
    return re.findall(r"\(([a-z]|i{1,3}v?|vi{0,3}|ix|x)\)|^(\d+)", q)


def norm(q):
    return re.sub(r"\s+", "", q)


def rows_of_page(pg):
    """返回 (rotation, w, h, labels, all_lines) —— 全部为显示坐标"""
    rot, w, h = pg.rotation, pg.mediabox.width, pg.mediabox.height
    labels, alll = [], []
    for bb, t in text_rows(pg):
        d = to_display(bb, rot, w, h)
        alll.append((d, t))
        if d[0] < LABEL_X_MAX:
            labels.append((d, t))
    alll.sort(key=lambda x: (x[0][1], x[0][0]))
    labels.sort(key=lambda x: (x[0][1], x[0][0]))
    return rot, w, h, labels, alll


def row_span(labels, alll, i, h):
    """第 i 个 label 所在行的显示纵向区间 [y0, y1]

    注意：labels 按 (y, x) 排序，同一视觉行可能有多个 label（如两列同高）。
    必须跳过与本 label 同 y 的 label 再找下一行，否则 limit 会落在 y0 之上，
    产生零高（退化）区间。
    """
    y = labels[i][0][1]
    y0 = max(0.0, y - TOP_PAD)
    nxt = None
    for j in range(i + 1, len(labels)):
        if labels[j][0][1] > y + 0.5:
            nxt = labels[j][0][1]
            break
    limit = (nxt - TOP_PAD) if nxt is not None else h
    if limit <= y0:
        limit = y0 + 0.5
    last = None
    for d, t in alll:
        if d[1] >= y0 - 0.5 and d[3] <= limit + 0.5 and d[0] >= LABEL_X_MAX:
            if last is None or d[3] > last:
                last = d[3]
    y1 = min(limit, (last + BOT_PAD) if last is not None else limit)
    if y1 <= y0:
        y1 = y0 + 0.5
    return round(y0, 1), round(y1, 1)


def disp_to_idx(dy0, dy1, rot, w, h, x0, x1):
    """显示纵向区间 + 显示横向区间 -> 索引 bbox"""
    if rot == 0:
        return [x0, dy0, x1, dy1]
    if rot == 90:
        return [dy0, h - x1, dy1, h - x0]
    raise ValueError(f"rot {rot} 未支持")


def parent_of(q):
    i = q.rfind("(")
    return q[:i].strip() if i > 0 else None


def infer_xspan(idx, doc):
    """从该卷已有区域推断**显示横向**范围 (dx0, dx1)。

    各卷页边距不同（实测 8386 = 62.8..735.2，0478 = 56.8..729.2），
    硬编码会写出错误的横向范围。取出现次数最多的 (dx0, dx1)。
    """
    from collections import Counter
    rot = doc[0].rotation
    h = doc[0].mediabox.height
    c = Counter()
    for q in idx["questions"]:
        for role in ("ms", "qp"):
            for r in (q.get(role) or []):
                b = r["bbox"]
                if rot == 90:
                    c[(round(h - b[3], 1), round(h - b[1], 1))] += 1
                else:
                    c[(round(b[0], 1), round(b[2], 1))] += 1
    if c:
        (x0, x1), _ = c.most_common(1)[0]
        return x0, x1, "inferred"
    return (62.8, 735.2, "fallback") if rot == 90 else (70.8, 534.0, "fallback")


def main():
    out = {"method": "classify_empty_ms_v4.py —— 直接在 MS 原件文字层查找题号行",
           "items": []}
    keys = []
    for p in sorted(Path(BATCH, "indexes").glob("*/*/cie-index.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        keys.append("/".join([d["identity"]["subject"], str(d["identity"]["year"]),
                              d["identity"]["season"], d["identity"]["paper"]]))
    for key in keys:
        idx = json.loads(index_path(key).read_text(encoding="utf-8"))
        empties = [q for q in idx["questions"] if not (q.get("ms") or [])]
        if not empties:
            continue
        pdf = pdf_for(key, "ms")
        if pdf is None:
            for q in empties:
                out["items"].append({"key": key, "q": q["question"],
                                     "class": "ms_pdf_missing", "evidence": str(pdf)})
            continue
        doc = pymupdf.open(pdf)
        dx0, dx1, xsrc = infer_xspan(idx, doc)
        pages = []
        for i in range(doc.page_count):
            pages.append(rows_of_page(doc[i]))
        # 该卷已被现有区域占用的 MS 页 = 真实评分表页。封面/总则/说明页（如 9618 p2、
        # 0580 p3 的 "Unless a particular method..." 编号条目）也含 Question 列编号，
        # 会被误判为 parse_omission，故必须让已知 MS 页优先、其余页单独记为 offpage。
        known = sorted({r["page"] for qq in idx["questions"] for r in (qq.get("ms") or [])})
        order = [p for p in known if 1 <= p <= len(pages)] + \
                [p for p in range(1, len(pages) + 1) if p not in known]

        def find_labels(name):
            """该题号行在**每一页**的首次出现（同一题可跨页，跨页部分也必须有区域）"""
            hits = []
            for pi in order:
                rot, w, h, labels, alll = pages[pi - 1]
                for li, (d, t) in enumerate(labels):
                    if norm(t) == norm(name):
                        y0, y1 = row_span(labels, alll, li, h)
                        hits.append({"page": pi, "rot": rot, "disp": [y0, y1],
                                     "disp_x": [dx0, dx1], "xspan_source": xsrc,
                                     "on_known_ms_page": pi in known,
                                     "idx_bbox_full_width": disp_to_idx(y0, y1, rot, w, h, dx0, dx1)})
                        break
            return hits

        for q in empties:
            hits = find_labels(q["question"])
            onpage = [h for h in hits if h["on_known_ms_page"]]
            rec = {"key": key, "q": q["question"], "qp": q.get("qp"),
                   "parent": parent_of(q["question"]), "known_ms_pages": known}
            if hits:
                rec["class"] = "parse_omission" if onpage else "parse_omission_offpage"
                rec["evidence"] = {"hits": onpage or hits,
                                   "n_pages_hit": len(hits),
                                   "offpage_hits": [h["page"] for h in hits if not h["on_known_ms_page"]]}
            else:
                par = parent_of(q["question"])
                phits = find_labels(par) if par else []
                pon = [h for h in phits if h["on_known_ms_page"]]
                if pon:
                    rec["class"] = "parent_aggregate"
                    rec["evidence"] = {"hits": pon}
                elif phits:
                    rec["class"] = "parent_only_offpage"
                    rec["evidence"] = {"hits": phits}
                else:
                    rec["class"] = "no_ms_row"
                    rec["evidence"] = None
            out["items"].append(rec)
        doc.close()

    from collections import Counter
    out["totals"] = dict(Counter(i["class"] for i in out["items"]))
    out["n"] = len(out["items"])
    js = json.dumps(out, ensure_ascii=False, indent=1)
    dest = os.path.join(A, "deliverables", "empty-ms-classify-v4.json")
    if "--json" in sys.argv:
        dest = sys.argv[sys.argv.index("--json") + 1]
    open(dest, "w", encoding="utf-8").write(js)
    print("n", out["n"], out["totals"])
    for i in out["items"]:
        if i["class"] != "parent_aggregate":
            print(" ", i["class"], i["key"], i["q"], json.dumps(i["evidence"], ensure_ascii=False)[:150])
    print("->", dest)


if __name__ == "__main__":
    main()
