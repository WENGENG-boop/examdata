"""对 64 个已删除的表头带条带做「独立于行检测器」的复核（只读本地 PDF，不联网）。

思路：不依赖题号行检测器的输出，直接在条带的纵向范围内、
Question 列（显示 x ≈ 60..120）以及 Answer 列（显示 x ≈ 120..690）里
取**全部文字行**，看条带内是否出现该题自己的题号或答案文字。

判定：
  qcol_lines  : 条带内 Question 列出现的所有文字（含下一题行号，若其行首落在条带内）
  ans_lines   : 条带内 Answer 列出现的所有文字
  own_label_inside : 条带内 Question 列是否出现该题自身题号
输出 deliverables/ms-header-band-independent-check.json
"""
import json
import os
import sys

import pymupdf

A = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, A)
from ms_row_audit import pdf_for, to_display  # noqa: E402

LIST = os.path.join(A, "deliverables", "ms-header-band-fix-list.json")
OUT = os.path.join(A, "deliverables", "ms-header-band-independent-check.json")

QCOL = (58.0, 118.0)     # 显示 x：Question 列
ACOL = (118.0, 700.0)    # 显示 x：Answer 列
PAD = 1.0

import re  # noqa: E402
HEADERISH = re.compile(
    r"^(PUBLISHED|©|Page \d+ of \d+|Cambridge I[GS]*CSE|Cambridge International|"
    r"May/June \d{4}|October/November \d{4}|February/March \d{4}|"
    r"Question|Answer|Marks|\d{4}/\d+$|.*Mark Scheme.*$)")


def main():
    items = json.load(open(LIST, encoding="utf-8"))["items"]
    docs = {}
    out = []
    for it in items:
        key = it["key"]
        if key not in docs:
            docs[key] = pymupdf.open(pdf_for(key, "ms"))
        pg = docs[key][it["page"] - 1]
        rot, w, h = pg.rotation, pg.mediabox.width, pg.mediabox.height
        b = it["bbox_display"]
        y0, y1 = b[1], b[3]
        qcol, acol = [], []
        for blk in pg.get_text("dict")["blocks"]:
            if blk.get("type") != 0:
                continue
            for ln in blk.get("lines", []):
                db = to_display(tuple(ln["bbox"]), rot, w, h)
                txt = "".join(s["text"] for s in ln.get("spans", [])).strip()
                if not txt:
                    continue
                if db[3] < y0 - PAD or db[1] > y1 + PAD:
                    continue
                if QCOL[0] <= db[0] <= QCOL[1]:
                    qcol.append({"text": txt, "y": round(db[1], 1), "x": round(db[0], 1)})
                elif ACOL[0] <= db[0] <= ACOL[1]:
                    acol.append({"text": txt, "y": round(db[1], 1), "x": round(db[0], 1)})
        own = [t for t in qcol if t["text"] == it["q"]]

        # 残差判定：排除 (a) 页眉/表头类文字；(b) 行首落在条带底边（下一题题号行）
        def residual(lst):
            return [t for t in lst
                    if not HEADERISH.match(t["text"]) and t["y"] < y1 - 1.0]

        res_q, res_a = residual(qcol), residual(acol)
        if own:
            verdict = "own_content_present"
        elif res_q or res_a:
            verdict = "own_content_present"
        else:
            verdict = "clean"
        out.append({
            "key": key, "page": it["page"], "q": it["q"],
            "classification": it["classification"],
            "band_display": b, "rotation": rot,
            "band_bottom": round(y1, 1),
            "qcol_lines": qcol, "ans_lines": acol,
            "own_label_inside": bool(own),
            "residual_qcol": res_q, "residual_ans": res_a,
            "verdict": verdict,
        })
    bad = [o for o in out if o["verdict"] != "clean"]
    json.dump({"count": len(out), "not_clean": len(bad),
               "not_clean_detail": [{"key": o["key"], "page": o["page"], "q": o["q"],
                                     "qcol": o["qcol_lines"], "ans": o["ans_lines"][:6]}
                                    for o in bad],
               "items": out},
              open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("count", len(out), "not_clean", len(bad))
    for o in bad[:20]:
        print(" !", o["key"], "p%d" % o["page"], o["q"], "qcol=", o["qcol_lines"],
              "ans=", [t["text"] for t in o["ans_lines"]][:4])


if __name__ == "__main__":
    main()
