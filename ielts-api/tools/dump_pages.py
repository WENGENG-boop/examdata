#!/usr/bin/env python3
"""Dump raw text of specific PDF pages as auditable evidence.

Writes one file per page: <outdir>/book<N>-p<page>.txt (1-based physical page).
Read-only with respect to the PDFs. Output is UTF-8 with a small header
comment line carrying the pdf sha256 so evidence can be tied to the exact
input bytes.

Usage:
  python tools/dump_pages.py --book 5 --pages 157 --outdir <dir>
  python tools/dump_pages.py --book 10 --pages 144-145,152-153 --outdir <dir>
"""
import argparse
import hashlib
import json
import pathlib
import sys

import pymupdf

ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_DOWNLOADS = ROOT / "tmp_audit_ielts" / "downloads"


def parse_pages(spec: str) -> list[int]:
    pages: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            pages.extend(range(int(a), int(b) + 1))
        else:
            pages.append(int(part))
    return pages


def sha256_file(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def pdf_for_book(book: int) -> pathlib.Path:
    p = DEFAULT_DOWNLOADS / f"book_{book}.pdf"
    if not p.exists():
        raise SystemExit(f"pdf not found: {p}")
    return p


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", type=int, required=True)
    ap.add_argument("--pages", required=True, help="e.g. 157 or 144-145,152-153")
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--pdf", default=None, help="override pdf path")
    args = ap.parse_args()

    pdf = pathlib.Path(args.pdf) if args.pdf else pdf_for_book(args.book)
    outdir = pathlib.Path(args.outdir)
    if not outdir.is_absolute():
        outdir = ROOT / outdir
    outdir.mkdir(parents=True, exist_ok=True)

    digest = sha256_file(pdf)
    doc = pymupdf.open(str(pdf))
    manifest = []
    for page_no in parse_pages(args.pages):
        if page_no < 1 or page_no > len(doc):
            print(f"page {page_no} out of range 1..{len(doc)}", file=sys.stderr)
            continue
        page = doc[page_no - 1]
        text = page.get_text("text")
        out_path = outdir / f"book{args.book}-p{page_no:04d}.txt"
        header = (
            f"# source={pdf.as_posix()} sha256={digest} "
            f"physical_page={page_no} pdf_pages={len(doc)}\n"
        )
        out_path.write_text(header + text, encoding="utf-8")
        manifest.append(
            {
                "book": args.book,
                "page": page_no,
                "file": out_path.name,
                "chars": len(text),
                "pdf_sha256": digest,
            }
        )
    doc.close()
    print(json.dumps({"book": args.book, "pdf_sha256": digest, "dumped": manifest}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
