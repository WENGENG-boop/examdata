import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pymupdf
import paperlib as P

BASE = Path(r"C:/Users/weo/Desktop/api/cie-location-batch")
TMP = BASE / "tmp/9715/2023-Nov-21"
QP = TMP / "9715_w23_qp_21.pdf"
MS = TMP / "9715_w23_ms_21.pdf"

mode = sys.argv[1]

def lines_of(path, page_no):
    with pymupdf.open(path) as pdf:
        page = pdf[page_no - 1]
        ws = page.get_text("words")
    g = {}
    for w in ws:
        g.setdefault((w[5], w[6]), []).append(w)
    out = []
    for (b, l), items in g.items():
        items.sort(key=lambda w: w[0])
        out.append({
            "text": " ".join(i[4] for i in items),
            "x0": min(i[0] for i in items), "y0": min(i[1] for i in items),
            "x1": max(i[2] for i in items), "y1": max(i[3] for i in items),
        })
    out.sort(key=lambda r: (round(r["y0"], 1), r["x0"]))
    return out

if mode == "qp":
    spec = json.loads((BASE / "work/spec-9715-qp.json").read_text(encoding="utf-8"))
    by_page = {}
    for s in spec:
        by_page.setdefault(s["page"], []).append(s)
    for pg in sorted(by_page):
        regs = sorted(by_page[pg], key=lambda s: s["bbox"][1])
        print(f"\n===== QP page {pg} =====")
        for ln in lines_of(QP, pg):
            cy = (ln["y0"] + ln["y1"]) / 2
            hit = [r["label"] for r in regs if r["bbox"][1] <= cy <= r["bbox"][3]]
            tag = hit[0] if hit else "*** UNASSIGNED ***"
            if len(hit) > 1:
                tag = "OVERLAP:" + ",".join(hit)
            txt = ln["text"]
            if len(txt) > 70:
                txt = txt[:70] + "…"
            print(f"  y{ln['y0']:7.1f}-{ln['y1']:7.1f} x{ln['x0']:6.1f}-{ln['x1']:6.1f} [{tag:22s}] {txt}")
else:
    spec = json.loads((BASE / "work/spec-9715-ms.json").read_text(encoding="utf-8"))
    for s in spec:
        pg = s["page"]
        bbox = s["bbox"]
        x0, y0, x1, y1 = bbox
        with pymupdf.open(MS) as pdf:
            page = pdf[pg - 1]
            ws = page.get_text("words")
            pr = page.rect
            rot = page.rotation
        inside = [w for w in ws if x0 <= (w[0] + w[2]) / 2 <= x1 and y0 <= (w[1] + w[3]) / 2 <= y1]
        inside.sort(key=lambda w: (round(w[0], 1), w[1]))
        joined = " ".join(w[4] for w in inside)
        if len(joined) > 200:
            joined = joined[:200] + "…"
        print(f"[{s['label']:6s}] ms p{pg} rect={pr.width:.0f}x{pr.height:.0f} rot={rot} nwords={len(inside)} :: {joined}")
