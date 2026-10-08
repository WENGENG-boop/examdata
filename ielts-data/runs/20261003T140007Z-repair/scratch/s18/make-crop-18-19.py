import fitz
pdf = fitz.open("tmp_audit_ielts/downloads/book_11.pdf")
out = "ielts-data/runs/20261003T140007Z-repair/scratch/s18"
pg = pdf[123]
clip = fitz.Rect(0, 320, 260, 400)
pix = pg.get_pixmap(clip=clip, matrix=fitz.Matrix(5, 5))
pix.save(f"{out}/page124-crop-Lcol-18-19.png")
print("done")
