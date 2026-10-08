"""Render label-region crops from local PDFs for visual confirmation of Q4 lettering."""
import os
import sys
from pathlib import Path

import fitz

BR = Path(r"C:/Users/weo/Desktop/api/cie-location-batch")
os.chdir(BR)

JOBS = [
    # (pdf, page(1-based), clip rect, out)
    ("tmp/0472/2025-Jun-21/0472_s25_qp_21.pdf", 11, (60, 330, 545, 410),
     "tmp/0472/2025-Jun-21/crops/_audit_4i_label.png"),
    ("tmp/0472/2025-Jun-22/0472_s25_qp_22.pdf", 9, (60, 330, 545, 410),
     "tmp/0472/2025-Jun-22/crops/_audit_4h_label.png"),
    ("tmp/0472/2025-Jun-22/0472_s25_qp_22.pdf", 9, (60, 395, 545, 470),
     "tmp/0472/2025-Jun-22/crops/_audit_4hi_label.png"),
    ("tmp/0472/2026-Jun-21/0472_s26_qp_21.pdf", 9, (85, 295, 545, 370),
     "tmp/0472/2026-Jun-21/crops/_audit_4i_label.png"),
    ("tmp/0472/2026-Jun-22/0472_s26_qp_22.pdf", 9, (85, 340, 545, 430),
     "tmp/0472/2026-Jun-22/crops/_audit_4hi_label.png"),
    ("tmp/0472/2026-Jun-22/0472_s26_qp_22.pdf", 9, (85, 280, 545, 360),
     "tmp/0472/2026-Jun-22/crops/_audit_4h_label.png"),
]

for pdf_rel, page_no, rect, out_rel in JOBS:
    pdf = BR / pdf_rel
    out = BR / out_rel
    out.parent.mkdir(parents=True, exist_ok=True)
    if not pdf.is_file():
        print(f"MISSING {pdf}")
        continue
    doc = fitz.open(pdf)
    page = doc[page_no - 1]
    clip = fitz.Rect(*rect)
    pix = page.get_pixmap(matrix=fitz.Matrix(3.0, 3.0), clip=clip, alpha=False)
    pix.save(out)
    print(f"saved {out_rel}  {pix.width}x{pix.height}")
    doc.close()
