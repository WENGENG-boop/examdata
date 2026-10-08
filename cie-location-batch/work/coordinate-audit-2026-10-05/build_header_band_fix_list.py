"""构建「表头带悬空区域」待删除清单（只读索引 + 本地墨迹证据，不联网）。

输入:
  deliverables/ms-band-ink.json          条带内墨迹证据（64 条）
  indexes/<subj>/<year>-<season>-<paper>/cie-index.json
输出:
  deliverables/ms-header-band-fix-list.json

每条含:
  key/page/q/bbox/rotation/header_bottom/lines_below_header/drawings_below_header
  /next_row_below/text_inside
  ms_regions_other_pages : 该题在其它页的 ms 区域（用于确认删除后本题仍有定位）
  ms_regions_total       : 该题 ms 区域总数
  classification         : header_only | header_plus_borders | eats_next_row
"""
import json
import os
import sys

A = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, A)
from ms_row_audit import index_path, to_display, pdf_for  # noqa: E402
import pymupdf  # noqa: E402

INK = os.path.join(A, "deliverables", "ms-band-ink.json")
OUT = os.path.join(A, "deliverables", "ms-header-band-fix-list.json")


def classify(r):
    lb = r.get("lines_below_header") or []
    db = r.get("drawings_below_header") or 0
    if lb:
        return "eats_next_row"
    if db:
        return "header_plus_borders"
    return "header_only"


def walk_questions(questions, out):
    for q in questions or []:
        out.append(q)
        walk_questions(q.get("subquestions") or q.get("children") or [], out)


def main():
    ink = json.load(open(INK, encoding="utf-8"))
    idx_cache = {}
    items = []
    for r in ink["regions"]:
        key = r["key"]
        if key not in idx_cache:
            idx_cache[key] = json.loads(index_path(key).read_text(encoding="utf-8"))
        idx = idx_cache[key]
        qs = []
        walk_questions(idx.get("questions") or [], qs)
        target = [q for q in qs if q.get("question") == r["q"]]
        regions = []
        for q in target:
            for reg in q.get("ms") or []:
                regions.append({"page": reg.get("page"), "bbox": reg.get("bbox")})
        doc = pymupdf.open(pdf_for(key, "ms"))
        pg = doc[r["page"] - 1]
        rot, w, h = pg.rotation, pg.mediabox.width, pg.mediabox.height
        target_disp = [round(v, 2) for v in r["bbox"]]

        def disp_of(reg):
            return [round(v, 2) for v in to_display(tuple(reg["bbox"]), rot, w, h)]

        this = [x for x in regions
                if x["page"] == r["page"] and disp_of(x) == target_disp]
        others = [x for x in regions if x not in this]
        items.append({
            "key": key,
            "page": r["page"],
            "q": r["q"],
            "bbox_display": r["bbox"],
            "index_bbox": this[0]["bbox"] if this else None,
            "rotation": r["rotation"],
            "header_bottom": r.get("header_bottom"),
            "lines_below_header": r.get("lines_below_header") or [],
            "drawings_below_header": r.get("drawings_below_header") or 0,
            "images": r.get("images") or 0,
            "next_row_below": r.get("next_row_below"),
            "text_inside": r.get("text_inside") or [],
            "above_all_rows": r.get("above_all_rows"),
            "n_questions_matching": len(target),
            "ms_regions_total": len(regions),
            "ms_regions_other_pages": others,
            "region_is_in_index": bool(this),
            "classification": classify(r),
        })

    from collections import Counter
    summary = {
        "count": len(items),
        "by_classification": dict(Counter(i["classification"] for i in items)),
        "by_paper": dict(Counter(i["key"] for i in items)),
        "q_missing_after_delete": [i["key"] + " p%d q=%s" % (i["page"], i["q"])
                                   for i in items if not i["ms_regions_other_pages"]],
        "not_found_in_index": [i["key"] + " p%d q=%s" % (i["page"], i["q"])
                               for i in items if not i["region_is_in_index"]],
    }
    json.dump({"summary": summary, "items": items},
              open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
