"""通用离线渲染：把某卷某角色的指定页渲染为 PNG（未旋转空间，1.4x）。

用法: python render_pages.py <subject/year/season/paper> <qp|ms> <page,page,...>
只读本地原件；输出到 work/coordinate-audit-2026-10-05/visual/<subj>_<year>_<season>_<paper>/。
"""
from __future__ import annotations

import glob
import os
import sys

import fitz

BATCH = r"C:/Users/weo/Desktop/api/cie-location-batch"
VIS = os.path.join(BATCH, "work/coordinate-audit-2026-10-05/visual")


def main() -> int:
    key = sys.argv[1]
    role = sys.argv[2]
    pages = [int(x) for x in sys.argv[3].split(",")]
    subject, year, season, paper = key.split("/")
    tmp_dir = os.path.join(BATCH, "tmp", subject, f"{year}-{season}-{paper}")
    suffix = "_qp_" if role == "qp" else "_ms_"
    matches = [p for p in glob.glob(os.path.join(tmp_dir, "*.pdf"))
               if suffix in os.path.basename(p)]
    if len(matches) != 1:
        print("PDF not uniquely found:", matches)
        return 2
    outdir = os.path.join(VIS, f"{subject}_{year}_{season}_{paper}")
    os.makedirs(outdir, exist_ok=True)
    doc = fitz.open(matches[0])
    print("pdf:", matches[0], "pages:", doc.page_count)
    for pno in pages:
        if pno < 1 or pno > doc.page_count:
            print("skip out-of-range", pno)
            continue
        page = doc[pno - 1]
        page.set_rotation(0)
        pm = page.get_pixmap(matrix=fitz.Matrix(1.4, 1.4))
        out = os.path.join(outdir, f"{role}-p{pno}-full.png")
        pm.save(out)
        print("rendered", role, pno, pm.width, pm.height)
    doc.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
