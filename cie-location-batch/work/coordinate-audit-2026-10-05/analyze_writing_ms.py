"""分析 8238 写作卷（Paper 3x）MS 的"表格→题目"归属，为补建 ms 区域提供证据（纯离线）。

背景：这 5 卷 MS 每页整体属于一个（或一组共用）题：TABLE A/B/C -> Q1；TABLE D/E/F -> Q2 与 Q3 共用。
本脚本逐页扫描文本块，找出 `TABLE(S) ... ± Question(s) ...` 标题块，输出页级归属与内容 bbox；
无文字层页单独标出（须目视）。不写任何索引。

用法: python analyze_writing_ms.py [key ...]   （默认 5 卷；输出 deliverables/writing-ms-<slug>.json）
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import re
import sys

import fitz

BATCH = r"C:/Users/weo/Desktop/api/cie-location-batch"
DELIV = os.path.join(BATCH, "work", "coordinate-audit-2026-10-05", "deliverables")
KEYS = ["8238/2025/Jun/32", "8238/2025/Nov/31", "8238/2025/Nov/32",
        "8238/2025/Nov/33", "8238/2026/Jun/32"]

HEAD_X_LO, FOOT_X_HI = 70.5, 540.0          # 页眉块 x0<=70.5；页脚块 x0>=540
CONTENT_X_LO, CONTENT_X_HI = 60.0, 535.0    # 内容列 x 带（含 68.9 的分值列，排除页眉/页脚）
TITLE_RE = re.compile(r"^TABLES?\s+([A-F])\b.*?\u00b1\s*(.*)$", re.S)
QS_RE = re.compile(r"Questions?\s+([\d\s,and]+)")


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def index_path(key: str) -> str:
    s, y, se, p = key.split("/")
    return os.path.join(BATCH, "indexes", s, f"{y}-{se}-{p}", "cie-index.json")


def ms_original(key: str) -> tuple[str, str]:
    idx = json.load(open(index_path(key), encoding="utf-8"))
    ms_sha = next(d["sha256"] for d in idx["documents"] if d["role"] == "ms")
    tmpdir = os.path.join(BATCH, "tmp", key.split("/")[0],
                          f"{key.split('/')[1]}-{key.split('/')[2]}-{key.split('/')[3]}")
    for p in glob.glob(os.path.join(tmpdir, "*.pdf")):
        if sha256_file(p) == ms_sha:
            return ms_sha, p
    return ms_sha, ""


def norm(s: str) -> str:
    return " ".join(s.split())


def analyze(key: str) -> dict:
    ms_sha, path = ms_original(key)
    res = {"key": key, "ms_sha256": ms_sha, "ms_original": path}
    if not path:
        res["error"] = "ms_original_missing"
        return res
    doc = fitz.open(path)
    res["ms_pages"] = doc.page_count
    pages = []
    for pno in range(doc.page_count):
        page = doc[pno]
        blocks = [(b[0], b[1], b[2], b[3], norm(b[4])) for b in page.get_text("blocks")]
        content = [b for b in blocks if CONTENT_X_LO <= b[0] <= CONTENT_X_HI
                   and FOOT_X_HI > b[0] and b[4]]
        titles = []
        for x0, y0, x1, y1, t in content:
            m = TITLE_RE.match(t)
            if m:
                qs = QS_RE.search(t)
                titles.append({"table": m.group(1), "text": t,
                               "questions": (qs.group(1).replace(" ", "")
                                             if qs else None),
                               "bbox": [round(x0, 2), round(y0, 2),
                                        round(x1, 2), round(y1, 2)]})
        bbox = None
        if content:
            bbox = [round(min(b[0] for b in content), 2),
                    round(min(b[1] for b in content), 2),
                    round(max(b[2] for b in content), 2),
                    round(max(b[3] for b in content), 2)]
        first = content[0][4][:90] if content else None
        pages.append({"page": pno + 1, "blocks": len(blocks), "has_text": bool(content),
                      "content_bbox": bbox, "first_content": first, "tables": titles})
    res["pages"] = pages
    doc.close()
    return res


def main() -> int:
    os.makedirs(DELIV, exist_ok=True)
    keys = sys.argv[1:] or KEYS
    for key in keys:
        res = analyze(key)
        slug = key.replace("/", "_")
        with open(os.path.join(DELIV, f"writing-ms-{slug}.json"), "w",
                  encoding="utf-8", newline="\n") as fh:
            json.dump(res, fh, ensure_ascii=False, indent=1)
        print(f"===== {key}  pages={res.get('ms_pages')} err={res.get('error')}")
        for p in res.get("pages", []):
            tabs = ",".join(f"{t['table']}->Q{t['questions']}" for t in p["tables"])
            print(f"  p{p['page']:>2} txt={int(p['has_text'])} bbox={p['content_bbox']} "
                  f"tables=[{tabs}] first={(p['first_content'] or '')[:60]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
