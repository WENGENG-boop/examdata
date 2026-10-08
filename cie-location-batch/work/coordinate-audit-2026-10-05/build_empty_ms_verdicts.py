"""生成空 MS 分类的旁侧验收日志（Schema 不允许 question 加自定义字段，理由只能放这里）。

输入：
  deliverables/empty-ms-classify-v4.json     最新分类（本次实测）
  ms-region-fixes-2-log.json                 第一批 15 条区域补建（8386/2024/Nov/11|13, 9489/2026/Jun/11）
  ms-region-fixes-generic-log.json           第二批 77 条区域补建（13 卷）
输出：
  deliverables/empty-ms-verdicts.json
"""
import hashlib
import json
import os
from datetime import datetime

A = os.path.dirname(os.path.abspath(__file__))
BATCH = os.path.dirname(os.path.dirname(A))
D = os.path.join(A, "deliverables")

METHOD_EVOLUTION = [
    {"version": "v1", "file": "classify_empty_ms.py",
     "method": "按已有区域几何覆盖判定",
     "defect": "把「该题号行落在别的题的区域里」误判为已覆盖，且不查原件文字层"},
    {"version": "v2", "file": "classify_empty_ms_v2.py",
     "method": "加入 MS 原件文字层行匹配",
     "defect": "题号列阈值过宽，把 Answer 列内部编号（显示 x≈120）当成题号行"},
    {"version": "v3", "file": "classify_empty_ms_v3.py",
     "method": "收紧题号列 + 原件行匹配",
     "defect": "仍依赖几何覆盖做归属；父/兄弟分支覆盖时把漏建判成已覆盖"},
    {"version": "v4", "file": "classify_empty_ms_v4.py",
     "method": "只用 MS 原件文字层；题号列显示 x<118；行区间取「本 label 行正文到下一 label 行」；"
               "横向范围按卷从已有区域众数推断；只承认落在**已知 MS 页**（被现有区域占用过的页）上的命中",
     "fixed": ["同 y 双 label 造成的零高退化区间",
               "硬编码 62.8/735.2 导致 0478 等卷横向范围错误（实测 0478=56.8..729.2）",
               "把总则/说明页（9618 p2、0580 p3 的 'Unless a particular method…' 编号条目）"
               "当成题目题号行的假阳性"]},
]

MANUAL_NOTE = {
    "parse_omission_offpage":
        "命中页不在该卷任何已有区域占用的页面上 —— 经人工查看为总则/说明页的编号条目"
        "（9618/2026/Jun/11 p2「General marking principles」编号 1–6；"
        "0580/2024/Jun/11 p3「Unless a particular method has been specified…」编号 1–6），"
        "**不是**该卷题号，不得据此建区域。真实 MS 位于已知 MS 页（9618 为 p5–p17，0580 为 p4–p7），"
        "但这些题的题号行在真实 MS 页上不存在 → 仍需视觉核验原件后才能定论。",
    "parent_only_offpage":
        "该题自身无题号行；父题题号行只在非 MS 页命中（同为说明页），证据不可用 → 待视觉核验。",
    "no_ms_row":
        "该题与父题在已知 MS 页均无题号行 → 待视觉核验（可能是共用评分区域、真实无独立评分或原件版式特殊）。",
}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def index_path(key):
    s, y, se, p = key.split("/")
    return os.path.join(BATCH, "indexes", s, f"{y}-{se}-{p}", "cie-index.json")


def main():
    cls = json.loads(open(os.path.join(D, "empty-ms-classify-v4.json"), encoding="utf-8").read())
    applied = {}
    for fn in ("ms-region-fixes-2-log.json", "ms-region-fixes-generic-log.json"):
        p = os.path.join(A, fn)
        if not os.path.exists(p):
            continue
        lg = json.loads(open(p, encoding="utf-8").read())
        for paper in lg["papers"]:
            if not paper.get("applied"):
                continue
            for c in paper["changes"]:
                if c["op"] == "noop":
                    continue
                applied[(paper["key"], c["q"])] = {
                    "log": fn, "op": c["op"], "page": c["page"],
                    "bbox": c.get("new"), "old": c.get("old"),
                    "paper_old_sha256": paper["old_sha256"],
                    "paper_new_sha256": paper.get("new_sha256")}

    items = []
    for it in cls["items"]:
        key, q = it["key"], it["q"]
        rec = {
            "key": key, "question": q, "parent": it["parent"],
            "class": it["class"],
            "ms_document_sha256": None,
            "evidence": it.get("evidence"),
            "index_sha256_now": None,
            "action": None,
        }
        p = index_path(key)
        if os.path.exists(p):
            rec["index_sha256_now"] = sha256(p)
            doc = json.loads(open(p, encoding="utf-8").read())
            for d in doc.get("documents", []):
                if d["role"] == "ms":
                    rec["ms_document_sha256"] = d["sha256"]
            cur = [x for x in doc["questions"] if x["question"] == q]
            rec["ms_regions_now"] = (cur[0].get("ms") or []) if cur else None
        a = applied.get((key, q))
        if a:
            rec["action"] = {"type": "region_added", **a}
        elif it["class"] in MANUAL_NOTE:
            rec["action"] = {"type": "manual_review_required",
                             "reason": MANUAL_NOTE[it["class"]]}
        items.append(rec)

    out = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "scope": "全部 63 份索引的空 MS 记录（按当前索引重算，非 2026-10-05 快照的 384 条）",
        "counts": cls["totals"],
        "n": cls["n"],
        "method": cls["method"],
        "method_evolution": METHOD_EVOLUTION,
        "manual_classes": MANUAL_NOTE,
        "note_on_schema": "cie-index-schema.json 的 question 为 additionalProperties:false，"
                          "无法在索引内记录理由字段；本条日志即理由与证据的旁侧验收记录。",
        "prior_batch_already_fixed": [],
        "items": items,
    }
    # 第一批已修复的 15 条：它们已不在「当前空 MS」集合里，单列以便追溯
    p1 = os.path.join(A, "ms-region-fixes-2-log.json")
    if os.path.exists(p1):
        lg = json.loads(open(p1, encoding="utf-8").read())
        for paper in lg["papers"]:
            for c in paper["changes"]:
                if c["op"] == "noop":
                    continue
                out["prior_batch_already_fixed"].append({
                    "key": paper["key"], "question": c["q"], "op": c["op"],
                    "page": c["page"], "old": c.get("old"), "new": c.get("new"),
                    "class": "parse_omission",
                    "reason": "MS 原件文字层存在该题题号行，索引漏建区域（第一批，"
                              "标签 y 与正文区间见 ms-region-fixes-2-log.json 与 probe 实测）",
                    "log": "ms-region-fixes-2-log.json",
                    "paper_new_sha256": paper.get("new_sha256")})
    dest = os.path.join(D, "empty-ms-verdicts.json")
    open(dest, "w", encoding="utf-8").write(json.dumps(out, ensure_ascii=False, indent=1))
    from collections import Counter
    print("n", out["n"], out["counts"])
    print("actions:", dict(Counter((i["action"] or {}).get("type") for i in items)))
    print("->", dest)


if __name__ == "__main__":
    main()
