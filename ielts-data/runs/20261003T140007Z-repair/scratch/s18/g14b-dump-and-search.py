#!/usr/bin/env python
"""G14b: dump ocr20 OCR'd page text; search cam21 raw + all raw/derived for feature words."""
import json
import re
from pathlib import Path

ROOT = Path("C:/Users/weo/Desktop/api")
R = ROOT / "ielts-data/runs/20261003T140007Z-repair"
OUT = R / "scratch/s18/g14b-ocr20-dump.txt"
lines = []

# 1) dump ocr20 full-page OCR text
for name in ["ocr20-test1-p45-full", "ocr20-test2-p567-full", "ocr20-test3-p56-full", "ocr20-test4-p56-full"]:
    p = R / "derived/ocr20" / f"{name}.json"
    if not p.exists():
        continue
    j = json.loads(p.read_text(encoding="utf-8"))
    lines.append(f"===== {name} (dpi={j.get('dpi')}) =====")
    for pg in j.get("pages", []):
        words = pg.get("words", [])
        txt = " ".join(w["text"] for w in sorted(words, key=lambda w: (round(w["y0"] / 6), w["x0"])))
        lines.append(f"--- file_page {pg['file_page']} words={len(words)}")
        lines.append(txt[:2000])
    lines.append("")

# 2) feature words in ocr20 structs (top strips) too
for name in ["ocr20-test1-struct", "ocr20-test2-struct", "ocr20-test3-struct", "ocr20-test4-struct"]:
    p = R / "derived/ocr20" / f"{name}.json"
    if not p.exists():
        continue
    j = json.loads(p.read_text(encoding="utf-8"))
    allt = " ".join(w["text"] for pg in j.get("pages", []) for w in pg.get("words", []))
    for w in ["743002", "Costwise", "Argus", "Holman", "erosion", "beach", "electric", "fibre", "wooden"]:
        if w.lower() in allt.lower():
            lines.append(f"STRUCT HIT {name}: {w}")

OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"wrote {OUT}")

# 3) comprehensive feature search across raw + derived + runs
FEATURES = ["743002", "Costwise", "Argus", "Holman", "beach erosion", "beach", "erosion",
            "electric wire", "fibre optic", "wooden post", "glass cap", "acrylic",
            "International Finest", "roof garden", "permanent marker", "pavement"]
search_dirs = [
    ROOT / "ielts-data/raw",
    ROOT / "ielts-data/derived",
    ROOT / "tmp_audit_ielts/completeness_20261003",
]
hits = []
for d in search_dirs:
    for f in d.rglob("*"):
        if not f.is_file():
            continue
        if f.suffix.lower() not in (".json", ".txt", ".body", ".md", ".tsv", ".csv", ".html"):
            continue
        try:
            t = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        tl = t.lower()
        for w in FEATURES:
            if w.lower() in tl:
                hits.append(f"{w}\t{f.relative_to(ROOT)}")
hits_path = R / "scratch/s18/g14b-feature-hits-all-sources.txt"
hits_path.write_text("\n".join(hits) + "\n", encoding="utf-8")
print(f"feature hits: {len(hits)} -> {hits_path}")
for h in hits[:60]:
    print(h)
