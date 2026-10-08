"""Render verification strips for the 0472 volumes (temporary helper).

Each strip is drawn at zoom 4; a red horizontal line marks the current
index bbox top edge of the question, with short vertical ticks at x0.
"""
import fitz

BR = r"C:\Users\weo\Desktop\api\cie-location-batch"
TMP = BR + r"\tmp\0472"
Z = 4


def build(vol, pdf, strips, out):
    doc = fitz.open(TMP + "\\" + vol + "\\" + pdf)
    parts = []
    for (pno, y0, y1, caption, marks) in strips:
        page = doc[pno - 1]
        pix = page.get_pixmap(matrix=fitz.Matrix(Z, Z),
                              clip=fitz.Rect(0, y0, page.rect.width, y1))
        parts.append((y0, pix, caption, marks))
    W = max(pix.width for _, pix, _, _ in parts)
    H = sum(pix.height for _, pix, _, _ in parts) + 16 * (len(parts) - 1)
    outdoc = fitz.open()
    pg = outdoc.new_page(width=W, height=H)
    y = 0
    for (y0, pix, caption, marks) in parts:
        pg.insert_image(fitz.Rect(0, y, pix.width, y + pix.height), pixmap=pix)
        for (mx0, mx1, my) in marks:
            yy = y + (my - y0) * Z
            pg.draw_line(fitz.Point(mx0 * Z, yy), fitz.Point(mx1 * Z, yy),
                         color=(1, 0, 0), width=2)
            pg.draw_line(fitz.Point(mx0 * Z, yy), fitz.Point(mx0 * Z, yy + 80),
                         color=(1, 0, 0), width=2)
        pg.insert_text(fitz.Point(W - 620, y + 18), caption, fontsize=14,
                       color=(0, 0, 1))
        y += pix.height + 16
    pixout = pg.get_pixmap(matrix=fitz.Matrix(1, 1))
    pixout.save(out)
    print("saved", out, pixout.width, pixout.height)


build("2026-Jun-21", "0472_s26_qp_21.pdf", [
    (3, 30, 135, "21 qp p3 y30-135 top=58.7", [(92.4, 541.2, 58.7)]),
    (3, 375, 475, "21 qp p3 y375-475 top=400.5", [(92.4, 541.2, 400.5)]),
], TMP + r"\2026-Jun-21\crops\r4_21_p3.png")

build("2026-Jun-21", "0472_s26_qp_21.pdf", [
    (6, 395, 625, "21 qp p6 y395-625 tops=425.4,582.0", [(70.8, 531.2, 425.4), (70.8, 531.2, 582.0)]),
], TMP + r"\2026-Jun-21\crops\r4_21_p6.png")

build("2026-Jun-21", "0472_s26_qp_21.pdf", [
    (7, 185, 365, "21 qp p7 y185-365 top=215.1", [(64.8, 534.0, 215.1)]),
    (7, 365, 545, "21 qp p7 y365-545 top=371.6", [(64.8, 534.0, 371.6)]),
], TMP + r"\2026-Jun-21\crops\r4_21_p7.png")

build("2026-Jun-22", "0472_s26_qp_22.pdf", [
    (3, 30, 135, "22 qp p3 y30-135 top=58.7", [(92.4, 540.4, 58.7)]),
    (6, 415, 545, "22 qp p6 y415-545 top=447.4", [(70.8, 527.6, 447.4)]),
], TMP + r"\2026-Jun-22\crops\r4_22_p3p6.png")

build("2026-Jun-22", "0472_s26_qp_22.pdf", [
    (7, 30, 215, "22 qp p7 y30-215 tops=58.6,203.8", [(92.4, 540.4, 58.6), (92.4, 540.4, 203.8)]),
    (7, 215, 380, "22 qp p7 y215-380 top=349.0", [(92.4, 540.4, 349.0)]),
], TMP + r"\2026-Jun-22\crops\r4_22_p7.png")
