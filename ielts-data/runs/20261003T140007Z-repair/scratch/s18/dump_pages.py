import sys, pymupdf
doc = pymupdf.open("C:/Users/weo/Desktop/api/tmp_audit_ielts/downloads/book_10.pdf")
for p in [int(a) for a in sys.argv[1:]]:
    t = doc[p-1].get_text()
    print(f"========== PAGE {p} ==========")
    print(t[:2600])
