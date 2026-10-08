"""密集竖排裁剪表：把多个区域裁剪按原始宽高比竖直堆叠，一张快照核验约 20 个区域。

和 `sheet.py crops` 的区别：`sheet.py` 用固定方格子（每格 500px，宽高比 24:1 的
题干会被压成一条细线），这里让每个裁剪保持自己的宽高比、统一占满 1000 CSS px 宽，
因此一行题干也能拿到约 1000x53 CSS px，文字清晰可读。

用法：
    python tools/stacksheet.py <key> --spec spec.json [--name base] [--role qp]
    python tools/stacksheet.py <key> --spec spec.json --ms      # 区域来自 MS 原件

spec 为 `[{"label","role","page","bbox"}, ...]`，`role` 决定用 QP 还是 MS 原件。
HTML 写到 work/sheets/，URL 逐行打印到 stdout。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import batchlib as B
import paperlib as P

SHEET_CSS = 1000          # 每张表 1000x1000 CSS px（设备像素比 2 -> 2000x2000）
TARGET_PX = 2 * SHEET_CSS  # 裁剪目标宽度（设备像素），正好 1:1 显示
ZOOM_MIN, ZOOM_MAX = 1.0, 8.0
LABEL_PX = 22             # 每个裁剪上方黄条的 CSS 高度


def _pdf_for(key: str, role: str, override: dict | None = None) -> Path:
    if override and override.get(role):
        path = Path(override[role])
        if not path.exists():
            raise SystemExit(f"缺少本地原件 {path}")
        return path
    entry = P.load_paper(key)
    if not entry:
        raise SystemExit(f"papers.json 中没有 {key}")
    docs = entry.get(role)
    if not docs:
        raise SystemExit(f"{key} 没有 {role} 原件记录")
    name = docs[0] if isinstance(docs[0], str) else docs[0]["filename"]
    path = P.paper_tmp(key) / name
    if not path.exists():
        raise SystemExit(f"缺少本地原件 {path}")
    return path


def _rendered_width_pt(page, bbox) -> float:
    x0, y0, x1, y1 = bbox
    return (y1 - y0) if page.rotation % 180 else (x1 - x0)


def build(key: str, spec: list[dict], name: str, override: dict | None = None) -> list[Path]:
    import pymupdf

    tmp = P.paper_tmp(key)
    crop_dir = tmp / "crops"
    crop_dir.mkdir(parents=True, exist_ok=True)
    pdfs = {"qp": _pdf_for(key, "qp", override)}
    if any(item.get("role") == "ms" for item in spec):
        pdfs["ms"] = _pdf_for(key, "ms", override)

    cells: list[tuple[str, str, int]] = []   # (label, png_rel, css_height)
    for i, item in enumerate(spec):
        role = item.get("role", "qp")
        page_no = int(item["page"])
        bbox = [float(v) for v in item["bbox"]]
        pdf = pdfs[role]
        with pymupdf.open(pdf) as doc:
            page = doc[page_no - 1]
            width_pt = _rendered_width_pt(page, bbox)
            if width_pt <= 0:
                raise SystemExit(f"{item.get('label')}: 零宽区域 {bbox}")
            zoom = min(ZOOM_MAX, max(ZOOM_MIN, TARGET_PX / width_pt))
        tag = f"{i:03d}-{role}-p{page_no}"
        out = crop_dir / f"stack-{name}-{tag}.png"
        P.crop_region(pdf, page_no, bbox, out, zoom=zoom)
        with pymupdf.open(out) as d:
            w = d[0].rect.width
            h = d[0].rect.height
        css_h = max(1, round(h * SHEET_CSS / w))
        cells.append((f"{item.get('label', tag)}  [{role} p{page_no}] {bbox}",
                      "/" + out.relative_to(B.BATCH_ROOT).as_posix(), css_h))

    pages: list[Path] = []
    batch: list[tuple[str, str, int]] = []
    used = 0
    limit = SHEET_CSS
    for cell in cells:
        cost = cell[2] + LABEL_PX + 4
        if batch and used + cost > limit:
            pages.append(_write(name, len(pages) + 1, batch))
            batch, used = [], 0
        batch.append(cell)
        used += cost
    if batch:
        pages.append(_write(name, len(pages) + 1, batch))
    return pages


def _write(name: str, index: int, cells) -> Path:
    parts = []
    for label, src, css_h in cells:
        parts.append(
            f'<div class=w><div class=cap>{label}</div>'
            f'<img src="{src}" style="width:{SHEET_CSS}px;height:{css_h}px"></div>')
    html = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{name} {index}</title><style>"
        "html,body{margin:0;padding:0;background:#fff}"
        f".w{{width:{SHEET_CSS}px;margin:0}}"
        ".cap{font:12px/16px monospace;background:#ff0;color:#000;padding:2px 4px;"
        "white-space:nowrap;overflow:hidden}"
        "img{display:block;border-bottom:1px solid #888}"
        "</style></head><body>" + "".join(parts) + "</body></html>")
    out = B.WORK / "sheets" / f"{name}-stack-{index}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("key")
    ap.add_argument("--spec", required=True)
    ap.add_argument("--name", default=None)
    ap.add_argument("--qp", default=None, help="直接指定 QP 原件路径（扫描期间 papers.json 不可用）")
    ap.add_argument("--ms", default=None, help="直接指定 MS 原件路径")
    args = ap.parse_args()

    spec_path = Path(args.spec)
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    if not isinstance(spec, list) or not spec:
        raise SystemExit("spec 必须是非空列表")
    name = args.name or (args.key.replace("/", "-") + "-" + spec_path.stem)
    pages = build(args.key, spec, name, {"qp": args.qp, "ms": args.ms})
    print(f"竖排裁剪表 {args.key}：{len(spec)} 个区域 / {len(pages)} 张表")
    for p in pages:
        print(f"http://127.0.0.1:8792/work/sheets/{p.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
