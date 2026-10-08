import pymupdf
doc = pymupdf.open("C:/Users/weo/Desktop/api/tmp_audit_ielts/downloads/book_10.pdf")
for i in range(90, 125):
    t = doc[i].get_text()
    for kw in ["Section 3", "Questions 28", "Questions 29", "Questions 27", "SECTION 3"]:
        if kw in t:
            print(f"--- page idx {i} (1-based {i+1}) contains {kw!r}")
            break
