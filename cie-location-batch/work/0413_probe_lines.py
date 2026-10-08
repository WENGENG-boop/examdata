from pathlib import Path
import pymupdf

PDF = Path(__file__).resolve().parents[1] / "tmp/0413/2026-Jun-11/0413_s26_ms_11.pdf"
with pymupdf.open(PDF) as doc:
    for page_no in (18, 19, 22, 25):
        page = doc[page_no - 1]
        pix = page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
        n = pix.n
        samples = pix.samples
        peaks = []
        for y in range(pix.height):
            dark = 0
            row = y * pix.width * n
            for x in range(40, pix.width - 40):
                i = row + x * n
                if samples[i] < 80 and samples[i + 1] < 80 and samples[i + 2] < 80:
                    dark += 1
            if dark > pix.width * 0.35:
                peaks.append((y, dark))
        # Collapse adjacent raster rows representing the same ruled line.
        groups = []
        for y, dark in peaks:
            if not groups or y > groups[-1][-1][0] + 1:
                groups.append([])
            groups[-1].append((y, dark))
        print(f"PAGE {page_no}: {pix.width}x{pix.height}, rotation={page.rotation}")
        print([(round(sum(y for y, _ in g) / len(g), 1), max(d for _, d in g)) for g in groups])
