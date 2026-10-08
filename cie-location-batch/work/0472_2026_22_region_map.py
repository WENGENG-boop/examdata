import json
import struct
import sys
from pathlib import Path

BR = Path(r"C:/Users/weo/Desktop/api/cie-location-batch")
key = "0472/2026-Jun-22"
idx = json.loads((BR / "indexes" / key / "cie-index.json").read_text(encoding="utf-8"))


def png_size(p: Path):
    with open(p, "rb") as f:
        d = f.read(26)
    w, h = struct.unpack(">II", d[16:24])
    return w, h


print("== questions ==")
for q in idx["questions"]:
    qp = " ".join(f"p{r['page']}({r['bbox'][0]:.0f},{r['bbox'][1]:.0f},{r['bbox'][2]:.0f},{r['bbox'][3]:.0f})" for r in q["qp"])
    ms = " ".join(f"p{r['page']}({r['bbox'][0]:.0f},{r['bbox'][1]:.0f},{r['bbox'][2]:.0f},{r['bbox'][3]:.0f})" for r in q["ms"])
    print(f"{q['question']:<8} parent={str(q.get('parent')):<7} qp[{len(q['qp'])}] {qp}   ms[{len(q['ms'])}] {ms}")

print()
print("== crops ==")
crops = sorted((BR / "tmp" / key / "crops").glob("*.png"))
for p in crops:
    w, h = png_size(p)
    print(f"{p.name:<28} {w:5}x{h:<5} disp_h@1000w={round(h * 1000 / w)}")
