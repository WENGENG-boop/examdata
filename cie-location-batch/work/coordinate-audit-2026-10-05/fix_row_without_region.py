"""修复 ms_row_audit 的 row_without_region：真实题号行没有任何 ms 区域覆盖（跨页续页漏建）。

输入：deliverables/ms-row-audit.json 的 row_without_region 发现（本次实测）。
做法：在该页 Question 列找到该题号行，用 v4 分类器的 row_span 求纵向区间，按该卷已有区域
推断的横向范围换算成 unrotated_pdf_points_top_left 的 bbox，追加为该题在该页的 ms 区域。
**只新增**，不修改/删除已有区域；已有该页区域则跳过。

用法: fix_row_without_region.py [--dry-run] [--keys k1,k2]
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
AUDIT = os.path.join(A, "deliverables", "ms-row-audit.json")
LOG = os.path.join(A, "row-without-region-fix-log.json")
sys.path.insert(0, A)
from classify_empty_ms_v4 import (LABEL_X_MAX, disp_to_idx, infer_xspan,  # noqa: E402
                                  norm, row_span, rows_of_page)
import pymupdf  # noqa: E402
from ms_row_audit import pdf_for  # noqa: E402

DRY = "--dry-run" in sys.argv
ONLY = set(sys.argv[sys.argv.index("--keys") + 1].split(",")) if "--keys" in sys.argv else None


def index_path(key):
    s, y, se, p = key.split("/")
    return os.path.join(BATCH, "indexes", s, f"{y}-{se}-{p}", "cie-index.json")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def main():
    audit = json.loads(open(AUDIT, encoding="utf-8").read())
    plan = {}
    for key, res in audit.items():
        if ONLY and key not in ONLY:
            continue
        for f in res["findings"]:
            if f["type"] == "row_without_region":
                plan.setdefault(key, []).append(f)

    logs = []
    for key, findings in sorted(plan.items()):
        p = index_path(key)
        doc = json.loads(open(p, encoding="utf-8").read())
        old_sha = sha256(p)
        pdf = pdf_for(key, "ms")
        mdoc = pymupdf.open(pdf)
        dx0, dx1, xsrc = infer_xspan(doc, mdoc)
        by_q = {q["question"]: q for q in doc["questions"]}
        log = {"key": key, "path": p, "old_sha256": old_sha, "changes": [], "problems": [],
               "overlaps": []}
        for f in findings:
            pi = f["page"]
            rot, w, h, labels, alll = rows_of_page(mdoc[pi - 1])
            qname = None
            for li, (d, t) in enumerate(labels):
                if abs(d[1] - f["disp"][1]) < 2.0:
                    qname = norm(t)
                    y0, y1 = row_span(labels, alll, li, h)
                    break
            if qname is None:
                log["problems"].append(f"p{pi} 找不到题号行 {f['disp']}")
                continue
            if qname not in by_q:
                log["problems"].append(f"题号 {qname} 不在索引里")
                continue
            bbox = [round(v, 1) for v in disp_to_idx(y0, y1, rot, w, h, dx0, dx1)]
            q = by_q[qname]
            regs = q.get("ms") or []
            if any(r["page"] == pi for r in regs):
                log["problems"].append(f"{qname} p{pi} 已有区域，跳过")
                continue
            regs.append({"page": pi, "bbox": bbox})
            regs.sort(key=lambda r: r["page"])
            q["ms"] = regs
            log["changes"].append({"q": qname, "page": pi, "op": "add", "new": bbox,
                                   "disp": [round(y0, 1), round(y1, 1)], "disp_x": [dx0, dx1],
                                   "src": "ms_row_audit/row_without_region"})
        mdoc.close()
        log["n_changes"] = len(log["changes"])
        if not log["problems"] and not DRY and log["changes"]:
            os.makedirs(BACKUP, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%dT%H%M%S")
            shutil.copy2(p, os.path.join(BACKUP, f"{key.replace('/', '_')}-before-rowfix-{ts}.json"))
            tmp = p + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(doc, fh, ensure_ascii=False, indent=1)
                fh.write("\n")
            os.replace(tmp, p)
            log["new_sha256"] = sha256(p)
        log["applied"] = not DRY
        logs.append(log)
        print(f"--- {key} changes={log['n_changes']} problems={log['problems']}")
        for c in log["changes"]:
            print("   +", c["q"], "p%d" % c["page"], c["new"], "disp", c["disp"])
        if log.get("new_sha256"):
            print(f"    sha {log['old_sha256'][:12]} -> {log['new_sha256'][:12]}")

    if not DRY:
        json.dump({"applied_at": datetime.now().isoformat(timespec="seconds"), "papers": logs},
                  open(LOG, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("log ->", LOG)
    print("== papers", len(logs), "changes", sum(l["n_changes"] for l in logs))


if __name__ == "__main__":
    main()
