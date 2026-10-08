import fitz
pdf = fitz.open("tmp_audit_ielts/downloads/book_11.pdf")
out = "ielts-data/runs/20261003T140007Z-repair/scratch/s18"
pg = pdf[123]
pix = pg.get_pixmap(clip=fitz.Rect(0, 285, 230, 360), matrix=fitz.Matrix(6, 6))
pix.save(f"{out}/page124-stripA-16-19.png")
pix = pg.get_pixmap(clip=fitz.Rect(215, 60, 440, 170), matrix=fitz.Matrix(6, 6))
pix.save(f"{out}/page124-stripB-20-26.png")
print("done")
