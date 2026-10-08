#!/usr/bin/env python3
"""S06 tool: column-aware structured extraction from IELTS source PDFs.

Read-only with respect to the input PDFs. Emits a JSON document with, for each
requested physical page:

  - file_page (1-based physical page) and printed_page (header/footer number
    resolved with the same heuristic as tools/printed_page.py)
  - text_layer flag, detected column count and the column split x
  - per-column reconstructed lines (y-ordered, word x-ordered)
  - standalone question-number tokens with positions
  - figure regions (images + drawing clusters) with bboxes; optionally rendered
    as PNG assets
  - needs_review flag when a page has no text layer (scanned image) or is
    suspected to be a partial scan

Usage:
  python tools/pdf_extract.py --book 1 --pages 40-45 --out out.json
  python tools/pdf_extract.py --book 3 --pages 34-40 --assets assets/ --textdir txt/
  python tools/pdf_extract.py --pdf C:/path/book_20_test2.pdf --pages 1-10 --out o.json
  python tools/pdf_extract.py --book 3 --pages 34-41 --ocr-json ocr.json --out out.json

--ocr-json merges OCR words (boxes + confidence, from ielts-data/tools/ocr_pages.py)
into the matching pages under a separate "ocr" block; the text-layer "lines" are
never overwritten.
"""

import argparse
import hashlib
import json
import pathlib
import re
import sys

import pymupdf

ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_DOWNLOADS = ROOT / "tmp_audit_ielts" / "downloads"

STANDALONE_INT_RE = re.compile(r"^(\d{1,3})$")
PAREN_INT_RE = re.compile(r"^\((\d{1,3})\)$")


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


def resolve_printed_page(page: "pymupdf.Page") -> dict:
    """Header/footer standalone-integer heuristic (mirrors printed_page.py)."""
    text = page.get_text("text") or ""
    lines = [ln for ln in text.splitlines()]
    nonempty = [ln.strip() for ln in lines if ln.strip()]
    first = None
    last = None
    for ln in nonempty[:2]:
        m = STANDALONE_INT_RE.match(ln)
        if m and 1 <= int(m.group(1)) <= 400:
            first = int(m.group(1))
            break
    for ln in reversed(nonempty[-2:]):
        m = STANDALONE_INT_RE.match(ln)
        if m and 1 <= int(m.group(1)) <= 400:
            last = int(m.group(1))
            break
    chosen = last if last is not None else first
    return {"first": first, "last": last, "chosen": chosen}


def page_words(page: "pymupdf.Page") -> list[dict]:
    out = []
    for w in page.get_text("words"):
        x0, y0, x1, y1, text = w[0], w[1], w[2], w[3], w[4]
        if not text:
            continue
        out.append(
            {
                "x0": round(float(x0), 2),
                "y0": round(float(y0), 2),
                "x1": round(float(x1), 2),
                "y1": round(float(y1), 2),
                "text": text,
            }
        )
    return out


def detect_columns(words: list[dict], width: float) -> tuple[int, float | None]:
    if not words:
        return 1, None
    n = len(words)
    best = None
    for pct in range(35, 66):
        frac = pct / 100.0
        x = width * frac
        left = 0
        right = 0
        cross = 0
        for w in words:
            if w["x1"] <= x:
                left += 1
            elif w["x0"] >= x:
                right += 1
            else:
                cross += 1
        if left < 0.15 * n or right < 0.15 * n:
            continue
        score = (cross, abs(frac - 0.5))
        if best is None or score < best[0]:
            best = (score, x, frac)
    if best is None:
        return 1, None
    (cross, _), x, _frac = best
    if cross <= max(1, n * 0.01):
        return 2, round(x, 2)
    return 1, None


def group_lines(words: list[dict], tol: float = 3.0) -> list[dict]:
    ws = sorted(words, key=lambda w: (w["y0"], w["x0"]))
    lines: list[dict] = []
    for w in ws:
        placed = False
        for ln in reversed(lines[-4:] if len(lines) > 4 else lines):
            if abs(w["y0"] - ln["y"]) <= tol:
                ln["words"].append(w)
                ln["y"] = min(ln["y"], w["y0"])
                placed = True
                break
        if not placed:
            lines.append({"y": w["y0"], "words": [w]})
    out = []
    for ln in sorted(lines, key=lambda l: l["y"]):
        ln["words"].sort(key=lambda w: w["x0"])
        text = " ".join(w["text"] for w in ln["words"])
        out.append(
            {
                "y": round(ln["y"], 2),
                "text": text,
                "x0": round(min(w["x0"] for w in ln["words"]), 2),
                "x1": round(max(w["x1"] for w in ln["words"]), 2),
            }
        )
    return out


def find_numbers(words: list[dict]) -> list[dict]:
    out = []
    for w in words:
        m = STANDALONE_INT_RE.match(w["text"])
        if m:
            out.append({"token": w["text"], "n": int(m.group(1)), "paren": False, "x": w["x0"], "y": w["y0"]})
            continue
        m = PAREN_INT_RE.match(w["text"])
        if m:
            out.append({"token": w["text"], "n": int(m.group(1)), "paren": True, "x": w["x0"], "y": w["y0"]})
    return out


