#!/usr/bin/env python3
"""tmp_reading_scan.py — S02 证据：扫描各册 PDF 的阅读 Passage/Section 起始页。

range-scan-all.txt 的逐行扫描会漏掉换行折行与 OCR 噪声（Questio11s / bused / 1vhich /
READI NG）的引导句；本工具对每页文本做空白归一化后用容错正则匹配，输出 JSON 供
build-manifest 引用。绝不写入 tmp_audit_ielts。

匹配锚点：
  - "spend (about) 2[0O] minutes" → 之后 100 字符内的题号区间（Academic 与旧版 GT 通用）
  - "SECTION N Questions X-Y" → 新版 GT 分节头
用法:
  python tools/tmp_reading_scan.py --books 1-8,10-15,17 --out evidence/reading-sections.json
"""
import argparse
import json
import pathlib
import re

import pymupdf

ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_DOWNLOADS = ROOT / "tmp_audit_ielts" / "downloads"

SEP = r"[-–—^+~]"
SPEND_RE = re.compile(r"spend\s+(?:about\s+)?2[0O]\s*minutes", re.I)
NUMPAIR_RE = re.compile(r"(\d{1,2})\s*" + SEP + r"\s*(\d{1,2})")
GT_SECTION_RE = re.compile(r"SECTION\s*([123])\s*Questions?\s*(\d{1,2})\s*" + SEP + r"\s*(\d{1,2})", re.I)
PASSAGE_RE = re.compile(r"PASSAGE\s*([123])", re.I)


def parse_books(spec: str) -> list[int]:
    books: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-")
            books.extend(range(int(a), int(b) + 1))
        else:
            books.append(int(part))
    return books


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--books", default="1-8,10-15,17")
    ap.add_argument("--pdf-dir", default=str(DEFAULT_DOWNLOADS))
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    pdf_dir = pathlib.Path(args.pdf_dir)
    result: dict[str, list[dict]] = {}
    for b in parse_books(args.books):
        pdf = pdf_dir / f"book_{b}.pdf"
        if not pdf.exists():
            result[str(b)] = []
            continue
        doc = pymupdf.open(str(pdf))
        hits: list[dict] = []
        for i in range(doc.page_count):
            raw = doc[i].get_text("text")
            if not raw.strip():
                continue
            t = norm(raw)
            seen = set()
            for m in SPEND_RE.finditer(t):
                seg = t[m.end():m.end() + 100]
                nm = NUMPAIR_RE.search(seg)
                window = t[max(0, m.start() - 60):m.end() + 200]
                pm = PASSAGE_RE.search(window)
                if "General Training" in window or "SECTION" in window.upper():
                    kind = "gt"
                elif pm:
                    kind = "academic"
                else:
                    kind = "unknown"
                if nm:
                    qa, qb = int(nm.group(1)), int(nm.group(2))
                    if qa >= qb or (qa, qb) in seen:
                        continue
                    seen.add((qa, qb))
                    hits.append({
                        "kind": kind,
                        "page": i + 1,
                        "q_start": qa,
                        "q_end": qb,
                        "passage": int(pm.group(1)) if pm else None,
                        "context": window[:220],
                    })
                else:
                    if "questions" not in window.lower():
                        continue
                    hits.append({
                        "kind": kind,
                        "page": i + 1,
                        "q_start": None,
                        "q_end": None,
                        "passage": int(pm.group(1)) if pm else None,
                        "context": window[:220],
                        "note": "spend-anchor found but number pair unparseable (OCR noise)",
                    })
            for m in GT_SECTION_RE.finditer(t):
                sec, qa, qb = int(m.group(1)), int(m.group(2)), int(m.group(3))
                key = ("sec", sec, qa, qb)
                if key in seen:
                    continue
                seen.add(key)
                hits.append({
                    "kind": "gt_section",
                    "page": i + 1,
                    "section": sec,
                    "q_start": qa,
                    "q_end": qb,
                    "passage": None,
                    "context": t[max(0, m.start() - 40):m.end() + 80][:220],
                })
        doc.close()
        result[str(b)] = hits
    out = pathlib.Path(args.out)
    if not out.is_absolute():
        out = ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    for bk, hits in result.items():
        print(f"BOOK {bk}: {len(hits)} hits")
        for h in hits:
            extra = f" passage={h['passage']}" if h.get("passage") else ""
            sec = f" sec={h['section']}" if h.get("section") else ""
            print(f"  [{h['kind']}] p{h['page']} Q{h['q_start']}-{h['q_end']}{extra}{sec}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
