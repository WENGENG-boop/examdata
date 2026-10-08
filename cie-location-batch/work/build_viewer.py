#!/usr/bin/env python
"""Concatenate all re-verification sheets for one paper into two tall viewer pages.

Usage:
    python work/build_viewer.py <subject> <year> <season> <paper>

Outputs:
    work/sheets/<slug>-viewer-pages.html    (pages grid sheets as iframes, 1000x1000 each)
    work/sheets/<slug>-viewer-regions.html  (region stack sheets concatenated)

The viewer pages are pure review aids (no index changes, no state writes).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sheet_body(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    m = re.search(r"<body>(.*)</body>", text, re.S)
    return m.group(1) if m else text


def main() -> int:
    if len(sys.argv) != 5:
        print(__doc__)
        return 2
    subject, year, season, paper = sys.argv[1:5]
    slug = f"{subject}-{year}-{season}-{paper}"
    sheets = ROOT / "work" / "sheets"

    # --- pages viewer: iframe each fixed-size 1000x1000 grid sheet ---
    pages_order = [f"{slug}-ms-pages-1.html"] + [f"{slug}-qp-pages-{i}.html" for i in range(1, 5)]
    parts = []
    for name in pages_order:
        p = sheets / name
        if not p.exists():
            print(f"[warn] missing {name}")
            continue
        parts.append(
            f"<iframe src=\"/work/sheets/{name}\" style=\"width:1000px;height:1000px;"
            f"border:0;display:block\"></iframe>"
        )
    out = sheets / f"{slug}-viewer-pages.html"
    out.write_text(
        "<!doctype html><html><head><meta charset='utf-8'><title>VIEWER pages "
        + slug
        + "</title><style>html,body{margin:0;padding:0;background:#ddd}iframe{background:#fff}"
        "</style></head><body>" + "".join(parts) + "</body></html>",
        encoding="utf-8",
    )
    print("wrote", out.name)

    # --- regions viewer: concatenate stack sheet bodies in order ---
    names = sorted(
        (p.name for p in sheets.glob(f"{slug}-qp-regions-stack-*.html")),
        key=lambda n: int(re.search(r"stack-(\d+)\.html$", n).group(1)),
    )
    names += sorted(
        (p.name for p in sheets.glob(f"{slug}-msreg-stack-*.html")),
        key=lambda n: int(re.search(r"stack-(\d+)\.html$", n).group(1)),
    )
    bodies = [sheet_body(sheets / n) for n in names]
    out2 = sheets / f"{slug}-viewer-regions.html"
    out2.write_text(
        "<!doctype html><html><head><meta charset='utf-8'><title>VIEWER regions "
        + slug
        + "</title><style>html,body{margin:0;padding:0;background:#fff}"
        ".w{width:1000px;margin:0}.cap{font:12px/16px monospace;background:#ff0;color:#000;"
        "padding:2px 4px;white-space:nowrap;overflow:hidden}img{display:block;"
        "border-bottom:1px solid #888}</style></head><body>"
        + "".join(bodies)
        + "</body></html>",
        encoding="utf-8",
    )
    print("wrote", out2.name, "sheets=", len(names))

    # --- chunked region viewers: each page <= 1850px so one capture shows all ---
    chunks: list[list[str]] = [[]]
    heights: list[int] = [0]
    for n in names:
        body = sheet_body(sheets / n)
        h = sum(int(m.group(1)) for m in re.finditer(r'style="width:1000px;height:(\d+)px"', body))
        h += len(re.findall(r"class=cap", body)) * 20
        if heights[-1] + h > 1850 and chunks[-1]:
            chunks.append([])
            heights.append(0)
        chunks[-1].append(body)
        heights[-1] += h
    for i, (bodies_i, h) in enumerate(zip(chunks, heights), 1):
        out_i = sheets / f"{slug}-viewer-regions-c{i:02d}.html"
        out_i.write_text(
            "<!doctype html><html><head><meta charset='utf-8'><title>VIEWER regions "
            + slug
            + f" c{i:02d}</title><style>html,body{{margin:0;padding:0;background:#fff}}"
            ".w{width:1000px;margin:0}.cap{font:12px/16px monospace;background:#ff0;color:#000;"
            "padding:2px 4px;white-space:nowrap;overflow:hidden}img{display:block;"
            "border-bottom:1px solid #888}</style></head><body>"
            + "".join(bodies_i)
            + "</body></html>",
            encoding="utf-8",
        )
        print(f"wrote {out_i.name} height={h}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
