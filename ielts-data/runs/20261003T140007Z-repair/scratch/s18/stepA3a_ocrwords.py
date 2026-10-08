import json

d = json.load(open("ielts-data/runs/20261003T140007Z-repair/official-keys/ocr/book_10.json", encoding="utf-8"))
pages = {p["file_page"]: p for p in d["pages"]}
for fp in (151,):
    p = pages[fp]
    print(f"===== fp{fp} OCR words ({len(p['words'])}) w={p['width']} h={p['height']} =====")
    ws = sorted(p["words"], key=lambda w: (round(w["y0"]), w["x0"]))
    for w in ws:
        print(f"  y={w['y0']:6.1f}-{w['y1']:6.1f} x={w['x0']:6.1f}-{w['x1']:6.1f} conf={w['conf']:.2f} {w['text']!r}")
