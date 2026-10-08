import json
import pymupdf

BASE = "C:/Users/weo/Desktop/api"
ocr = json.load(open(f"{BASE}/ielts-data/runs/20261003T140007Z-repair/official-keys/ocr/book_10.json"))
pg = [p for p in ocr["pages"] if p["file_page"] == 147][0]
print("== OCR words y278-382, x<210 ==")
for w in pg["words"]:
    if 278 <= w["y0"] <= 382 and w["x0"] < 210:
        print(f"  y={w['y0']:.1f} x={w['x0']:.1f}-{w['x1']:.1f} {w['text']!r} conf={w.get('conf')}")

doc = pymupdf.open(f"{BASE}/tmp_audit_ielts/downloads/book_10.pdf")
p = doc[146]
d = p.get_text("rawdict")
print("== RAW chars y278-382, x<210 ==")
for blk in d["blocks"]:
    if blk.get("type") != 0:
        continue
    for ln in blk["lines"]:
        for sp in ln["spans"]:
            for ch in sp["chars"]:
                x0, y0, x1, y1 = ch["bbox"]
                if 278 <= y0 <= 382 and x0 < 210 and ch["c"].strip():
                    print(f"  y={y0:.1f} x={x0:.1f}-{x1:.1f} {ch['c']!r} font={sp['font']} size={sp['size']:.1f}")