def _rect_overlaps(a, b, pad: float = 6.0) -> bool:
    return not (
        a.x1 + pad < b.x0 or b.x1 + pad < a.x0 or a.y1 + pad < b.y0 or b.y1 + pad < a.y0
    )


def figure_regions(page: "pymupdf.Page") -> list[dict]:
    regions: list[dict] = []
    page_area = page.rect.width * page.rect.height
    for img in page.get_images(full=True):
        xref = img[0]
        try:
            rects = page.get_image_rects(xref)
        except Exception:
            rects = []
        for r in rects:
            if r.width < 8 or r.height < 8:
                continue
            regions.append(
                {
                    "kind": "image",
                    "xref": xref,
                    "bbox": [round(v, 2) for v in (r.x0, r.y0, r.x1, r.y1)],
                }
            )
    try:
        drawings = page.get_drawings()
    except Exception:
        drawings = []
    for d in drawings:
        r = d["rect"]
        if r.width * r.height < 400:
            continue
        if r.width * r.height > page_area * 0.85:
            continue
        regions.append(
            {
                "kind": "drawing",
                "bbox": [round(v, 2) for v in (r.x0, r.y0, r.x1, r.y1)],
            }
        )
    # merge overlapping regions of same kind (simple union)
    merged: list[dict] = []
    for reg in sorted(regions, key=lambda g: (g["kind"], g["bbox"][1], g["bbox"][0])):
        bbox = pymupdf.Rect(reg["bbox"])
        hit = None
        for m in merged:
            if m["kind"] == reg["kind"] and _rect_overlaps(pymupdf.Rect(m["bbox"]), bbox):
                hit = m
                break
        if hit is None:
            merged.append(reg)
        else:
            hb = pymupdf.Rect(hit["bbox"])
            nb = hb | bbox
            hit["bbox"] = [round(v, 2) for v in (nb.x0, nb.y0, nb.x1, nb.y1)]
    return merged


def render_assets(
    page: "pymupdf.Page",
    regions: list[dict],
    assets_dir: pathlib.Path,
    stem: str,
    min_area: float,
) -> None:
    idx = 0
    for reg in regions:
        bbox = pymupdf.Rect(reg["bbox"])
        if bbox.width * bbox.height < min_area:
            continue
        clip = pymupdf.Rect(bbox.x0 - 4, bbox.y0 - 4, bbox.x1 + 4, bbox.y1 + 4)
        clip = clip & page.rect
        if clip.is_empty:
            continue
        idx += 1
        name = f"{stem}-fig{idx}.png"
        pix = page.get_pixmap(matrix=pymupdf.Matrix(2, 2), clip=clip)
        pix.save(str(assets_dir / name))
        reg["asset"] = name
        reg["asset_px"] = [pix.width, pix.height]


