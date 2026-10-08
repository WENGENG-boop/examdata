import sys, fitz
pdf = r"C:/Users/weo/Desktop/api/tmp_audit_ielts/downloads/book_3.pdf"
page_no = int(sys.argv[1])
doc = fitz.open(pdf)
page = doc[page_no-1]
print("images:", page.get_images(full=True))
print("image_info blocks:")
for b in page.get_text("dict")["blocks"]:
    if b["type"]==1:
        print(" ", b["bbox"], b.get("width"), b.get("height"))
