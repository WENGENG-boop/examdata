#!/usr/bin/env python
"""Build all re-verification sheets for one paper and print the ordered frame list.

Usage:
    python work/reverify_build_sheets.py <subject> <year> <season> <paper>

Steps:
1. Render every QP/MS page to tmp/<key>/pages/{role}-pNNN.png (2x).
2. Build region stack sheets from the CURRENT index regions (stacksheet.build):
   crops -> tmp/<key>/crops/stack-*.png, sheets -> work/sheets/<slug>-*-stack-*.html
3. Build page grid sheets (sheet.write_sheets, 2 cols, 4 pages per 1000x1000 sheet).
4. Print the ordered frame list (URL + labels) for browser-by-frame visual review.

No network, no index changes, no shared-state changes.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import pymupdf  # noqa: E402
import batchlib as B  # noqa: E402
import paperlib as P  # noqa: E402
import sheet as SH  # noqa: E402
import stacksheet  # noqa: E402


def main() -> int:
    if len(sys.argv) != 5:
        print(__doc__)
        return 2
    subject, year, season, paper = sys.argv[1:5]
    key = f"{subject}/{year}/{season}/{paper}"
    slug = key.replace("/", "-")

    idx_path = B.index_dir(subject, int(year), season, paper) / "cie-index.json"
    data = json.loads(idx_path.read_text(encoding="utf-8"))
    tmp = P.paper_tmp(key)
    pdfs = SH.find_pdfs(tmp)
    if "qp" not in pdfs:
        raise SystemExit(f"缺 QP 原件：{tmp}")
    if any(q.get("ms") for q in data["questions"]) and "ms" not in pdfs:
        raise SystemExit(f"缺 MS 原件：{tmp}")

    # 1) render pages at 2x
    pages_dir = tmp / "pages"
    pages_dir.mkdir(exist_ok=True)
    counts = {}
    for role in ("qp", "ms"):
        pdf = pdfs.get(role)
        if pdf is None:
            continue
        with pymupdf.open(pdf) as doc:
            counts[role] = doc.page_count
            for n, page in enumerate(doc, 1):
                out = pages_dir / f"{role}-p{n:03d}.png"
                page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False).save(str(out))

    # 2) region specs from current index
    qp_spec, ms_spec = [], []
    for q in data["questions"]:
        num = q["question"]
        for r in q["qp"]:
            qp_spec.append({"label": f"Q{num}", "role": "qp",
                            "page": int(r["page"]), "bbox": list(r["bbox"])})
        for r in q["ms"]:
            ms_spec.append({"label": f"M{num}", "role": "ms",
                            "page": int(r["page"]), "bbox": list(r["bbox"])})

    frames: list[tuple[str, str]] = []

    # 3) page grid sheets
    for role in ("qp", "ms"):
        imgs = sorted(pages_dir.glob(f"{role}-p*.png"),
                      key=lambda p: int(re.search(r"-p(\d+)\.png$", p.name).group(1)))
        if not imgs:
            continue
        cells = [{"src": SH.rel_url(img),
                  "caption": f"{role} p{int(re.search(r'-p(\d+)', img.name).group(1))}"}
                 for img in imgs]
        written = SH.write_sheets(cells, 2, f"{slug}-{role}-pages", f"{key} {role} pages")
        for i, p in enumerate(written, 1):
            frames.append((f"/work/sheets/{p.name}", f"{role}-pages-{i}"))

    # 4) region stack sheets
    def add_stacks(paths: list[Path], tag: str) -> None:
        for i, p in enumerate(paths, 1):
            html = p.read_text(encoding="utf-8")
            labels = [lab.split("  [")[0].strip()
                      for lab in re.findall(r"<div class=cap>(.*?)</div>", html)]
            frames.append((f"/work/sheets/{p.name}", f"{tag}-{i} | " + ",".join(labels)))

    if qp_spec:
        add_stacks(stacksheet.build(key, qp_spec, f"{slug}-qp-regions"), "qp-regions")
    if ms_spec:
        add_stacks(stacksheet.build(key, ms_spec, f"{slug}-msreg"), "ms-regions")

    # duplicate region keys would break the record writer; report now
    for tag, spec in (("qp", qp_spec), ("ms", ms_spec)):
        keys = [(s["role"], s["page"], tuple(round(float(v), 1) for v in s["bbox"]))
                for s in spec]
        dupes = sorted({k for k in keys if keys.count(k) > 1})
        if dupes:
            print(f"[警告] {tag} 有重复区域键: {dupes}")

    print(f"帧清单 {key}: {len(frames)} 帧  (qp regions={len(qp_spec)}, ms regions={len(ms_spec)}, "
          f"pages qp={counts.get('qp')}, ms={counts.get('ms')})")
    for i, (url, lab) in enumerate(frames, 1):
        print(f"{i:2}/{len(frames)}  {lab}\n     http://127.0.0.1:8792{url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
