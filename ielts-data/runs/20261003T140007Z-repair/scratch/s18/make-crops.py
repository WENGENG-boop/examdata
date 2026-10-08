import fitz
pdf = fitz.open("tmp_audit_ielts/downloads/book_11.pdf")
out = "ielts-data/runs/20261003T140007Z-repair/scratch/s18"
# B1: page 124 right col y78-372 (page index 123)
pg = pdf[123]
clip = fitz.Rect(215, 78, 350, 372)
pix = pg.get_pixmap(clip=clip, matrix=fitz.Matrix(4.5, 4.5))
pix.save(f"{out}/page124-crop-Rcol.png")
# B2: page 124 left col y195-345
clip = fitz.Rect(0, 195, 260, 345)
pix = pg.get_pixmap(clip=clip, matrix=fitz.Matrix(5, 5))
pix.save(f"{out}/page124-crop-Lcol.png")
# B3: page 123 right col x250-440 y140-265 (page index 122)
pg3 = pdf[122]
clip = fitz.Rect(250, 140, 440, 265)
pix = pg3.get_pixmap(clip=clip, matrix=fitz.Matrix(5, 5))
pix.save(f"{out}/page123-crop-S3.png")
print("done")
