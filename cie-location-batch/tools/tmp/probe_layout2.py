"""只读探针 2：0580 QP 右栏所有 token 形态；0580 MS p1-p3 与 specimen p5 的文本内容。

跑法: <venv python> tools/tmp/probe_layout2.py
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

import pymupdf

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

EX = Path("C:/Users/weo/Desktop/api/examdata")

print("=" * 30, "0580 s24 QP: 右栏 tokens (x0>460) 逐页")
qp = EX / "tmpwork/agent-curl/0580_s24_qp_11.pdf"
with pymupdf.open(qp) as pdf:
    for i, page in enumerate(pdf):
        words = page.get_text("words")
        right = [(round(w[0], 1), round(w[1], 1), w[4]) for w in words if w[0] > 460]
        if right:
            print(f"  p{i+1}: {right}")

print()
print("=" * 30, "0580 s24 QP: 含 '[' 的行 (全页)")
with pymupdf.open(qp) as pdf:
    for i, page in enumerate(pdf):
        words = page.get_text("words")
        grouped = {}
        for w in words:
            grouped.setdefault((w[5], w[6]), []).append(w)
        for key, items in sorted(grouped.items()):
            items.sort(key=lambda w: w[0])
            text = " ".join(w[4] for w in items)
            if "[" in text and i + 1 <= 10:
                xs = [round(w[0], 1) for w in items]
                print(f"  p{i+1}: x0s={xs} | {text[:110]}")

print()
print("=" * 30, "0580 s24 MS p1-p4 内容行")
ms = EX / "tmpwork/agent-curl/0580_s24_ms_11.pdf"
with pymupdf.open(ms) as pdf:
    for pno in (1, 2, 3, 4):
        page = pdf[pno - 1]
        words = page.get_text("words")
        grouped = {}
        for w in words:
            grouped.setdefault((w[5], w[6]), []).append(w)
        print(f"--- p{pno} ({len(words)} words) ---")
        for key, items in sorted(grouped.items(), key=lambda kv: (min(w[1] for w in kv[1]))):
            items.sort(key=lambda w: w[0])
            text = " ".join(w[4] for w in items)
            y0 = round(min(w[1] for w in items), 1)
            x0 = round(min(w[0] for w in items), 1)
            print(f"    y{y0:>6} x{x0:>6}: {text[:100]}")

print()
print("=" * 30, "0580 specimen MS p5 内容行")
sp = EX / "tests/fixtures/0580_ms_01_specimen.pdf"
with pymupdf.open(sp) as pdf:
    page = pdf[4]
    words = page.get_text("words")
    grouped = {}
    for w in words:
        grouped.setdefault((w[5], w[6]), []).append(w)
    for key, items in sorted(grouped.items(), key=lambda kv: (min(w[1] for w in kv[1]))):
        items.sort(key=lambda w: w[0])
        text = " ".join(w[4] for w in items)
        y0 = round(min(w[1] for w in items), 1)
        x0 = round(min(w[0] for w in items), 1)
        print(f"    y{y0:>6} x{x0:>6}: {text[:100]}")
