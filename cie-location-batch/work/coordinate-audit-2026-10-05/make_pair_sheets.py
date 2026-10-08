"""把每卷每角色的 -full.png 整页图两两并排合成对照图（页级完整性目视扫描用）。

输出 pairs/<paperdir>/<role>-pair-<a>-<b>.png（含页标签），并写 pairs/manifest.json。
纯离线。单页（奇数末页）也出一张。
"""
from __future__ import annotations

import json
import os

import fitz

ROOT = r"C:/Users/weo/Desktop/api"
AUD = os.path.join(ROOT, "cie-location-batch/work/coordinate-audit-2026-10-05")
VIS = os.path.join(AUD, "visual")
PAIRS = os.path.join(AUD, "pairs")

PAPERS = {
    "8386_2025_Jun_11": {"label": "8386 2025 Jun 11", "qp": 12, "ms": 13},
    "8386_2026_Jun_12": {"label": "8386 2026 Jun 12", "qp": 16, "ms": 15},
    "8386_2026_Jun_13": {"label": "8386 2026 Jun 13", "qp": 16, "ms": 15},
    "0495_2026_Jun_11": {"label": "0495 2026 Jun 11", "qp": 8, "ms": 41},
}

IMG_W, IMG_H = 857, 1109
GAP = 20
TOP = 60


def sheet(out: str, items: list[tuple[str, str]]) -> None:
    doc = fitz.open()
    page = doc.new_page(width=IMG_W * 2 + GAP, height=TOP + IMG_H)
    for i, (path, label) in enumerate(items):
        x = i * (IMG_W + GAP)
        page.insert_image(fitz.Rect(x, TOP, x + IMG_W, TOP + IMG_H), filename=path)
        page.insert_text((x + 8, TOP - 18), label, fontsize=34, fontname="hebo")
    pix = page.get_pixmap(matrix=fitz.Matrix(1, 1))
    pix.save(out)
    doc.close()


def main() -> int:
    os.makedirs(PAIRS, exist_ok=True)
    manifest = {}
    problems = []
    for paperdir, spec in PAPERS.items():
        vdir = os.path.join(VIS, paperdir)
        outdir = os.path.join(PAIRS, paperdir)
        os.makedirs(outdir, exist_ok=True)
        entries = []
        for role in ("qp", "ms"):
            n = spec[role]
            for a in range(1, n + 1, 2):
                b = a + 1
                f1 = os.path.join(vdir, f"{role}-p{a}-full.png")
                if not os.path.isfile(f1):
                    problems.append(f"missing {f1}")
                    continue
                items = [(f1, f"{spec['label']} {role} p{a}")]
                pages = [a]
                if b <= n:
                    f2 = os.path.join(vdir, f"{role}-p{b}-full.png")
                    if os.path.isfile(f2):
                        items.append((f2, f"{spec['label']} {role} p{b}"))
                        pages.append(b)
                    else:
                        problems.append(f"missing {f2}")
                name = f"{role}-pair-{a:02d}-{pages[-1]:02d}.png"
                out = os.path.join(outdir, name)
                sheet(out, items)
                entries.append({"file": f"pairs/{paperdir}/{name}", "role": role,
                                "pages": pages})
        manifest[paperdir] = entries
        print(paperdir, len(entries), "sheets")
    with open(os.path.join(PAIRS, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=1)
    if problems:
        print("PROBLEMS:")
        for p in problems:
            print("  ", p)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
