#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""删除「表头带悬空区域」——按 deliverables/ms-header-band-fix-list.json 执行。

安全规则：
  - 每个文件先整体断言：64 条中属于该文件的每一条都能在索引里精确定位
    （page + bbox 完全一致），任一条 mismatch → 该文件整体不写。
  - 写前把原文件备份到 work/coordinate-audit-2026-10-05/index-backups/
  - 幂等：区域已不存在时记为 skipped。
  - 写后记录 old/new sha256。

用法（从 C:/Users/weo/Desktop/api 执行）：
  examdata/.venv/Scripts/python.exe cie-location-batch/work/coordinate-audit-2026-10-05/apply_header_band_fix.py [--dry-run]
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BATCH = Path("C:/Users/weo/Desktop/api/cie-location-batch")
A = BATCH / "work" / "coordinate-audit-2026-10-05"
LIST = A / "deliverables" / "ms-header-band-fix-list.json"
BACKUPS = A / "index-backups"
TZ = timezone(timedelta(hours=8))


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def index_path(key: str) -> Path:
    subj, year, season, paper = key.split("/")
    return BATCH / "indexes" / subj / f"{year}-{season}-{paper}" / "cie-index.json"


def walk(qs, out):
    for q in qs or []:
        out.append(q)
        walk(q.get("subquestions") or q.get("children") or [], out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    items = json.load(open(LIST, encoding="utf-8"))["items"]
    by_key: dict[str, list] = {}
    for it in items:
        by_key.setdefault(it["key"], []).append(it)

    ts = datetime.now(TZ).strftime("%Y%m%dT%H%M%S")
    log = {"ts": ts, "dry_run": args.dry_run, "papers": []}

    for key, regs in sorted(by_key.items()):
        p = index_path(key)
        old_sha = sha256_file(p)
        doc = json.loads(p.read_text(encoding="utf-8"))
        qs = []
        walk(doc.get("questions") or [], qs)
        by_name: dict[str, list] = {}
        for q in qs:
            by_name.setdefault(q.get("question"), []).append(q)

        # 断言阶段
        plan = []
        problems = []
        for it in regs:
            cands = by_name.get(it["q"]) or []
            want = list(it["index_bbox"])
            hit = None
            for q in cands:
                for r in q.get("ms") or []:
                    if r.get("page") == it["page"] and r.get("bbox") == want:
                        hit = (q, r)
                        break
                if hit:
                    break
            if hit:
                plan.append((it, hit[0], hit[1]))
            else:
                # 幂等：区域已不存在
                still = any(r.get("page") == it["page"] and r.get("bbox") == want
                            for q in cands for r in q.get("ms") or [])
                if still:
                    problems.append(f"{it['q']} p{it['page']} 定位歧义")
                else:
                    plan.append((it, None, None))

        entry = {"key": key, "old_sha256": old_sha, "applied": [], "skipped": [],
                 "problems": problems, "new_sha256": old_sha}
        if problems:
            print(f"[ABORT] {key}: {problems}")
            entry["status"] = "aborted"
            log["papers"].append(entry)
            continue

        for it, q, r in plan:
            if q is None:
                entry["skipped"].append(f"{it['q']} p{it['page']}")
                continue
            q["ms"].remove(r)
            entry["applied"].append({"q": it["q"], "page": it["page"],
                                     "bbox": it["index_bbox"],
                                     "bbox_display": it["bbox_display"],
                                     "classification": it["classification"]})

        if entry["applied"] and not args.dry_run:
            BACKUPS.mkdir(parents=True, exist_ok=True)
            bak = BACKUPS / f"{key.replace('/', '-')}-before-headerband-{ts}.json"
            bak.write_bytes(p.read_bytes())
            entry["backup"] = str(bak)
            p.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            entry["new_sha256"] = sha256_file(p)
        entry["status"] = "dry-run" if args.dry_run else ("applied" if entry["applied"] else "noop")
        print(f"[{entry['status']:8s}] {key} applied={len(entry['applied'])} skipped={len(entry['skipped'])} sha {old_sha[:12]} -> {entry['new_sha256'][:12]}")
        log["papers"].append(entry)

    out = A / "header-band-fix-log.json"
    json.dump(log, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("log ->", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
