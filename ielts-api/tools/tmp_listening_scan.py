#!/usr/bin/env python3
"""tmp_listening_scan.py — S02 证据：扫描各册 PDF 的 SECTION 头与紧随其后的 Questions 范围。

range-scan-all.txt 只记录含 "Questions X-Y" 的行；多数册的 SECTION 头与 Questions
行分开，因此听力 Part 起始页需要单独扫描。输出 JSON 供 build-manifest 引用；
绝不写入 tmp_audit_ielts。

用法:
  python tools/tmp_listening_scan.py --books 1-8,10-15,17 --out evidence/listening-sections.json
"""
import argparse
import json
import pathlib
import re
import sys

import pymupdf

ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_DOWNLOADS = ROOT / "tmp_audit_ielts" / "downloads"

SEC_RE = re.compile(r"SEC[TI]{1,3}ON\s*[1-4]|SEC[TI]{1,3}ON\s*[I1l][Vv]?|PART\s*[1-4]", re.I)
Q_RE = re.compile(r"Questions?\s*[I|]?\s*(\d{1,2})\s*[-–—~一+]\s*(\d{1,2})", re.I)


def parse_books(spec: str) -> list[int]:
    books = []
    for part in spec.split(","):
        if "-" in part:
            a, b = part.split("-")
            books.extend(range(int(a), int(b) + 1))
        else:
            books.append(int(part))
    return books


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--books", default="1-8,10-15,17")
    ap.add_argument("--pdf-dir", default=str(DEFAULT_DOWNLOADS))
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-page", type=int, default=0, help="0 = all pages")
    args = ap.parse_args()

    pdf_dir = pathlib.Path(args.pdf_dir)
    result: dict[str, list[dict]] = {}
    for b in parse_books(args.books):
        pdf = pdf_dir / f"book_{b}.pdf"
        if not pdf.exists():
            result[str(b)] = []
            continue
        doc = pymupdf.open(str(pdf))
        n = doc.page_count if not args.max_page else min(args.max_page, doc.page_count)
        hits: list[dict] = []
        for i in range(n):
            raw = doc[i].get_text("text")
            if not raw.strip():
                continue
            lines = [ln.strip() for ln in raw.splitlines()]
            for j, ln in enumerate(lines):
                if SEC_RE.search(ln):
                    # 同一行或紧随的 1-3 行里找 Questions 范围
                    a = b2 = None
                    for k in range(j, min(j + 3, len(lines))):
                        m = Q_RE.search(lines[k])
                        if m:
                            a, b2 = int(m.group(1)), int(m.group(2))
                            break
                    hits.append({
                        "page": i + 1,
                        "line": ln[:80],
                        "q_start": a,
                        "q_end": b2,
                        "next": [lines[k][:60] for k in range(j + 1, min(j + 3, len(lines)))],
                    })
        result[str(b)] = hits
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    # 文本摘要
    for bk in sorted(result, key=int):
        print(f"BOOK {bk}:")
        for h in result[bk]:
            print(f"  p{h['page']}: {h['line']!r} q={h['q_start']}-{h['q_end']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
