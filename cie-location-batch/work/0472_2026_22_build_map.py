# -*- coding: utf-8 -*-
"""0472/2026/Jun/22: build the post-fix reverify map (sheets -> regions).

Parses the freshly rebuilt sheets (25 qp-regions-stack + 9 msreg-stack, built
from the FIXED index at 21:38), cross-checks 1:1 against the current index
(49 qp + 43 ms regions, all qp first then all ms), and prints:
- the sheets that contain any of the 18 changed QP regions
- all 9 msreg sheets (43 MS regions)
Writes work/0472_2026_22_reverify_map.json.
"""
import json
import re
from pathlib import Path

BR = Path(r"C:/Users/weo/Desktop/api/cie-location-batch")
SHEETS = BR / "work/sheets"
IDX = BR / "indexes/0472/2026-Jun-22/cie-index.json"
MAP = BR / "work/0472_2026_22_reverify_map.json"

index = json.loads(IDX.read_text(encoding="utf-8"))
cap_re = re.compile(r"<div class=cap>(.*?)</div><img src=\"([^\"]+)\"")


def _num(p: Path) -> int:
    return int(re.search(r"stack-(\d+)", p.name).group(1))


qp_sheets = sorted(SHEETS.glob("0472-2026-Jun-22-qp-regions-stack-*.html"), key=_num)
ms_sheets = sorted(SHEETS.glob("0472-2026-Jun-22-msreg-stack-*.html"), key=_num)
assert len(qp_sheets) == 25, [p.name for p in qp_sheets]
assert len(ms_sheets) == 9, [p.name for p in ms_sheets]

sheet_map = {}
frame_regions = []
for f in qp_sheets + ms_sheets:
    html = f.read_text(encoding="utf-8")
    regs = []
    for m in cap_re.finditer(html):
        cap, src = m.group(1).strip(), m.group(2)
        mm = re.match(r"^(\S+)\s+\[(qp|ms) p(\d+)\]\s+\[([\d.,\s]+)\]$", cap)
        assert mm, f"bad caption: {cap!r}"
        label, role, page = mm.group(1), mm.group(2), int(mm.group(3))
        bbox = tuple(round(float(x), 1) for x in mm.group(4).split(","))
        reg = {"label": label, "role": role, "page": page,
               "bbox": list(bbox), "src": src}
        regs.append(reg)
        frame_regions.append({**reg, "sheet": f.name})
    assert regs, f.name
    sheet_map[f.name] = regs

print(f"parsed: {len(frame_regions)} regions in {len(sheet_map)} sheets")
assert len(frame_regions) == 92, len(frame_regions)

# ---- expected order from the index: all qp (question order), then all ms
expected = []
for q in index["questions"]:
    for r in q["qp"]:
        expected.append((q["question"], "qp", r["page"],
                         tuple(round(float(x), 1) for x in r["bbox"]), list(r["bbox"])))
for q in index["questions"]:
    for r in q["ms"]:
        expected.append((q["question"], "ms", r["page"],
                         tuple(round(float(x), 1) for x in r["bbox"]), list(r["bbox"])))
assert len(expected) == 92, len(expected)

for fr, (num, role, page, bbox1, _raw) in zip(frame_regions, expected):
    assert fr["role"] == role and fr["page"] == page and fr["bbox"] == list(bbox1), \
        (fr, num, role, page, bbox1)
    want = ("Q" if role == "qp" else "M") + num
    assert fr["label"] == want, (fr["label"], want)
print("ordered 1:1 match with index: OK (49 qp + 43 ms)")

# ---- identify sheets containing the 18 changed QP regions
fix = json.loads((BR / "work/0472_2026_22_fixlist.json").read_text(encoding="utf-8"))
changed = [(ch["question"], "qp", ch["page"],
            tuple(round(float(x), 1) for x in ch["new"])) for ch in fix["qp_changes"]]
assert len(changed) == 18, len(changed)

changed_sheets = {}
for (num, role, page, bbox1) in changed:
    hits = [fr for fr in frame_regions
            if fr["label"] == "Q" + num and fr["role"] == "qp"
            and fr["page"] == page and tuple(fr["bbox"]) == bbox1]
    assert len(hits) == 1, (num, page, bbox1, hits)
    changed_sheets.setdefault(hits[0]["sheet"], []).append(hits[0]["label"])

visit_order = []
for f in qp_sheets:
    if f.name in changed_sheets:
        visit_order.append(f.name)
for f in ms_sheets:
    visit_order.append(f.name)

print()
print("== sheets to re-verify (18 changed QP regions + all 43 MS regions) ==")
for i, name in enumerate(visit_order, 1):
    regs = sheet_map[name]
    labels = ",".join(r["label"] for r in regs)
    tag = "qp" if "qp-regions" in name else "ms"
    print(f"{i:2}/{len(visit_order)}  [{tag}] {name}  ({len(regs)} regions: {labels})")

print()
print(f"changed QP sheets: {len(changed_sheets)}; ms sheets: {len(ms_sheets)}; "
      f"total visit: {len(visit_order)}")
print(f"regions to re-verify: {len(changed)} QP + 43 MS = {len(changed) + 43}")

MAP.write_text(json.dumps({
    "key": "0472/2026/Jun/22",
    "built_at": "2026-10-04",
    "index_sha256": None,  # filled by caller if needed
    "sheets": sheet_map,
    "visit_order": visit_order,
    "changed_qp_sheets": changed_sheets,
    "changed_qp": [{"question": n, "page": p, "bbox": list(b)} for n, _, p, b in changed],
}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"wrote {MAP.name}")
