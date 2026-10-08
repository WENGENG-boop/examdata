"""逐页打印 MS 结构：表头、候选标签(x0<110)、竖线x、横线y，用于定型 ms_rows 重写。"""
import io
import re
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import pymupdf

ROOT = Path(__file__).resolve().parents[2]          # cie-location-batch
EX = Path("C:/Users/weo/Desktop/api/examdata")
MS_LABEL_RE = re.compile(r"^\d{1,2}(?:\([a-z]\))?$")

CASES = {
    "0472-s25": ROOT / "tmp/0472/2025-Jun-11",
    "0580-s24": EX / "tmpwork/agent-curl",
    "0580-fix": EX / "tests/fixtures",
    "0580-spe": EX / "tests/fixtures",
}
PATTERNS = {
    "0472-s25": "*ms*.pdf",
    "0580-s24": "0580_s24_ms_11.pdf",
    "0580-fix": "0580_ms_11.pdf",
    "0580-spe": "0580_ms_01_specimen.pdf",
}


def thin(page):
    v, h = [], []
    for d in page.get_drawings():
        r = d["rect"]
        w, hh = r.x1 - r.x0, r.y1 - r.y0
        if w < 2.5:
            v.append(round((r.x0 + r.x1) / 2, 1))
        elif hh < 2.5 and w >= 10:
            h.append((round((r.y0 + r.y1) / 2, 1), round(r.x0, 1), round(r.x1, 1)))
    return sorted(set(v)), sorted(set(h))


for name, d in CASES.items():
    hits = sorted(d.glob(PATTERNS[name]))
    print(f"\n######## {name}: {[p.name for p in hits]}")
    for path in hits:
        with pymupdf.open(path) as pdf:
            for i, page in enumerate(pdf):
                words = page.get_text("words")
                # 行聚合（简单按 y 聚）
                rows = {}
                for w in words:
                    key = (w[5], w[6])
                    rows.setdefault(key, []).append(w)
                lines = []
                for key, items in sorted(rows.items()):
                    items.sort(key=lambda w: w[0])
                    lines.append({
                        "text": " ".join(x[4] for x in items),
                        "x0": min(x[0] for x in items), "y0": min(x[1] for x in items),
                        "x1": max(x[2] for x in items), "y1": max(x[3] for x in items),
                    })
                lines.sort(key=lambda l: (round(l["y0"], 1), l["x0"]))
                hdr = [l for l in lines if l["text"].strip() == "Question"]
                labels = [l for l in lines
                          if MS_LABEL_RE.match(l["text"].strip()) and l["x0"] < 110]
                v, h = thin(page)
                print(f"  p{i+1}: 表头 {[(round(x['x0'],1), round(x['y0'],1), round(x['y1'],1)) for x in hdr]}")
                print(f"       标签 {[(x['text'].strip(), round(x['x0'],1), round(x['y0'],1)) for x in labels]}")
                print(f"       竖线x {v}")
                print(f"       横线y {[y for y,_,_ in h][:14]}{' ...' if len(h)>14 else ''} (共{len(h)})")
