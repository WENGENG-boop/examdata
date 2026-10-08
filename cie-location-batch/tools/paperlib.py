"""单卷处理的共享工具：路径、PDF 校验、渲染、裁剪、文字层读取。

坐标约定与提示词一致：
- bbox 一律是「未旋转 PDF、左上原点、points」，page 从 1 起
- 分析范围 = page.rect * page.derotation_matrix
- 渲染 clip = rect * page.rotation_matrix
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import batchlib as B

PAGE_ZOOM = 2.0
CROP_ZOOM = 3.0
MAX_PDF_BYTES = 64 * 1024 * 1024


def _p(path) -> Path:
    return path if isinstance(path, Path) else Path(path)


def load_paper(key: str) -> dict | None:
    papers = B.read_json(B.PAPERS, {}) or {}
    return papers.get(key)


def save_paper(entry: dict) -> None:
    papers = B.read_json(B.PAPERS, {}) or {}
    papers[entry["key"]] = entry
    B.atomic_write_json(B.PAPERS, papers)


def patch_paper(key: str, **fields) -> dict:
    papers = B.read_json(B.PAPERS, {}) or {}
    entry = papers.get(key) or {"key": key}
    entry.update(fields)
    papers[key] = entry
    B.atomic_write_json(B.PAPERS, papers)
    return entry


def set_stage(key: str, stage: str, **fields) -> dict:
    return patch_paper(key, stage=stage, stage_at=B.now_iso(), **fields)


def analysis_bounds(page) -> tuple[float, float, float, float]:
    rect = page.rect * page.derotation_matrix
    return (rect.x0, rect.y0, rect.x1, rect.y1)


def render_clip(page, bbox):
    import pymupdf
    return pymupdf.Rect(bbox) * page.rotation_matrix


def validate_pdf(path) -> dict:
    import pymupdf
    path = _p(path)
    data = path.read_bytes()
    info = {"bytes": len(data), "sha256": B.sha256_bytes(data)}
    if not data.startswith(b"%PDF-"):
        raise ValueError("not a PDF (missing %PDF- magic)")
    if len(data) > MAX_PDF_BYTES:
        raise ValueError(f"PDF exceeds {MAX_PDF_BYTES} bytes")
    with pymupdf.open(stream=data, filetype="pdf") as pdf:
        if pdf.needs_pass:
            raise ValueError("PDF is encrypted")
        if not pdf.page_count:
            raise ValueError("PDF has no pages")
        if pdf.page_count > 400:
            raise ValueError("PDF page limit exceeded")
        info["pages"] = pdf.page_count
    return info


def page_meta(path) -> list[dict]:
    import pymupdf
    path = _p(path)
    out = []
    with pymupdf.open(path) as pdf:
        for i, page in enumerate(pdf):
            bounds = analysis_bounds(page)
            out.append({
                "page": i + 1,
                "rect": [page.rect.x0, page.rect.y0, page.rect.x1, page.rect.y1],
                "rotation": page.rotation,
                "analysis_bounds": list(bounds),
                "text_chars": len(page.get_text() or ""),
            })
    return out


def render_page(path, page_no: int, out_png, zoom: float = PAGE_ZOOM) -> Path:
    import pymupdf
    path, out_png = _p(path), _p(out_png)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    with pymupdf.open(path) as pdf:
        page = pdf[page_no - 1]
        pixmap = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
        pixmap.save(str(out_png))
        pixmap = None
    return out_png


def crop_region(path, page_no: int, bbox, out_png, zoom: float = CROP_ZOOM) -> Path:
    import pymupdf
    path, out_png = _p(path), _p(out_png)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    with pymupdf.open(path) as pdf:
        page = pdf[page_no - 1]
        bounds = analysis_bounds(page)
        x0, y0, x1, y1 = bbox
        if not (bounds[0] <= x0 < x1 <= bounds[2] and bounds[1] <= y0 < y1 <= bounds[3]):
            raise ValueError(f"bbox {bbox} outside analysis bounds {bounds}")
        clip = render_clip(page, bbox)
        pixmap = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), clip=clip, alpha=False)
        pixmap.save(str(out_png))
        pixmap = None
    return out_png


def page_words(path, page_no: int) -> list[dict]:
    import pymupdf
    with pymupdf.open(_p(path)) as pdf:
        page = pdf[page_no - 1]
        words = page.get_text("words")
    return [{"text": w[4], "x0": w[0], "y0": w[1], "x1": w[2], "y1": w[3],
             "block": w[5], "line": w[6], "word_no": w[7]} for w in words]


def page_lines(path: Path, page_no: int) -> list[dict]:
    """按行聚合，保留每行 bbox 与文字，便于定位题号与题干范围。"""
    words = page_words(path, page_no)
    grouped: dict[tuple[int, int], list[dict]] = {}
    for w in words:
        grouped.setdefault((w["block"], w["line"]), []).append(w)
    lines = []
    for (block, line), items in sorted(grouped.items()):
        items.sort(key=lambda w: w["x0"])
        lines.append({
            "block": block, "line": line,
            "text": " ".join(w["text"] for w in items),
            "x0": min(w["x0"] for w in items), "y0": min(w["y0"] for w in items),
            "x1": max(w["x1"] for w in items), "y1": max(w["y1"] for w in items),
        })
    lines.sort(key=lambda l: (round(l["y0"], 1), l["x0"]))
    return lines


def paper_tmp(key: str) -> Path:
    subject, year, season, paper = key.split("/")
    return B.paper_dir(subject, int(year), season, paper)


def viewer_html(paths: list[str], title: str, width: int = 1400) -> str:
    """生成查看页：把若干 PNG 按给定宽度依次排列，便于浏览器截图目视。"""
    imgs = "\n".join(
        f'<figure><figcaption>{p}</figcaption>'
        f'<img src="{p}" style="width:{width}px;display:block"></figure>' for p in paths)
    return (f"<!doctype html><html><head><meta charset='utf-8'><title>{title}</title>"
            "<style>body{margin:0;background:#fff;font:12px sans-serif}"
            "figure{margin:0 0 8px 0}figcaption{background:#eee;padding:2px 6px}"
            "img{image-rendering:auto}</style></head><body>" + imgs + "</body></html>")
