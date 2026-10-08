import pymupdf as fitz
doc = fitz.open(r"C:/Users/weo/Desktop/api/tmp_audit_ielts/downloads/book_10.pdf")
page = doc[151]
for f in page.get_fonts(full=True):
    print(f)
