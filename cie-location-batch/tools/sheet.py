"""生成联络表 HTML：整页总览与区域裁剪。

两种模式：
- `pages <key> [--role qp|ms] [--from N] [--to N] [--cols 2]`：按页拼格子。
- `crops <key> --spec <json>`：spec 为 `[{"label","role","page","bbox"}]`，
  用 `paperlib.crop_region` 渲染到 `tmp/<...>/crops/` 后拼格子。

HTML 写到 `work/sheets/`，并把可访问的 URL 逐行打印到 stdout。
静态服务器（8792）的根目录是 `BATCH_ROOT`，所以图片用 `/tmp/...` 绝对路径引用。
每个格子不超过 500 CSS px，整张表不超过 1000x1000 CSS px；装不下就多出几张表，
不把格子缩到 400px 以下。页面不锁视口（无 height/overflow:hidden），视口装不下时
浏览器可滚动查看整表。格子上有一个黄色小标题。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import batchlib as B
import paperlib as P

SHEET_BASE = "http://127.0.0.1:8792"
SHEET_REL = "work/sheets"
SHEET_DIR = B.WORK / "sheets"

SHEET_PX = 1000
CELL_MAX = 500
CELL_MIN = 400
DEFAULT_COLS = 2

SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def slug(key: str) -> str:
    return key.replace("/", "-")


def safe_name(text: str, fallback: str = "region") -> str:
    cleaned = SAFE_NAME_RE.sub("-", text).strip("-.")
    return cleaned or fallback


def cell_geometry(cols: int) -> tuple[int, int, int]:
    """返回 (格子边长, 每张表的行数, 每张表容量)。"""
    if cols < 1:
        raise ValueError("--cols 至少为 1")
    cell = min(CELL_MAX, SHEET_PX // cols)
    if cell < CELL_MIN:
        raise ValueError(f"--cols {cols} 会把格子压到 {cell}px，低于 {CELL_MIN}px 下限")
    rows = SHEET_PX // cell
    return cell, rows, cols * rows


def sheet_html(cells: list[dict], cols: int, cell: int, title: str) -> str:
    style = (
        "<style>"
        "html,body{margin:0;padding:0;background:#fff;"
        f"width:{SHEET_PX}px}}"
        ".g{display:grid;"
        f"grid-template-columns:repeat({cols},{cell}px);"
        f"grid-template-rows:repeat({SHEET_PX // cell},{cell}px)}}"
        f".c{{width:{cell}px;height:{cell}px;overflow:hidden;border:1px solid #ccc;"
        "box-sizing:border-box;position:relative;background:#fafafa}"
        ".cap{font:11px monospace;background:#ff0;color:#000;position:absolute;"
        "top:0;left:0;z-index:9;padding:1px 3px;max-width:100%;"
        "overflow:hidden;white-space:nowrap}"
        "a{display:block;width:100%;height:100%}"
        "img{max-width:100%;max-height:100%;object-fit:contain;display:block;"
        "margin:auto;position:absolute;top:0;bottom:0;left:0;right:0}"
        "</style>"
    )
    parts = []
    for item in cells:
        caption = item["caption"]
        parts.append(
            f'<div class=c><div class=cap>{caption}</div>'
            f'<a href="{item["src"]}" title="{caption}">'
            f'<img src="{item["src"]}"></a></div>')
    return (f"<!doctype html><html><head><meta charset='utf-8'><title>{title}</title>"
            + style + "</head><body><div class=g>"
            + "".join(parts) + "</div></body></html>")


def write_sheets(cells: list[dict], cols: int, name_prefix: str,
                 title: str) -> list[Path]:
    cell, _rows, capacity = cell_geometry(cols)
    SHEET_DIR.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for index in range(0, len(cells), capacity):
        chunk = cells[index:index + capacity]
        dest = SHEET_DIR / f"{name_prefix}-{index // capacity + 1}.html"
        dest.write_text(sheet_html(chunk, cols, cell, title), encoding="utf-8")
        written.append(dest)
    return written


def print_urls(paths: list[Path]) -> None:
    for path in paths:
        print(f"{SHEET_BASE}/{SHEET_REL}/{path.name}")


def find_pdfs(tmp_dir: Path) -> dict[str, Path]:
    def pick(*patterns):
        for pattern in patterns:
            hits = sorted(tmp_dir.glob(pattern))
            if hits:
                return hits[0]
        return None

    found = {"qp": pick("*_qp_*.pdf", "*qp*.pdf"), "ms": pick("*_ms_*.pdf", "*ms*.pdf")}
    return {role: path for role, path in found.items() if path is not None}


def rel_url(path: Path) -> str:
    return "/" + path.relative_to(B.BATCH_ROOT).as_posix()


def parse_page_no(path: Path) -> int | None:
    m = re.search(r"-p(\d+)\.png$", path.name)
    return int(m.group(1)) if m else None


def cmd_pages(args) -> int:
    key = args.key
    tmp_dir = P.paper_tmp(key)
    if not tmp_dir.is_dir():
        print(f"[失败] 没有临时目录 {tmp_dir}")
        return 1
    roles = ["qp", "ms"] if args.role == "both" else [args.role]
    cells: list[dict] = []
    for role in roles:
        pages_dir = tmp_dir / "pages"
        images = sorted(pages_dir.glob(f"{role}-p*.png"),
                        key=lambda p: (parse_page_no(p) or 0))
        for image in images:
            page_no = parse_page_no(image)
            if page_no is None:
                continue
            if args.from_page and page_no < args.from_page:
                continue
            if args.to_page and page_no > args.to_page:
                continue
            cells.append({"src": rel_url(image),
                          "caption": f"{role} p{page_no} {image.name}"})
    if not cells:
        print(f"[失败] {tmp_dir}/pages 下没有匹配的渲染图，先跑 propose.py")
        return 1
    role_tag = args.role
    written = write_sheets(cells, args.cols, f"{slug(key)}-{role_tag}-pages",
                           f"{key} {role_tag} pages")
    print(f"页表 {key} {role_tag}：{len(cells)} 张图 / {len(written)} 张表")
    print_urls(written)
    return 0


def load_spec(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not data:
        raise ValueError("spec 必须是至少含一项的 JSON 数组")
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"spec[{i}] 不是对象")
        for field in ("label", "role", "page", "bbox"):
            if field not in item:
                raise ValueError(f"spec[{i}] 缺字段 {field}")
        if item["role"] not in ("qp", "ms"):
            raise ValueError(f"spec[{i}] role 必须是 qp 或 ms")
        bbox = item["bbox"]
        if not isinstance(bbox, list) or len(bbox) != 4:
            raise ValueError(f"spec[{i}] bbox 必须是 4 个数")
    return data


def cmd_crops(args) -> int:
    key = args.key
    tmp_dir = P.paper_tmp(key)
    if not tmp_dir.is_dir():
        print(f"[失败] 没有临时目录 {tmp_dir}")
        return 1
    spec = load_spec(Path(args.spec))
    pdfs = find_pdfs(tmp_dir)
    crops_dir = tmp_dir / "crops"
    crops_dir.mkdir(parents=True, exist_ok=True)

    cells: list[dict] = []
    failures: list[str] = []
    for index, item in enumerate(spec, start=1):
        role = item["role"]
        pdf = pdfs.get(role)
        if pdf is None:
            failures.append(f"{item['label']}: 找不到 {role} PDF")
            continue
        name = f"{index:02d}-{role}-{safe_name(str(item['label']))}-p{item['page']}.png"
        dest = crops_dir / name
        try:
            P.crop_region(pdf, int(item["page"]), item["bbox"], dest)
        except Exception as exc:
            failures.append(f"{item['label']}: {exc}")
            continue
        caption = f"{item['label']} [{role} p{item['page']} {item['bbox']}]"
        cells.append({"src": rel_url(dest), "caption": caption})

    for failure in failures:
        print(f"  ~ 裁剪失败 {failure}")
    if not cells:
        print("[失败] 没有任何裁剪成功")
        return 1
    written = write_sheets(cells, args.cols, f"{slug(key)}-crops", f"{key} crops")
    print(f"裁剪表 {key}：{len(cells)} 张图 / {len(written)} 张表")
    print_urls(written)
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="生成联络表 HTML")
    sub = parser.add_subparsers(dest="mode", required=True)

    pages = sub.add_parser("pages", help="按页生成总览表")
    pages.add_argument("key", help="subject/year/season/paper")
    pages.add_argument("--role", choices=["qp", "ms", "both"], default="qp")
    pages.add_argument("--from", dest="from_page", type=int, default=None)
    pages.add_argument("--to", dest="to_page", type=int, default=None)
    pages.add_argument("--cols", type=int, default=DEFAULT_COLS)

    crops = sub.add_parser("crops", help="按 spec 生成裁剪表")
    crops.add_argument("key", help="subject/year/season/paper")
    crops.add_argument("--spec", required=True, help="裁剪清单 JSON 路径")
    crops.add_argument("--cols", type=int, default=DEFAULT_COLS)

    args = parser.parse_args()
    try:
        if args.mode == "pages":
            return cmd_pages(args)
        return cmd_crops(args)
    except ValueError as exc:
        print(f"[失败] {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
