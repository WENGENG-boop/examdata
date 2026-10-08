import json
import re
from pathlib import Path

import pymupdf

B = Path(r"..")
MS_PDF = B / "tmp/8386/2026-Jun-11/8386_s26_ms_11.pdf"
OUT = B / "work/proposals/8386/spec-combined.json"

QP_W = (5.0, 607.0)
MS_Y = (5.0, 790.0)

qp = [
    ("QP p6 Q2(b)(ii)+marks", 6, [QP_W[0], 480.0, QP_W[1], 730.0]),
    ("QP p7 Q3+marks", 7, [QP_W[0], 360.0, QP_W[1], 640.0]),
    ("QP p8 Q4(a)(b)(c)", 8, [QP_W[0], 250.0, QP_W[1], 790.0]),
    ("QP p9 Q4(c)/(d)", 9, [QP_W[0], 40.0, QP_W[1], 440.0]),
    ("QP p11 Q5(b)/(c)", 11, [QP_W[0], 330.0, QP_W[1], 790.0]),
]

ms_spec = json.loads((B / "work/proposals/8386/spec-ms.json").read_text(encoding="utf-8"))
ms = [(it["label"], it["page"], [it["bbox"][0], MS_Y[0], it["bbox"][2], MS_Y[1]])
      for it in ms_spec if not it["label"].startswith("MS p")]

items = [("qp", lab, page, bb) for lab, page, bb in qp] + \
        [("ms", lab, page, bb) for lab, page, bb in ms]

# css height = (rendered height / rendered width) * 1000
rows = []
for role, lab, page, bb in items:
    with pymupdf.open(MS_PDF if role == "ms" else B / "tmp/8386/2026-Jun-11/8386_s26_qp_11.pdf") as d:
        pg = d[page - 1]
        w = (bb[3] - bb[1]) if pg.rotation % 180 else (bb[2] - bb[0])
        h = (bb[2] - bb[0]) if pg.rotation % 180 else (bb[3] - bb[1])
    rows.append((round(h / w * 1000) + 26, role, lab, page, bb))

rows.sort(key=lambda r: -r[0])
bins: list[list] = []
for r in rows:
    for b in bins:
        if sum(x[0] for x in b) + r[0] <= 1150:
            b.append(r)
            break
    else:
        bins.append([r])

order = [r for b in bins for r in b]
spec = [{"label": lab, "role": role, "page": page, "bbox": bb} for _, role, lab, page, bb in order]
OUT.write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
print("bins", len(bins), "fill", [sum(x[0] for x in b) for b in bins])
for b in bins:
    print("  ", " | ".join(f"{lab}({c})" for c, _, lab, _, _ in b))

# --- MS marks column text per row ---
doc = pymupdf.open(MS_PDF)
print("\n=== MS header words per page ===")
for pno in range(6, 15):
    p = doc[pno]
    heads = []
    for blk in p.get_text("dict")["blocks"]:
        for ln in blk.get("lines", []):
            t = "".join(s["text"] for s in ln["spans"]).strip()
            x0, y0, x1, y1 = ln["bbox"]
            if t in ("Question", "Answer", "Marks", "Guidance") and x0 < 200:
                heads.append(f"{t}@x{x0:.0f}-{x1:.0f}")
    print("p%-2d %s" % (pno + 1, " ".join(heads)))

print("\n=== per-row marks-column text ===")
for lab, page, bb in ms:
    p = doc[page - 1]
    x0, x1 = bb[0], bb[2]
    vals = []
    for blk in p.get_text("dict")["blocks"]:
        for ln in blk.get("lines", []):
            lx0, ly0, lx1, ly1 = ln["bbox"]
            t = "".join(s["text"] for s in ln["spans"]).strip()
            if not t:
                continue
            if x0 - 1 <= lx0 and lx1 <= x1 + 1 and ly0 > 620 and ly1 < 680:
                vals.append(t)
    print("%-10s p%-2d %s" % (lab, page, " | ".join(vals)[:150]))
