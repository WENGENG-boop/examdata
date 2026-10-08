# -*- coding: utf-8 -*-
"""Ink-margin check for each region of 0472/2025/Jun/12 (pure python, no numpy).

For every region render clip=(bbox+6pt margin) at zoom 4 grayscale; find the
distance (pt) from the bbox edge to the nearest ink inside, and whether any ink
falls in the 6pt margin band outside the bbox (mTop/mBot/mLeft/mRight).
"""
import json

import pymupdf as fitz

root = "C:/Users/weo/Desktop/api/cie-location-batch"
Z = 4          # px per pt
M = 6.0        # margin pt
TH = 235       # ink threshold (gray)


def check(doc, spec, tag, out):
    for item in spec:
        page = doc[item["page"] - 1]
        x0, y0, x1, y1 = item["bbox"]
        clip = fitz.Rect(x0 - M, y0 - M, x1 + M, y1 + M)
        pm = page.get_pixmap(clip=clip, matrix=fitz.Matrix(Z, Z),
                             colorspace=fitz.csGRAY)
        w, h, s = pm.width, pm.height, pm.samples
        mz = int(M * Z)
        ih, iw = h - 2 * mz, w - 2 * mz

        row_ink = []
        for r in range(ih):
            base = (mz + r) * w + mz
            row_ink.append(min(s[base:base + iw]) < TH)
        col_ink = []
        for c in range(iw):
            col_ink.append(min(s[mz * w + mz + c:(h - mz) * w + mz + c:w]) < TH)

        if not any(row_ink):
            out.write(f"{tag} {item['label']:5s} p{item['page']:2d} NO_INK\n")
            continue
        rows = [i for i, v in enumerate(row_ink) if v]
        cols = [i for i, v in enumerate(col_ink) if v]
        top_d = rows[0] / Z
        bot_d = (ih - 1 - rows[-1]) / Z
        left_d = cols[0] / Z
        right_d = (iw - 1 - cols[-1]) / Z
        m_top = min(s[:mz * w]) < TH
        m_bot = min(s[(h - mz) * w:]) < TH
        m_left = any(min(s[r * w:r * w + mz]) < TH for r in range(h))
        m_right = any(min(s[r * w + w - mz:r * w + w]) < TH for r in range(h))
        flags = []
        if top_d < 1.0: flags.append("TOP_HUG")
        if bot_d < 1.0: flags.append("BOT_HUG")
        if left_d < 1.0: flags.append("LEFT_HUG")
        if right_d < 1.0: flags.append("RIGHT_HUG")
        if m_top: flags.append("mTop")
        if m_bot: flags.append("mBot")
        if m_left: flags.append("mLeft")
        if m_right: flags.append("mRight")
        out.write(f"{tag} {item['label']:5s} p{item['page']:2d} "
                  f"t={top_d:4.1f} b={bot_d:4.1f} l={left_d:4.1f} r={right_d:4.1f} "
                  f"| {' '.join(flags) if flags else 'ok'}\n")


qp = fitz.open(root + "/tmp/0472/2025-Jun-12/0472_s25_qp_12.pdf")
ms = fitz.open(root + "/tmp/0472/2025-Jun-12/0472_s25_ms_12.pdf")
spec_qp = json.load(open(root + "/work/spec-0472-2025-Jun-12-qp.json", encoding="utf-8"))
spec_ms = json.load(open(root + "/work/spec-0472-2025-Jun-12-ms.json", encoding="utf-8"))

lines = []
check(qp, spec_qp, "QP", type("W", (), {"write": lines.append})())
check(ms, spec_ms, "MS", type("W", (), {"write": lines.append})())
txt = "".join(lines)
open(root + "/work/0472-12-edges.txt", "w", encoding="utf-8").write(txt)
print(txt)
