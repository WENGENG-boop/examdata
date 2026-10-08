"""把四卷 MS 的页对图重渲染为阅读方向（display 空间，/Rotate 已应用）覆盖原 ms-pair-*.png。

原因：ms PDF 全部页 /Rotate=90，未旋转空间（set_rotation(0) 渲染的 -full.png）文字侧向；
display 空间（默认 get_pixmap）为阅读方向。区域裁剪已有 -disp.png 变体，本脚本补齐页对图。
纯离线；只写 visual/<key>/ms-pN-disp-full.png 与 pairs/<key>/ms-pair-*.png（覆盖同名单页对）。
"""
from __future__ import annotations

import os

import fitz

BATCH = r"C:/Users/weo/Desktop/api/cie-location-batch"
AUD = os.path.join(BATCH, "work/coordinate-audit-2026-10-05")
VIS = os.path.join(AUD, "visual")
PAIRS = os.path.join(AUD, "pairs")

PAPERS = {
    "8386_2025_Jun_11": {"label": "8386 2025 Jun 11", "ms": 13},
    "8386_2026_Jun_12": {"label": "8386 2026 Jun 12", "ms": 15},
    "8386_2026_Jun_13": {"label": "8386 2026 Jun 13", "ms": 15},
    "0495_2026_Jun_11": {"label": "0495 2026 Jun 11", "ms": 41},
}

SCALE = 1.4
GAP = 20
TOP = 60


def find_ms_pdf(paperdir: str) -> str:
    subj, rest = paperdir.split("_", 1)  # "8386_2025_Jun_11" -> 8386 / 2025_Jun_11
    year, season, paper = rest.split("_")
    tmp = os.path.join(BATCH, "tmp", subj, f"{year}-{season}-{paper}")
    import glob

    matches = [
        p
        for p in glob.glob(os.path.join(tmp, "*.pdf"))
        if "_ms_" in os.path.basename(p)
    ]
    if len(matches) != 1:
        raise SystemExit(f"ms pdf not unique for {paperdir}: {matches}")
    return matches[0]


def sheet(out: str, items: list[tuple[str, str]], img_w: int, img_h: int) -> None:
    doc = fitz.open()
    page = doc.new_page(width=img_w * len(items) + GAP * (len(items) - 1),
                        height=TOP + img_h)
    for i, (path, label) in enumerate(items):
        x = i * (img_w + GAP)
        page.insert_image(fitz.Rect(x, TOP, x + img_w, TOP + img_h), filename=path)
        page.insert_text((x + 8, TOP - 18), label, fontsize=34, fontname="hebo")
    pix = page.get_pixmap(matrix=fitz.Matrix(1, 1))
    pix.save(out)
    doc.close()


def main() -> int:
    for paperdir, spec in PAPERS.items():
        vdir = os.path.join(VIS, paperdir)
        outdir = os.path.join(PAIRS, paperdir)
        os.makedirs(outdir, exist_ok=True)
        pdf = find_ms_pdf(paperdir)
        doc = fitz.open(pdf)
        n = spec["ms"]
        assert doc.page_count == n, (paperdir, doc.page_count, n)
        disp_paths: dict[int, str] = {}
        img_w = img_h = 0
        for i in range(n):
            page = doc[i]  # keep /Rotate: get_pixmap applies it -> display orientation
            pm = page.get_pixmap(matrix=fitz.Matrix(SCALE, SCALE))
            out = os.path.join(vdir, f"ms-p{i + 1}-disp-full.png")
            pm.save(out)
            disp_paths[i + 1] = out
            img_w, img_h = pm.width, pm.height
        for a in range(1, n + 1, 2):
            b = min(a + 1, n)
            items = [(disp_paths[p], f"{spec['label']} ms p{p}") for p in range(a, b + 1)]
            name = f"ms-pair-{a:02d}-{b:02d}.png"
            out = os.path.join(outdir, name)
            sheet(out, items, img_w, img_h)
            print(f"{paperdir} {name} cells={img_w}x{img_h} n={len(items)}")
        doc.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
