import pymupdf
doc = pymupdf.open("tmpwork/probe/wec11.pdf")
for pno in (10, 11, 16, 31):
    print(f"===== QP p{pno} =====")
    print(doc[pno].get_text()[:700])
    print()
