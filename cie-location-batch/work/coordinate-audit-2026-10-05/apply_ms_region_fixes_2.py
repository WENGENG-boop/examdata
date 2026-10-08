"""实写第二批 MS 区域修复：8386/2024/Nov/11、8386/2024/Nov/13、9489/2026/Jun/11。

全部依据本地 MS 原件的**文字层行位置**（probe_rows.py 实测），坐标一律
unrotated_pdf_points_top_left / page_base=1。rot=90 的 8386 卷换算关系已实测：
    idx = [disp_y0, 792 - disp_x1, disp_y1, 792 - disp_x0]
    本卷所有区域 disp_x0=62.8, disp_x1=735.2 → idx = [disp_y0, 56.8, disp_y1, 729.2]
9489 卷 rot=0，idx == disp。

用法: apply_ms_region_fixes_2.py [--dry-run]
"""
import hashlib
import json
import os
import shutil
import sys
from datetime import datetime

A = os.path.dirname(os.path.abspath(__file__))
BATCH = os.path.dirname(os.path.dirname(A))
BACKUP = os.path.join(A, "index-backups")
LOG = os.path.join(A, "ms-region-fixes-2-log.json")

DRY = "--dry-run" in sys.argv

Y0, Y1 = 56.8, 729.2          # 8386 rot=90 卷的固定纵向范围（索引坐标）
X0, X1 = 62.8, 735.2          # 显示横向范围


def R(dy0, dy1):
    """显示纵向区间 -> 8386 rot=90 索引 bbox"""
    return [dy0, Y0, dy1, Y1]


# --- 8386/2024/Nov/11 与 /13：结构完全一致（实测标签 y 位置逐页相同） ---
EDITS_8386 = {
    # q: {page: ("set"|"del", bbox)}
    "1(a)":     {5: ("set", R(102.0, 244.0))},
    "1":        {5: ("set", R(102.0, 495.2)), 6: ("set", R(102.0, 306.0))},
    "1(b)":     {6: ("del", None)},
    "1(b)(ii)": {6: ("del", None)},
    "1(c)":     {6: ("set", R(102.0, 196.4))},
    "2":        {7: ("del", None)},
    "3":        {7: ("set", R(102.0, 372.0)), 8: ("set", R(102.0, 402.0))},
    "3(a)":     {7: ("set", R(102.0, 194.0))},
    "3(a)(i)":  {7: ("set", R(102.0, 124.8))},
    "3(a)(iii)": {7: ("set", R(148.0, 170.8))},
    "3(c)":     {7: ("set", R(240.8, 287.6))},
    "3(d)":     {7: ("set", R(287.6, 372.0))},
    "3(d)(i)":  {7: ("set", R(287.6, 358.0))},
    "4":        {9: ("set", R(102.0, 223.2))},
    "4(c)":     {8: ("set", R(459.6, 509.6))},
}

# --- 9489/2026/Jun/11：rot=0 ---
EDITS_9489 = {
    "1":   {8: ("set", [70.8, 87.6, 534.0, 712.0]),
            9: ("set", [70.8, 87.6, 534.0, 184.5])},
    "1(b)": {8: ("set", [70.8, 87.6, 534.0, 712.0]),
             9: ("set", [70.8, 87.6, 534.0, 184.5])},
}

TARGETS = [
    ("8386/2024/Nov/11", EDITS_8386),
    ("8386/2024/Nov/13", EDITS_8386),
    ("9489/2026/Jun/11", EDITS_9489),
]


def index_path(key):
    s, y, se, p = key.split("/")
    return os.path.join(BATCH, "indexes", s, f"{y}-{se}-{p}", "cie-index.json")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def apply_edits(key, edits, dry):
    p = index_path(key)
    doc = json.loads(open(p, encoding="utf-8").read())
    old_sha = sha256(p)
    log = {"key": key, "path": p, "old_sha256": old_sha, "changes": [], "problems": []}
    by_q = {q["question"]: q for q in doc["questions"]}

    for qname, pages in edits.items():
        if qname not in by_q:
            log["problems"].append(f"题号不存在: {qname}")
            continue
        q = by_q[qname]
        regs = q.get("ms") or []
        for pg, (op, bbox) in sorted(pages.items()):
            cur = [r for r in regs if r["page"] == pg]
            if op == "del":
                if len(cur) != 1:
                    log["problems"].append(f"{qname} p{pg} del 期望 1 条，实际 {len(cur)}")
                    continue
                regs = [r for r in regs if r["page"] != pg]
                log["changes"].append({"q": qname, "page": pg, "op": "del",
                                       "old": cur[0]["bbox"]})
            else:
                if len(cur) > 1:
                    log["problems"].append(f"{qname} p{pg} set 期望 <=1 条，实际 {len(cur)}")
                    continue
                if cur:
                    old = cur[0]["bbox"]
                    if old == bbox:
                        log["changes"].append({"q": qname, "page": pg, "op": "noop",
                                               "bbox": bbox})
                        continue
                    regs = [r for r in regs if r["page"] != pg]
                    log["changes"].append({"q": qname, "page": pg, "op": "replace",
                                           "old": old, "new": bbox})
                else:
                    log["changes"].append({"q": qname, "page": pg, "op": "add", "new": bbox})
                regs.append({"page": pg, "bbox": bbox})
        regs.sort(key=lambda r: r["page"])
        if regs:
            q["ms"] = regs
        else:
            q.pop("ms", None)
            log["problems"].append(f"{qname} 修复后 ms 为空（需人工确认）")

    log["n_changes"] = sum(1 for c in log["changes"] if c["op"] != "noop")
    if log["problems"]:
        log["applied"] = False
        return log

    if not dry:
        os.makedirs(BACKUP, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%dT%H%M%S")
        shutil.copy2(p, os.path.join(BACKUP, f"{key.replace('/', '_')}-before-msfix2-{ts}.json"))
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=1)
            f.write("\n")
        os.replace(tmp, p)
        log["new_sha256"] = sha256(p)
    log["applied"] = True
    return log


def main():
    logs = []
    for key, edits in TARGETS:
        lg = apply_edits(key, edits, DRY)
        logs.append(lg)
        print(f"--- {key}  dry={DRY}  changes={lg['n_changes']}  problems={lg['problems']}")
        for c in lg["changes"]:
            print("   ", json.dumps(c, ensure_ascii=False))
        if lg.get("new_sha256"):
            print(f"    sha {lg['old_sha256'][:12]} -> {lg['new_sha256'][:12]}")
    if not DRY:
        json.dump({"applied_at": datetime.now().isoformat(timespec="seconds"),
                   "dry_run": DRY, "papers": logs},
                  open(LOG, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("log ->", LOG)


if __name__ == "__main__":
    main()
