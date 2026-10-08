"""离线探针：给定 key + role + page，dump 该页所有文字块坐标与文本（未旋转空间）。

用法：python probe_blocks.py "8386/2025/Jun/11" ms 8
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import sys

import fitz

ROOT = r"C:/Users/weo/Desktop/api"
BATCH = os.path.join(ROOT, "cie-location-batch")


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    key, role, page_no = sys.argv[1], sys.argv[2], int(sys.argv[3])
    subject, year, season, paper = key.split("/")
    idx_path = os.path.join(BATCH, "indexes", subject, f"{year}-{season}-{paper}",
                            "cie-index.json")
    index = json.loads(open(idx_path, encoding="utf-8").read())
    tmp_dir = os.path.join(BATCH, "tmp", subject, f"{year}-{season}-{paper}")
    by_sha = {sha256_file(p): p for p in glob.glob(os.path.join(tmp_dir, "*.pdf"))}
    sha = {d["role"]: d["sha256"] for d in index["documents"]}[role]
    doc = fitz.open(by_sha[sha])
    page = doc[page_no - 1]
    print(f"# {key} {role} p{page_no}  rect(before)={page.rect} rotation={page.rotation}")
    page.set_rotation(0)
    print(f"# after set_rotation(0): rect={page.rect} rotation={page.rotation}")
    blocks = page.get_text("blocks")
    print(f"# blocks={len(blocks)}")
    for b in blocks:
        x0, y0, x1, y1, txt = b[0], b[1], b[2], b[3], b[4]
        t = " ".join(txt.split())
        print(f"  [{x0:7.1f},{y0:7.1f},{x1:7.1f},{y1:7.1f}] {t[:110]!r}")
    print("# --- rawdict spans (first 40) ---")
    raw = page.get_text("rawdict")
    n = 0
    for blk in raw.get("blocks", []):
        for line in blk.get("lines", []):
            for span in line.get("spans", []):
                txt = "".join(ch["c"] for ch in span.get("chars", []))
                if not txt.strip():
                    continue
                x0, y0, x1, y1 = span["bbox"]
                print(f"  S[{x0:7.1f},{y0:7.1f},{x1:7.1f},{y1:7.1f}] {txt[:90]!r}")
                n += 1
                if n >= 40:
                    return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
