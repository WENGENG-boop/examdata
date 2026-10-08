"""渲染当前卷的全部页面为 PNG（qp/ms），供页面网格表与页序核对使用。

用法：python work/render_paper_pages.py <subject>/<year>/<season>/<paper> [role ...]
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import paperlib as P  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    key = sys.argv[1]
    roles = sys.argv[2:] or ["qp", "ms"]
    entry = P.load_paper(key)
    if not entry:
        print(f"papers.json 中没有 {key}")
        return 1
    tmp = P.paper_tmp(key)
    pages_dir = tmp / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    for role in roles:
        docs = entry.get(role)
        if not docs:
            print(f"{role}: papers.json 无记录，跳过")
            continue
        name = docs[0] if isinstance(docs[0], str) else docs[0]["filename"]
        pdf = tmp / name
        if not pdf.exists():
            print(f"{role}: 缺少本地原件 {pdf}")
            return 1
        n = P.validate_pdf(pdf)["pages"]
        for pno in range(1, n + 1):
            out = pages_dir / f"{role}-p{pno}.png"
            P.render_page(pdf, pno, out)
            print(f"  {role} p{pno} -> {out.name} {out.stat().st_size}B")
    print(f"完成 {key}：{len(roles)} 个角色")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
