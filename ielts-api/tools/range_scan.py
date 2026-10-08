#!/usr/bin/env python3
"""range_scan.py — 扫描剑桥雅思 PDF 全册中的 "Questions X-Y" 范围声明行。

S02 证据工具：题目页（question pages）的范围声明是"预期清单"的第一手证据，
比答案页（多栏交错/OCR 噪声）更可靠。输出每行带 1-based 文件页。

用法:
  python tools/range_scan.py --books 1-20 --out evidence/range-scan-all.txt
  python tools/range_scan.py --books 10 --gt-only   # 只打印 GENERAL TRAINING 命中页

输出为 UTF-8 文本；绝不写入 tmp_audit_ielts。
"""
import argparse
import pathlib
import re
import sys

import pymupdf

ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_DOWNLOADS = ROOT / "tmp_audit_ielts" / "downloads"

RANGE_RE = re.compile(r"Questions?\s*[I|]?\s*\d{1,2}\s*[-–—~一+]\s*\d{1,2}", re.I)
GT_RE = re.compile(r"GENERAL\s+TRAI\S*ING", re.I)


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
    ap.add_argument("--books", default="1-20")
    ap.add_argument("--pdf-dir", default=str(DEFAULT_DOWNLOADS))
    ap.add_argument("--out", required=True)
    ap.add_argument("--gt-only", action="store_true")
    args = ap.parse_args()

    pdf_dir = pathlib.Path(args.pdf_dir)
    out = open(args.out, "w", encoding="utf-8")
    for b in parse_books(args.books):
        pdf = pdf_dir / f"book_{b}.pdf"
        if not pdf.exists():
            out.write(f"===== BOOK {b} MISSING =====\n")
            continue
        doc = pymupdf.open(str(pdf))
        out.write(f"===== BOOK {b} pages={doc.page_count} =====\n")
        for i in range(doc.page_count):
            raw = doc[i].get_text("text")
            if not raw.strip():
                continue
            if args.gt_only:
                if GT_RE.search(raw):
                    out.write(f"p{i + 1:>3}: GT_MARK\n")
                continue
            for line in raw.splitlines():
                line = line.strip()
                if line and RANGE_RE.search(line):
                    out.write(f"p{i + 1:>3}: {line[:110]}\n")
        doc.close()
    out.close()
    print(f"written {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
