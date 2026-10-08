"""Measure text-layer lines of CIE tmp originals in UNROTATED pdf-point space (page_base=1).

Usage: python measure_text.py <pdf> <label> <p1> [p2 ...]
Prints each line: unrot(x0,y0,x1,y1) | text, with coordinates matching the index
bbox space (unrotated_pdf_points_top_left), so values are directly comparable to
cie-index.json boxes.

Transform notes (page.rotation=90, unrotated mediabox 612x792):
  t = raw_line_bbox * page.derotation_matrix     # raw from get_text('dict')
  x_u = 792 - t.y1 .. 792 - t.y0 ;  y_u = t.x0 .. t.x1
(verified against known index band values: label "1(a)" -> x_u0 = 102.1 etc.)
"""
import sys
import fitz


def to_unrot(page, rb):
    t = fitz.Rect(rb) * page.derotation_matrix
    if page.rotation == 90:
        return fitz.Rect(792 - t.y1, t.x0, 792 - t.y0, t.x1)
    if page.rotation == 270:
        return fitz.Rect(t.y0, 612 - t.x1, t.y1, 612 - t.x0)
    return t


def main():
    pdf, label = sys.argv[1], sys.argv[2]
    pages = [int(x) for x in sys.argv[3:]]
    doc = fitz.open(pdf)
    for pno in pages:
        page = doc[pno - 1]
        print(f"### {label} p{pno} rot={page.rotation} rect={page.rect} textlen={len(page.get_text().strip())}")
        d = page.get_text("dict")
        for blk in d.get("blocks", []):
            if blk.get("type") != 0:
                bb = to_unrot(page, blk["bbox"]) if page.rotation else fitz.Rect(blk["bbox"])
                print(f"   [IMAGE] ({bb.x0:.1f},{bb.y0:.1f},{bb.x1:.1f},{bb.y1:.1f})")
                continue
            for line in blk.get("lines", []):
                r = to_unrot(page, line["bbox"])
                txt = "".join(s["text"] for s in line.get("spans", [])).replace("\n", " ")
                if not txt.strip():
                    continue
                print(f"   ({r.x0:.1f},{r.y0:.1f},{r.x1:.1f},{r.y1:.1f}) | {txt[:110]}")


if __name__ == "__main__":
    main()
