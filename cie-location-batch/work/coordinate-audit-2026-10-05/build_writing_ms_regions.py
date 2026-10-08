"""为 8238 写作卷（Paper 3x）补建 ms 区域 —— 证据来自 MS 原件文字层（纯离线）。

归属规则（不用硬编码页码，逐卷从标题块推导）：
  * 出现 `TABLE(S) X [and Y] ± Question(s) N [and M] ...` 的页 -> 该页属于这些题；
  * 紧随其后的无标题页 -> 承接上一归属（表格续页）；
  * `Glossary of terms ...` 页 -> 归属清空（参考页，不是某题的评分）；
  * 其余页（封面/通用评分原则/评分说明/等级使用指引）-> 无归属。

区域取"该页内容块的并集 bbox"（排除页眉 x0<=70.5、页脚 x0>=540，排除空块），
再按 PAD 外扩并夹在内容列内。整页属于一题的表格，故区域即该页内容区。

共用题：TABLE D/E/F 同时用于 Question 2 与 Question 3，两题得到**相同**区域，
并在 notes 中写明共用（这是合法的共用评分区域，不是重复计数）。

不改 uncertain（留待逐区域目视核验后由核验流程定论）；无文字层页单独标出待目视。

用法: python build_writing_ms_regions.py [key ...] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import analyze_writing_ms as W  # noqa: E402

sys.path.insert(0, os.path.join(W.BATCH, "tools"))
import batchlib as B  # noqa: E402

PAD = 1.5
X_CLAMP = (60.0, 538.0)
Y_CLAMP = (40.0, 762.0)


def owner_map(res: dict) -> tuple[dict, list]:
    """返回 {page: [q,...]} 与前缀页码列表（题目集）。"""
    owners: dict[int, list] = {}
    cur: list | None = None
    for p in res["pages"]:
        if not p["has_text"]:
            continue
        first = (p["first_content"] or "")
        if first.startswith("Glossary of terms"):
            cur = None
            continue
        withq = [t for t in p["tables"] if t["questions"]]
        if withq:
            qs: list[str] = []
            for t in withq:
                for q in t["questions"].split("and"):
                    q = q.strip()
                    if q and q not in qs:
                        qs.append(q)
            cur = qs
        if cur:
            owners[p["page"]] = list(cur)
    return owners, []


def region_for(p: dict) -> list:
    x0, y0, x1, y1 = p["content_bbox"]
    return [round(max(x0 - PAD, X_CLAMP[0]), 2), round(max(y0 - PAD, Y_CLAMP[0]), 2),
            round(min(x1 + PAD, X_CLAMP[1]), 2), round(min(y1 + PAD, Y_CLAMP[1]), 2)]


def plan(key: str) -> dict:
    res = W.analyze(key)
    if res.get("error"):
        return {"key": key, "error": res["error"]}
    owners = owner_map(res)[0]
    pages = {p["page"]: p for p in res["pages"]}
    no_text = [p["page"] for p in res["pages"] if not p["has_text"]]
    per_q: dict[str, list] = {}
    for q in ("1", "2", "3"):
        regs = []
        for pg in sorted(owners):
            if q in owners[pg]:
                regs.append({"page": pg, "bbox": region_for(pages[pg])})
        per_q[q] = regs
    # 每题的证据行
    ev = {}
    for q, regs in per_q.items():
        lines = []
        for r in regs:
            tabs = ",".join(f"{t['table']}" for t in pages[r["page"]]["tables"]) or "续页"
            lines.append(f"p{r['page']}[{tabs}]")
        ev[q] = lines
    shared = sorted({pg for pg in owners if len(owners[pg]) > 1})
    return {"key": key, "ms_sha256": res["ms_sha256"], "ms_pages": res["ms_pages"],
            "owners": {str(k): v for k, v in sorted(owners.items())},
            "regions": per_q, "evidence": ev, "shared_pages": shared,
            "unclassified_no_text_pages": no_text}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("keys", nargs="*")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    keys = args.keys or W.KEYS
    logs = []
    for key in keys:
        pl = plan(key)
        if pl.get("error"):
            print(f"{key}: ERROR {pl['error']}")
            return 2
        print(f"===== {key}  pages={pl['ms_pages']}  shared_pages={pl['shared_pages']}"
              f"  no_text={pl['unclassified_no_text_pages']}")
        for q in ("1", "2", "3"):
            regs = pl["regions"][q]
            print(f"   Q{q}: {len(regs)} 区域  " +
                  " ".join(f"p{r['page']}{r['bbox']}" for r in regs))
            print(f"        证据: {'; '.join(pl['evidence'][q])}")
        logs.append(pl)
        if args.dry_run:
            continue
        path = W.index_path(key)
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        old_sha = W.sha256_file(path)
        ts = time.strftime("%Y%m%dT%H%M%S")
        bdir = os.path.join(W.BATCH, "work", "coordinate-audit-2026-10-05", "index-backups")
        os.makedirs(bdir, exist_ok=True)
        bpath = os.path.join(bdir, f"{key.replace('/', '-')}-before-writing-ms-{ts}.json")
        shutil.copy2(path, bpath)
        for q in data["questions"]:
            qn = str(q["question"])
            regs = pl["regions"].get(qn)
            if not regs:
                print(f"   !! Q{qn} 无推导区域，跳过（保持原状）")
                continue
            q["ms"] = [{"page": r["page"], "bbox": list(r["bbox"])} for r in regs]
            ev = "; ".join(pl["evidence"][qn])
            sh = "；Q2 与 Q3 共用 TABLES D/E/F，两题区域相同" if pl["shared_pages"] else ""
            q["notes"] = (f"ms 区域由 MS 原件文字层推导：{ev}{sh}。"
                          f"text 为 Windows.Media.Ocr(zh-Hans-CN) 转写，仅供辅助；"
                          f"待逐区域目视核验后定论。")
            if len(q["notes"]) > 2000:
                q["notes"] = q["notes"][:2000]
        tmp = str(path) + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=1)
        os.replace(tmp, path)
        new_sha = W.sha256_file(path)
        pl.update({"index_sha256_before": old_sha, "index_sha256_after": new_sha,
                   "backup": bpath.replace("\\", "/"), "written_at": ts})
        out = os.path.join(W.DELIV, f"writing-ms-regions-{key.replace('/', '_')}-{ts}.json")
        with open(out, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(pl, fh, ensure_ascii=False, indent=1)
        print(f"   写入 {old_sha[:12]} -> {new_sha[:12]}  log={out}")
    if args.dry_run:
        print("(dry-run，未写入)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
