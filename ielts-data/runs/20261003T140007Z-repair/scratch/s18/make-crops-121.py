import fitz
pdf = fitz.open("tmp_audit_ielts/downloads/book_11.pdf")
out = "ielts-data/runs/20261003T140007Z-repair/scratch/s18"
pg = pdf[120]  # page 121 = t3L key
for name, clip in [
    ("page121-crop-Ltop.png",  fitz.Rect(0, 120, 260, 265)),
    ("page121-crop-Lbot.png",  fitz.Rect(0, 265, 260, 400)),
    ("page121-crop-Rtop.png",  fitz.Rect(250, 120, 440, 265)),
    ("page121-crop-Rbot.png",  fitz.Rect(250, 265, 440, 400)),
]:
    pix = pg.get_pixmap(clip=clip, matrix=fitz.Matrix(5, 5))
    pix.save(f"{out}/{name}")
pg3 = pdf[122]  # page 123 = t4L key
pix = pg3.get_pixmap(clip=fitz.Rect(250, 245, 440, 320), matrix=fitz.Matrix(6, 6))
pix.save(f"{out}/page123-crop-28-30.png")
print("done")
