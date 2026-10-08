"""从原 PDF 按索引坐标渲染逐区域裁剪图与整页标注图，供浏览器目视核验（纯离线）。

坐标系统 unrotated_pdf_points_top_left、page_base=1：用 page.set_rotation(0) 把页面
还原到未旋转空间后再按 bbox 裁剪，保证裁剪用的就是索引声明的那套坐标。

输出：
  work/coordinate-audit-2026-10-05/visual/<key>/<role>-p<page>-<qid>.png   紧贴 bbox 的裁剪
  work/coordinate-audit-2026-10-05/visual/<key>/<role>-p<page>-<qid>-page.png 整页 + 红框
  work/coordinate-audit-2026-10-05/visual/<key>/index.html                 目视用索引页
用法：python render_regions.py <subject>/<year>/<season>/<paper> [scale]
"""
from __future__ import annotations

import glob
import hashlib
import html
import json
import os
import sys

import fitz

ROOT = r"C:/Users/weo/Desktop/api"
BATCH = os.path.join(ROOT, "cie-location-batch")
OUTROOT = os.path.join(BATCH, "work/coordinate-audit-2026-10-05/visual")


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    key = sys.argv[1]
    scale = float(sys.argv[2]) if len(sys.argv) > 2 else 2.0
    subject, year, season, paper = key.split("/")

    idx_path = os.path.join(BATCH, "indexes", subject, f"{year}-{season}-{paper}",
                            "cie-index.json")
    index = json.load(open(idx_path, encoding="utf-8"))
    tmp_dir = os.path.join(BATCH, "tmp", subject, f"{year}-{season}-{paper}")
    pdfs = glob.glob(os.path.join(tmp_dir, "*.pdf"))
    by_sha = {sha256_file(p): p for p in pdfs}

    outdir = os.path.join(OUTROOT, key.replace("/", "_"))
    os.makedirs(outdir, exist_ok=True)

    manifest = []
    for doc in index["documents"]:
        role, sha = doc["role"], doc["sha256"]
        if sha not in by_sha:
            manifest.append({"role": role, "status": "original_missing", "sha256": sha})
            continue
        docpdf = fitz.open(by_sha[sha])
        for page in docpdf:
            rotation = page.rotation
            rot_matrix = page.rotation_matrix      # 必须在 set_rotation(0) 之前取
            page.set_rotation(0)          # 回到未旋转空间
            mb = page.mediabox
            for q in index["questions"]:
                for i, r in enumerate(q.get(role) or []):
                    if r["page"] != page.number + 1:
                        continue
                    rect = fitz.Rect(*r["bbox"])
                    base = f"{role}-p{r['page']}-q{q['question'].replace('(','').replace(')','')}-r{i}"
                    crop_png = os.path.join(outdir, base + ".png")
                    pm = page.get_pixmap(clip=rect, matrix=fitz.Matrix(scale, scale))
                    pm.save(crop_png)
                    # 展示朝向（已旋转空间）的同一区域，便于阅读内容；几何权威仍是未旋转裁剪。
                    disp_png = None
                    disp_rect = (rect * rot_matrix) if rotation % 360 else rect
                    if rotation % 360:
                        page.set_rotation(rotation)
                        dpm = page.get_pixmap(clip=disp_rect,
                                              matrix=fitz.Matrix(scale, scale))
                        disp_png = os.path.join(outdir, base + "-disp.png")
                        dpm.save(disp_png)
                        page.set_rotation(0)
                        page.draw_rect(rect, color=(1, 0, 0), width=1.5)
                    else:
                        page.draw_rect(rect, color=(1, 0, 0), width=1.5)
                    full_png = os.path.join(outdir, base + "-page.png")
                    page.get_pixmap(matrix=fitz.Matrix(scale * 0.7, scale * 0.7)).save(full_png)
                    manifest.append({
                        "role": role, "question": q["question"], "region_index": i,
                        "page": r["page"], "bbox": r["bbox"],
                        "page_rotation_original": rotation,
                        "mediabox": [mb.x0, mb.y0, mb.x1, mb.y1],
                        "crop": os.path.relpath(crop_png, outdir).replace("\\", "/"),
                        "crop_display": (os.path.relpath(disp_png, outdir).replace("\\", "/")
                                         if disp_png else None),
                        "page_image": os.path.relpath(full_png, outdir).replace("\\", "/"),
                        "crop_size_px": [pm.width, pm.height],
                        "uncertain": q.get("uncertain"),
                        "marks": q.get("marks"),
                        "parent": q.get("parent"),
                    })
        docpdf.close()

    with open(os.path.join(outdir, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump({"key": key, "scale": scale, "regions": manifest}, fh,
                  ensure_ascii=False, indent=2)

    rows = []
    for m in manifest:
        if "crop" not in m:
            rows.append(f"<p>MISSING ORIGINAL: {html.escape(m['role'])}</p>")
            continue
        rows.append(
            f'<div class="card"><h3>{m["role"]} · Q{m["question"]} · 区域{m["region_index"]}'
            f' · 第{m["page"]}页 · bbox {m["bbox"]} · 原页旋转 {m["page_rotation_original"]}°'
            f' · 裁剪 {m["crop_size_px"][0]}×{m["crop_size_px"][1]}px</h3>'
            f'<div class="imgs"><img src="{m["crop"]}">'
            f'<img src="{m["page_image"]}"></div></div>')
    doc = ("<!doctype html><meta charset=utf-8><title>" + html.escape(key) +
           "</title><style>body{font-family:sans-serif;margin:8px}"
           ".card{border:1px solid #ccc;margin:10px 0;padding:6px}"
           "h3{margin:2px 0;font-size:13px}"
           ".imgs{display:flex;gap:12px;align-items:flex-start}"
           ".imgs img{max-width:100%;border:1px solid #999}</style>"
           f"<h2>{html.escape(key)} · {len(manifest)} 个区域 · scale={scale}</h2>"
           + "\n".join(rows))
    with open(os.path.join(outdir, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(doc)

    print(json.dumps({"key": key, "outdir": outdir.replace("\\", "/"),
                      "regions_rendered": sum(1 for m in manifest if "crop" in m),
                      "manifest_entries": len(manifest)},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