def load_ocr_json(path: pathlib.Path) -> dict:
    """Load an ocr_pages.py output JSON; index pages by file_page."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "pages" not in data:
        raise SystemExit(f"not an ocr_pages.py output: {path}")
    pages = {}
    for p in data["pages"]:
        pages[int(p["file_page"])] = p
    meta = {
        "engine": data.get("engine"),
        "engine_version": data.get("engine_version"),
        "dpi": data.get("dpi"),
        "pdf": data.get("pdf"),
    }
    return {"meta": meta, "pages": pages}


def build_ocr_block(ocr_page: dict, meta: dict) -> dict:
    words = ocr_page.get("words") or []
    lines = group_lines([{**w, "y0": w["y0"]} for w in words])
    return {
        "engine": meta.get("engine"),
        "engine_version": meta.get("engine_version"),
        "dpi": meta.get("dpi"),
        "rect": ocr_page.get("rect"),
        "n_words": len(words),
        "words": words,
        "lines": lines,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", type=int, default=None)
    ap.add_argument("--pdf", default=None, help="override pdf path")
    ap.add_argument("--pages", required=True, help="e.g. 40-45 or 144,145")
    ap.add_argument("--out", required=True, help="output JSON path")
    ap.add_argument("--textdir", default=None, help="optional dir for per-page text dumps")
    ap.add_argument("--assets", default=None, help="optional dir for rendered figure PNGs")
    ap.add_argument("--min-fig-area", type=float, default=4000.0, help="min bbox area (pt^2) to render an asset")
    ap.add_argument("--render-pages", action="store_true", help="render every requested page as PNG into --assets")
    ap.add_argument("--ocr-json", default=None, help="ocr_pages.py output JSON; merges OCR words for matching pages")
    args = ap.parse_args()

    if args.pdf:
        pdf = pathlib.Path(args.pdf)
    elif args.book is not None:
        pdf = DEFAULT_DOWNLOADS / f"book_{args.book}.pdf"
    else:
        raise SystemExit("need --book or --pdf")
    if not pdf.exists():
        raise SystemExit(f"pdf not found: {pdf}")

    out_path = pathlib.Path(args.out)
    if not out_path.is_absolute():
        out_path = ROOT / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    textdir = None
    if args.textdir:
        textdir = pathlib.Path(args.textdir)
        if not textdir.is_absolute():
            textdir = ROOT / textdir
        textdir.mkdir(parents=True, exist_ok=True)
    assets_dir = None
    if args.assets:
        assets_dir = pathlib.Path(args.assets)
        if not assets_dir.is_absolute():
            assets_dir = ROOT / assets_dir
        assets_dir.mkdir(parents=True, exist_ok=True)

    digest = sha256_file(pdf)
    ocr_data = None
    if args.ocr_json:
        ocr_path = pathlib.Path(args.ocr_json)
        if not ocr_path.is_absolute():
            ocr_path = ROOT / ocr_path
        ocr_data = load_ocr_json(ocr_path)
        ocr_pdf = (ocr_data["meta"].get("pdf") or "").replace("\\", "/").lower()
        if ocr_pdf and ocr_pdf != pdf.as_posix().lower():
            raise SystemExit(f"--ocr-json was produced from a different pdf: {ocr_pdf} != {pdf.as_posix()}")
    doc = pymupdf.open(str(pdf))
    pages_out = []
    for page_no in parse_pages(args.pages):
        if page_no < 1 or page_no > len(doc):
            print(f"page {page_no} out of range 1..{len(doc)}", file=sys.stderr)
            continue
        page = doc[page_no - 1]
        words = page_words(page)
        columns, split_x = detect_columns(words, page.rect.width)
        if columns == 2:
            left_words = [w for w in words if w["x1"] <= split_x]
            right_words = [w for w in words if w["x0"] >= split_x]
            cross_words = [w for w in words if w not in left_words and w not in right_words]
            col_sets = [left_words, right_words]
            if cross_words:
                # attach crossing words to the nearest column by x center
                for w in cross_words:
                    cx = (w["x0"] + w["x1"]) / 2
                    col_sets[0 if cx <= split_x else 1].append(w)
        else:
            col_sets = [words]
        col_lines = [group_lines(ws) for ws in col_sets]
        numbers = find_numbers(words)
        figures = figure_regions(page)
        stem = f"book{args.book if args.book is not None else 'x'}-p{page_no:04d}"
        if assets_dir is not None:
            render_assets(page, figures, assets_dir, stem, args.min_fig_area)
            if args.render_pages:
                pix = page.get_pixmap(matrix=pymupdf.Matrix(2, 2))
                pix.save(str(assets_dir / f"{stem}-page.png"))
        printed = resolve_printed_page(page)
        n_words = len(words)
        needs_review = n_words == 0
        suspected_scan = False
        if n_words > 0 and n_words < 60:
            big = [f for f in figures if f["kind"] == "image"]
            for f in big:
                b = f["bbox"]
                area = (b[2] - b[0]) * (b[3] - b[1])
                if area > page.rect.width * page.rect.height * 0.5:
                    suspected_scan = True
                    break
        ocr_block = None
        if ocr_data is not None and page_no in ocr_data["pages"]:
            ocr_block = build_ocr_block(ocr_data["pages"][page_no], ocr_data["meta"])
        page_json = {
            "file_page": page_no,
            "printed_page": printed["chosen"],
            "printed_first": printed["first"],
            "printed_last": printed["last"],
            "width": round(page.rect.width, 2),
            "height": round(page.rect.height, 2),
            "rotation": page.rotation,
            "text_layer": n_words > 0,
            "n_words": n_words,
            "columns": columns,
            "column_split_x": split_x,
            "lines": col_lines,
            "numbers": numbers,
            "figures": figures,
            "needs_review": needs_review,
            "suspected_scan": suspected_scan,
            "ocr": ocr_block,
        }
        pages_out.append(page_json)
        if textdir is not None:
            buf = [
                f"# source={pdf.as_posix()} sha256={digest} physical_page={page_no} "
                f"pdf_pages={len(doc)} printed_page={printed['chosen']} columns={columns}\n"
            ]
            for ci, lines in enumerate(col_lines):
                buf.append(f"## column {ci + 1}\n")
                for ln in lines:
                    buf.append(f"[y={ln['y']:7.2f}] {ln['text']}\n")
            (textdir / f"{stem}.txt").write_text("".join(buf), encoding="utf-8")
    doc.close()

    payload = {
        "tool": "pdf_extract",
        "version": 1,
        "pdf": {"path": pdf.as_posix(), "sha256": digest, "pages": None},
        "pages": pages_out,
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    summary = {
        "ok": True,
        "pdf": pdf.as_posix(),
        "sha256": digest,
        "pages": [
            {
                "file_page": p["file_page"],
                "printed_page": p["printed_page"],
                "words": p["n_words"],
                "columns": p["columns"],
                "needs_review": p["needs_review"],
                "suspected_scan": p["suspected_scan"],
                "figures": len(p["figures"]),
                "ocr": bool(p.get("ocr")),
            }
            for p in pages_out
        ],
    }
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
