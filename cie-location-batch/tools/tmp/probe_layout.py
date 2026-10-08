"""只读探针：核对 QP 分值 word 形态、合并子题行、MS 标签与表格线几何。

跑法: <venv python> tools/tmp/probe_layout.py
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

import pymupdf

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BATCH = Path("C:/Users/weo/Desktop/api/cie-location-batch")
EX = Path("C:/Users/weo/Desktop/api/examdata")

MS_LABEL_RE = re.compile(r"^\d{1,2}(?:\([a-z]\))?$")
MARK_WORD_RE = re.compile(r"^\[(\d{1,3})\]$")
MERGED_SUB_RE = re.compile(r"^(\d{1,2})\s*\(([a-z])\)")

MS_FILES = [
    ("0472/2025 MS", BATCH / "tmp/0472/2025-Jun-11/0472_s25_ms_11.pdf"),
    ("0580 s24 MS", EX / "tmpwork/agent-curl/0580_s24_ms_11.pdf"),
    ("0580 fixtures MS", EX / "tests/fixtures/0580_ms_11.pdf"),
    ("0580 specimen MS", EX / "tests/fixtures/0580_ms_01_specimen.pdf"),
]
QP_FILES = [
    ("0472/2025 QP", BATCH / "tmp/0472/2025-Jun-11/0472_s25_qp_11.pdf"),
    ("0580 s24 QP", EX / "tmpwork/agent-curl/0580_s24_qp_11.pdf"),
    ("0580 fixtures QP", EX / "tests/fixtures/0580_qp_11.pdf"),
]


def group_words(words):
    grouped = {}
    for w in words:
        grouped.setdefault((w[5], w[6]), []).append(w)
    lines = []
    for (block, line), items in sorted(grouped.items()):
        items.sort(key=lambda w: w[0])
        lines.append({"block": block, "line": line, "text": " ".join(w[4] for w in items),
                      "x0": min(w[0] for w in items), "y0": min(w[1] for w in items),
                      "x1": max(w[2] for w in items), "y1": max(w[3] for w in items),
                      "words": items})
    lines.sort(key=lambda l: (round(l["y0"], 1), l["x0"]))
    return lines


print("#" * 30, "MS probes")
for name, path in MS_FILES:
    print("=" * 90)
    print("MS:", name, path.name)
    if not path.exists():
        print("  (missing)")
        continue
    with pymupdf.open(path) as pdf:
        print("pages:", pdf.page_count)
        for i, page in enumerate(pdf):
            lines = group_words(page.get_text("words"))
            header = next((l for l in lines if l["text"].strip() == "Question" and l["x0"] < 100), None)
            band = (header["y0"] - 8, header["y1"] + 8) if header else None
            labels = [l for l in lines if MS_LABEL_RE.match(l["text"].strip()) and l["x0"] < 110]
            passed = [l for l in labels if band and l["y0"] >= band[0] - 1 and l["y1"] <= band[1] + 1]
            below = [l for l in labels if header and l["y0"] > header["y1"]]
            hlines = []
            for d in page.get_drawings():
                r = d["rect"]
                w, hh = r.x1 - r.x0, r.y1 - r.y0
                if hh < 2.5 and w >= 10:
                    hlines.append((round(r.x0, 1), round(r.x1, 1), round((r.y0 + r.y1) / 2, 1)))
            vxs = sorted({round((d["rect"].x0 + d["rect"].x1) / 2, 1) for d in page.get_drawings()
                          if (d["rect"].x1 - d["rect"].x0) < 2.5 and (d["rect"].y1 - d["rect"].y0) >= 5})
            print(f"  p{i+1} rot={page.rotation}: "
                  f"header={'y%.1f-%.1f x%.1f' % (header['y0'], header['y1'], header['x0']) if header else None}"
                  f" labels(x0<110)={len(labels)} band_pass={len(passed)} below_header={len(below)}")
            print(f"        labels: {[(l['text'], round(l['x0'],1), round(l['y0'],1), round(l['y1'],1)) for l in labels[:10]]}")
            print(f"        vxs(first 12): {vxs[:12]}")
            print(f"        hlines(first 8): {hlines[:8]}  (total {len(hlines)})")

print()
print("#" * 30, "QP probes")
for name, path in QP_FILES:
    print("=" * 90)
    print("QP:", name, path.name)
    if not path.exists():
        print("  (missing)")
        continue
    with pymupdf.open(path) as pdf:
        mark_words = []
        merged = []
        for i, page in enumerate(pdf):
            words = page.get_text("words")
            for w in words:
                if MARK_WORD_RE.match(w[4]):
                    mark_words.append((i + 1, round(w[0], 1), w[4]))
            for l in group_words(words):
                m = MERGED_SUB_RE.match(l["text"].strip())
                if m and l["x0"] < 95:
                    merged.append((i + 1, round(l["x0"], 1), l["text"][:60]))
        xs = [x for _, x, _ in mark_words]
        print(f"mark words total={len(mark_words)}  x0 min={min(xs) if xs else None} max={max(xs) if xs else None}"
              f"  x0<480 count={sum(1 for x in xs if x < 480)}")
        print(f"  sample: {mark_words[:8]}")
        print(f"  x0 in [480,530]: {[t for t in mark_words if 480 <= t[1] <= 530][:8]}")
        print(f"merged-sub lines: {len(merged)}")
        for row in merged[:15]:
            print("   ", row)
        # 看几个页面上带 '[' 的行的形态（分值是否与正文同行）
        if pdf.page_count >= 3:
            for pno in (1, min(2, pdf.page_count)):
                page = pdf[pdf.page_count - 1] if pno == 2 else pdf[pno - 1]
                sample = []
                for l in group_words(page.get_text("words")):
                    if "[" in l["text"] and l["x1"] > 460:
                        sample.append((round(l["x0"], 1), round(l["x1"], 1), l["text"][-50:]))
                print(f"  page {pdf.page_count if pno == 2 else pno} lines w/ '[' & x1>460: {sample[:6]}")
