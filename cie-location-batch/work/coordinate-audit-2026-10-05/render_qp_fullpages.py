"""离线渲染 QP 整页图（第 1、5-8 页），用于逐页漏题检查。只读本地原件。"""
from __future__ import annotations

import glob
import hashlib
import os

import fitz

ROOT = r"C:/Users/weo/Desktop/api"
BATCH = os.path.join(ROOT, "cie-location-batch")
OUTDIR = os.path.join(BATCH, "work/coordinate-audit-2026-10-05/visual/0472_2026_Jun_41")
QP_SHA = "4cd9c4040e74082d5a9e027036008928ac588bc16d2ff7ee02cdae495c71600a"


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    pdfs = glob.glob(os.path.join(BATCH, "tmp/0472/2026-Jun-41", "*.pdf"))
    matches = [p for p in pdfs if sha256_file(p) == QP_SHA]
    if len(matches) != 1:
        print("QP original not uniquely found:", matches)
        return 2
    doc = fitz.open(matches[0])
    print("pages:", doc.page_count)
    for pno in [1, 5, 6, 7, 8]:
        page = doc[pno - 1]
        page.set_rotation(0)
        pm = page.get_pixmap(matrix=fitz.Matrix(1.4, 1.4))
        out = os.path.join(OUTDIR, f"qp-p{pno}-full.png")
        pm.save(out)
        print("rendered", pno, pm.width, pm.height, out)
    doc.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
