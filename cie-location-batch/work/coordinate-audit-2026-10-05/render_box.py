"""渲染任意 bbox 的裁剪图（未旋转空间 + 显示态）用于目视核验，纯离线。

用法: python render_box.py <pdf> <page_base1> x0 y0 x1 y1 <outdir> <label> [scale]

输出 <outdir>/<label>.png（未旋转空间裁剪，几何权威）与
<outdir>/<label>-disp.png（若页面有旋转，附显示方向裁剪便于阅读）。
"""
from __future__ import annotations

import os
import sys

import fitz


def main() -> int:
    if len(sys.argv) < 9:
        print(__doc__)
        return 2
    pdf_path, page_no = sys.argv[1], int(sys.argv[2])
    x0, y0, x1, y1 = (float(v) for v in sys.argv[3:7])
    outdir, label = sys.argv[7], sys.argv[8]
    scale = float(sys.argv[9]) if len(sys.argv) > 9 else 2.0
    os.makedirs(outdir, exist_ok=True)
    doc = fitz.open(pdf_path)
    page = doc[page_no - 1]
    rot = page.rotation
    rotm = page.rotation_matrix
    page.set_rotation(0)
    rect = fitz.Rect(x0, y0, x1, y1)
    pm = page.get_pixmap(clip=rect, matrix=fitz.Matrix(scale, scale))
    raw = os.path.join(outdir, label + ".png")
    pm.save(raw)
    print(raw)
    if rot % 360:
        disp_rect = rect * rotm
        page.set_rotation(rot)
        dpm = page.get_pixmap(clip=disp_rect, matrix=fitz.Matrix(scale, scale))
        disp = os.path.join(outdir, label + "-disp.png")
        dpm.save(disp)
        print(disp)
    doc.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
