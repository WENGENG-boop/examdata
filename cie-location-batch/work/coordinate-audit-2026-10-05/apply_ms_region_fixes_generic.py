"""通用 MS 区域补建：读 classify_empty_ms_v4.py 的 parse_omission 证据，写入索引。

原则：
  * 只**新增**空 MS 题的缺失区域，绝不改动/删除已有区域（可逆、零破坏）。
  * 坐标取证据里的 idx_bbox_full_width（unrotated_pdf_points_top_left / page_base=1）。
  * 与**非祖先非后代**题的已有区域重叠时记录为 overlap 警告，交给视觉核验判定，
    不自动改别人。

用法:
  apply_ms_region_fixes_generic.py [--dry-run] [--json CLASSIFY.json] [--keys k1,k2]
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
CLASSIFY = os.path.join(A, "deliverables", "empty-ms-classify-v4.json")
LOG = os.path.join(A, "ms-region-fixes-generic-log.json")

DRY = "--dry-run" in sys.argv
if "--json" in sys.argv:
    CLASSIFY = sys.argv[sys.argv.index("--json") + 1]
ONLY = None
if "--keys" in sys.argv:
    ONLY = set(sys.argv[sys.argv.index("--keys") + 1].split(","))


def index_path(key):
    s, y, se, p = key.split("/")
    return os.path.join(BATCH, "indexes", s, f"{y}-{se}-{p}", "cie-index.json")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ancestors(qname, by_q):
    """题号的祖先链（由近到远）"""
    out = []
    cur = by_q.get(qname)
    while cur is not None and cur.get("parent"):
        out.append(cur["parent"])
        cur = by_q.get(cur["parent"])
    return out


def descendants(qname, by_q):
    out, stack = set(), [qname]
    while stack:
        p = stack.pop()
        for n, q in by_q.items():
            if q.get("parent") == p and n not in out:
                out.add(n)
                stack.append(n)
    return out


def yrange(b):
    """索引 bbox 的纵向（rot=90 用 x 分量，rot=0 用 y 分量由调用方处理）"""
    return b


def apply_key(key, items, dry):
    p = index_path(key)
    doc = json.loads(open(p, encoding="utf-8").read())
    old_sha = sha256(p)
    by_q = {q["question"]: q for q in doc["questions"]}
    rot = None
    log = {"key": key, "path": p, "old_sha256": old_sha, "changes": [], "problems": [],
           "overlaps": []}

    for it in items:
        qname = it["q"]
        hits = it["evidence"]["hits"]
        if qname not in by_q:
            log["problems"].append(f"题号不存在: {qname}")
            continue
        q = by_q[qname]
        regs = q.get("ms") or []

        anc = set(ancestors(qname, by_q))
        desc = descendants(qname, by_q)
        for h in hits:
            pg, bbox = h["page"], [round(v, 1) for v in h["idx_bbox_full_width"]]
            rot = h["rot"]
            if any(r["page"] == pg for r in regs):
                log["problems"].append(f"{qname} p{pg} 已有区域，跳过（不覆盖）")
                continue
            if not (bbox[0] < bbox[2] and bbox[1] < bbox[3]):
                log["problems"].append(f"{qname} bbox 非法: {bbox}")
                continue

            # 重叠检测：同页、非祖先/后代题的已有区域
            for other, oq in by_q.items():
                if other == qname or other in anc or other in desc:
                    continue
                for r in (oq.get("ms") or []):
                    if r["page"] != pg:
                        continue
                    ob = r["bbox"]
                    if rot == 90:
                        a0, a1, b0, b1 = bbox[0], bbox[2], ob[0], ob[2]
                    else:
                        a0, a1, b0, b1 = bbox[1], bbox[3], ob[1], ob[3]
                    if min(a1, b1) - max(a0, b0) > 1.0:
                        log["overlaps"].append({"q": qname, "other": other, "page": pg,
                                                "new": bbox, "existing": ob,
                                                "overlap_pt": round(min(a1, b1) - max(a0, b0), 1)})

            regs.append({"page": pg, "bbox": bbox})
            log["changes"].append({"q": qname, "page": pg, "op": "add", "new": bbox,
                                   "disp": h["disp"],
                                   "src": "classify_empty_ms_v4/parse_omission"})
        if regs:
            regs.sort(key=lambda r: r["page"])
            q["ms"] = regs

    log["n_changes"] = len(log["changes"])
    if log["problems"]:
        log["applied"] = False
        return log

    if not dry:
        os.makedirs(BACKUP, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%dT%H%M%S")
        shutil.copy2(p, os.path.join(BACKUP, f"{key.replace('/', '_')}-before-msfix-generic-{ts}.json"))
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=1)
            f.write("\n")
        os.replace(tmp, p)
        log["new_sha256"] = sha256(p)
    log["applied"] = True
    return log


def main():
    cls = json.loads(open(CLASSIFY, encoding="utf-8").read())
    by_key = {}
    for it in cls["items"]:
        if it["class"] != "parse_omission":
            continue
        if ONLY and it["key"] not in ONLY:
            continue
        by_key.setdefault(it["key"], []).append(it)

    logs = []
    for key in sorted(by_key):
        lg = apply_key(key, by_key[key], DRY)
        logs.append(lg)
        print(f"--- {key}  dry={DRY}  changes={lg['n_changes']}  problems={lg['problems']}"
              f"  overlaps={len(lg['overlaps'])}")
        for c in lg["changes"]:
            print("   +", c["q"], "p%d" % c["page"], c["new"])
        for o in lg["overlaps"]:
            print("   !overlap", o["q"], "vs", o["other"], "p%d" % o["page"], o["overlap_pt"])
        if lg.get("new_sha256"):
            print(f"    sha {lg['old_sha256'][:12]} -> {lg['new_sha256'][:12]}")

    if not DRY:
        json.dump({"applied_at": datetime.now().isoformat(timespec="seconds"),
                   "dry_run": DRY, "source": os.path.basename(CLASSIFY), "papers": logs},
                  open(LOG, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("log ->", LOG)
    tot = sum(l["n_changes"] for l in logs)
    print(f"== papers {len(logs)}  changes {tot}  problems "
          f"{sum(len(l['problems']) for l in logs)}  overlaps {sum(len(l['overlaps']) for l in logs)}")


if __name__ == "__main__":
    main()
