import sys, json
import fitz
pdf = r"C:/Users/weo/Desktop/api/tmp_audit_ielts/downloads/book_10.pdf"
doc = fitz.open(pdf)
page = doc[152]  # 0-based -> page 153
print("== fonts on page 153 (0-based 152) ==")
for f in page.get_fonts(full=True):
    print(f)
