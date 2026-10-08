import fitz, sys, io

root = "C:/Users/weo/Desktop/api/cie-location-batch"
qp = fitz.open(root + "/tmp/0472/2025-Jun-12/0472_s25_qp_12.pdf")
ms = fitz.open(root + "/tmp/0472/2025-Jun-12/0472_s25_ms_12.pdf")

out = io.StringIO()

def dump(doc, tag, pages):
    for pno in pages:
        p = doc[pno - 1]
        out.write(f"=== {tag} p{pno} rect={p.rect} rot={p.rotation}\n")
        d = p.get_text("dict")
        for b in d["blocks"]:
            if b["type"] != 0:
                out.write(f"  [IMG] bbox={[round(v,1) for v in b['bbox']]}\n")
                continue
            for l in b["lines"]:
                x0, y0, x1, y1 = l["bbox"]
                txt = "".join(s["text"] for s in l["spans"])
                out.write(f"  y={y0:7.1f}-{y1:7.1f} x={x0:6.1f}-{x1:6.1f} | {txt[:110]}\n")

dump(qp, "QP", [1, 2, 3, 6, 7, 8, 9])
dump(qp, "QP", [10, 11, 12, 13, 14, 15, 16])
dump(ms, "MS", [1, 2, 3])

with open(root + "/work/0472-12-lines.txt", "w", encoding="utf-8") as f:
    f.write(out.getvalue())
print("done", len(out.getvalue()))
