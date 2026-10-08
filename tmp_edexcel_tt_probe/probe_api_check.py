import pymupdf
print("pymupdf", pymupdf.__version__)
doc = pymupdf.open('downloads/edexcel/gce/2018-06.pdf')
page = doc[3]
finder = page.find_tables()
print("finder type:", type(finder).__name__)
tables = list(finder)
print("tables:", len(tables))
for t in tables[:2]:
    print(" table rows:", len(t.rows), "cols:", len(t.rows[0].cells))
    cells = t.rows[1].cells if len(t.rows) > 1 else None
    print(" row1 cells:", cells)
    words = page.get_text("words", clip=pymupdf.Rect(cells[0])) if cells and cells[0] else []
    print(" words in cell0:", words[:6])
    break
doc.close()
