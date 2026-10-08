#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""0495/2026/Jun/11 空 MS 修复：补建 1(b)（MS p17）与 1(c)（MS p18–p19）独立评分区域。

发现：索引把 1(b)/1(c) 记为 ms=[] + uncertain=true，notes 声称"MS 未单独列出该子题"。
实测（OCR 报告 + 200dpi 行线检测 + 窗口目视）：
  * MS p17 有独立 "1(b)" 评分行（Marks=2，Guidance "Key annotations used…"）；
  * MS p18 起 "1(c)" 评分行（Marks=4），续到 p19（p19 文字层含 "1(c)"）；
  故为"解析遗漏"：propose 阶段 OCR 漏检这两个行标签，其内容被并入父题 1 的行带。
处置：按同卷既有行带约定补建 ms 区域；并把父题 1(a)(iii) 的 p17 行带上界收窄到
1(b) 行起始分隔线，使相邻子题行带不重叠。

幂等 + 先断言后修改 + 备份 + 原子写。任何 mismatch → 整体不写。

用法（从 C:/Users/weo/Desktop/api 执行）：
  examdata/.venv/Scripts/python.exe cie-location-batch/work/coordinate-audit-2026-10-05/fix_0495_q1_ms.py [--dry-run]
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BATCH = Path("C:/Users/weo/Desktop/api/cie-location-batch")
A = BATCH / "work" / "coordinate-audit-2026-10-05"
INDEX = BATCH / "indexes" / "0495" / "2026-Jun-11" / "cie-index.json"
BACKUP_DIR = A / "index-backups"
EVID = "work/coordinate-audit-2026-10-05/0495-2026-11-empty-ms-verdict.json"
TZ = timezone(timedelta(hours=8))

PRE_SHA = "07e8ec2149b3e73bc1594fd3429692d29cdecd667c3ea0d86f5a70cb3ced4b60"
# 200dpi 行线检测（disp_y == unrot x）：
#   p17 表顶 72.9 / 表头下沿 95.9 / 1(a)(iii)|1(b) 分隔 275.8 / 表底 458.5
#   p18 表顶 72.9 / 表头下沿 95.9 / 表底 519.5
#   p19 表顶 73.1 / 表头下沿 96.1 / 表底 301.0

LOG: list[dict] = []


def rec(action: str, status: str, detail: str = "") -> None:
    LOG.append({"action": action, "status": status, "detail": detail})
    print(f"  [{status:8s}] {action} | {detail}", flush=True)


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def region(page: int, bbox: list) -> dict:
    return {"page": page, "bbox": list(bbox)}


def find_q(qs: list, name: str):
    for q in qs:
        if q.get("question") == name:
            return q
    return None


def fix_empty_ms(q: dict, target: list, notes_new: str) -> str:
    if q.get("ms") == target and q.get("uncertain") is False and q.get("notes") == notes_new:
        return "skipped"
    if q.get("ms") == [] and q.get("uncertain") is True:
        q["ms"] = target
        q["uncertain"] = False
        q["notes"] = notes_new
        return "applied"
    return "mismatch"


def region_replace(q: dict, role: str, page: int, before: list, after: list) -> str:
    regions = q.get(role)
    if not isinstance(regions, list):
        return "mismatch"
    for r in regions:
        if r.get("page") == page and r.get("bbox") == list(before):
            r["bbox"] = list(after)
            return "applied"
    for r in regions:
        if r.get("page") == page and r.get("bbox") == list(after):
            return "skipped"
    return "mismatch"


NOTES_1B = (
    "text 来自 Windows.Media.Ocr(zh-Hans-CN) 转录，可能有识别噪声（说明继承自父题 1）；"
    "2026-10-06 复核：MS p17 有独立 '1(b)' 评分行（Marks=2，Guidance 'Key annotations used…'），"
    "旧索引 ms=[] 系 propose 阶段 OCR 漏检该行标签所致的解析遗漏；已按行带约定补建 ms 区域"
    f"（行分隔线 x=275.8 → 表底 x=458.5）并解除 uncertain；见 {EVID}"
)
NOTES_1C = (
    "text 来自 Windows.Media.Ocr(zh-Hans-CN) 转录，可能有识别噪声（说明继承自父题 1）；"
    "2026-10-06 复核：MS p18 起独立 '1(c)' 评分行（Marks=4，Question 栏重复印 '1(c)'），"
    "续至 p19；旧索引 ms=[] 系 propose 阶段 OCR 漏检该行标签所致的解析遗漏；已按行带约定补建"
    f" ms 区域（p18 表头下沿 x=95.9 → 表底 519.5，p19 表头下沿 x=96.1 → 表底 301.0）并解除 uncertain；见 {EVID}"
)

TARGET_1B = [region(17, [275.8, 168.0, 458.5, 729.2])]
TARGET_1C = [region(18, [95.9, 62.8, 519.5, 729.2]), region(19, [96.1, 177.2, 301.0, 735.2])]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    ts = datetime.now(TZ).strftime("%Y%m%dT%H%M%S")
    if not INDEX.exists():
        rec("load", "mismatch", "索引不存在")
        return 1
    cur = sha256_file(INDEX)
    d = json.loads(INDEX.read_bytes().decode("utf-8"))
    old_qs = json.loads(json.dumps(d["questions"]))
    qs = d["questions"]
    ok = True

    for name, target, notes in (("1(b)", TARGET_1B, NOTES_1B), ("1(c)", TARGET_1C, NOTES_1C)):
        q = find_q(qs, name)
        st = "mismatch" if q is None else fix_empty_ms(q, target, notes)
        rec(f"补建 {name} ms 区域并解除 uncertain", st,
            f"target={json.dumps(target, ensure_ascii=False)}")
        ok &= st in ("applied", "skipped")

    q = find_q(qs, "1(a)(iii)")
    st = "mismatch" if q is None else region_replace(
        q, "ms", 17, [101.6, 168.0, 455.2, 729.2], [101.6, 168.0, 275.8, 729.2])
    rec("收窄 1(a)(iii) ms p17 行带（止于 1(b) 行起始）", st, "455.2 → 275.8")
    ok &= st in ("applied", "skipped")

    if not ok:
        rec("WRITE", "mismatch", "存在 mismatch，不写")
        return 1
    if cur == sha256_file(INDEX) and all(x["status"] == "skipped" for x in LOG):
        rec("WRITE", "skipped", f"无需改动，sha={cur[:16]}…")
    elif args.dry_run:
        rec("WRITE", "skipped", "dry-run")
    else:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        bak = BACKUP_DIR / f"0495-2026-Jun-11-before-emptyfix-{ts}.json"
        shutil.copy2(INDEX, bak)
        out = json.dumps(d, indent=2, ensure_ascii=False) + "\n"
        tmp = INDEX.with_suffix(".json.tmp")
        tmp.write_bytes(out.encode("utf-8"))
        json.loads(tmp.read_bytes().decode("utf-8"))
        tmp.replace(INDEX)
        rec("WRITE", "applied", f"backup={bak.name} post_sha={sha256_file(INDEX)}")

    logfile = A / f"emptyfix-0495-qu1-log-{ts}.json"
    if not args.dry_run:
        logfile.write_text(json.dumps(
            {"at": datetime.now(TZ).isoformat(timespec="seconds"), "pre_sha": cur,
             "post_sha": sha256_file(INDEX), "operations": LOG},
            indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"\n日志: {logfile}")

    bad = [x for x in LOG if x["status"] == "mismatch"]
    print(f"\n结论: {'全部完成' if not bad else f'{len(bad)} 个 mismatch'}")
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
