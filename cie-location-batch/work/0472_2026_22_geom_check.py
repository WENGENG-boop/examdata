import json
import sys

import pymupdf

BR = "C:/Users/weo/Desktop/api/cie-location-batch"
IDENT = "0472/2026/Jun/22"

idx = json.load(open(f"{BR}/indexes/0472/2026-Jun-22/cie-index.json", encoding="utf-8"))
qp = pymupdf.open(f"{BR}/tmp/0472/2026-Jun-22/0472_s26_qp_22.pdf")
ms = pymupdf.open(f"{BR}/tmp/0472/2026-Jun-22/0472_s26_ms_22.pdf")

HEADER_ZONE_Y = 35.0
FOOTER_ZONE_Y = 725.0


def collect(page):
    items = []
    for d in page.get_drawings():
        r = d["rect"]
        if r.width < 1.0 and r.height < 1.0:
            continue
        items.append(("draw", pymupdf.Rect(r)))
    for w in page.get_text("words"):
        r = pymupdf.Rect(w[:4])
        items.append(("word", r))
    return items


def check_region(items, bbox):
    rx = pymupdf.Rect(bbox)
    issues = []
    for kind, r in items:
        if not r.intersects(rx):
            continue
        inter = r & rx
        if inter.is_empty:
            continue
        # fully inside (with 0.5pt tolerance)
        if (r.x0 >= rx.x0 - 0.5 and r.y0 >= rx.y0 - 0.5
                and r.x1 <= rx.x1 + 0.5 and r.y1 <= rx.y1 + 0.5):
            continue
        # how much of r is outside the region?
        out_w = max(0.0, rx.x0 - r.x0) + max(0.0, r.x1 - rx.x1)
        out_h = max(0.0, rx.y0 - r.y0) + max(0.0, r.y1 - rx.y1)
        if out_w < 0.6 and out_h < 0.6:
            continue  # grazing
        parts = []
        if r.x0 < rx.x0 - 0.5:
            parts.append("cross_left")
        if r.x1 > rx.x1 + 0.5:
            parts.append("cross_right")
        if r.y0 < rx.y0 - 0.5:
            parts.append("cross_top")
        if r.y1 > rx.y1 + 0.5:
            parts.append("cross_bottom")
        issues.append((kind, [round(v, 1) for v in r], parts,
                       round(out_w, 1), round(out_h, 1)))
    return issues


report = []
for q in idx["questions"]:
    for role, doc in (("qp", qp), ("ms", ms)):
        for reg in q.get(role, []):
            page = doc[reg["page"] - 1]
            items = collect(page)
            issues = check_region(items, reg["bbox"])
            flags = []
            bbox = reg["bbox"]
            if role == "qp":
                if bbox[1] < HEADER_ZONE_Y:
                    flags.append("y0_in_header_zone")
                if bbox[3] > FOOTER_ZONE_Y:
                    flags.append("y1_in_footer_zone")
            if issues or flags:
                report.append({
                    "question": q["question"], "role": role, "page": reg["page"],
                    "bbox": bbox, "flags": flags,
                    "crossing": [
                        {"kind": k, "rect": r, "parts": p, "out_w": ow, "out_h": oh}
                        for k, r, p, ow, oh in issues
                    ],
                })

out = f"{BR}/work/0472_2026_22_geom_report.json"
with open(out, "w", encoding="utf-8") as fh:
    json.dump(report, fh, ensure_ascii=False, indent=1)

print(f"regions with findings: {len(report)}")
for rec in report:
    print(f"--- {rec['question']} {rec['role']} p{rec['page']} {rec['bbox']} {rec['flags']}")
    for c in rec["crossing"][:12]:
        print(f"    {c['kind']} {c['rect']} {c['parts']} out_w={c['out_w']} out_h={c['out_h']}")
    if len(rec["crossing"]) > 12:
        print(f"    ... {len(rec['crossing']) - 12} more")
print("saved:", out)
