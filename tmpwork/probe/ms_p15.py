import pymupdf
doc = pymupdf.open("tmpwork/probe/wec11_rms.pdf")
for pno in (5, 15):
    print(f"===== MS p{pno} =====")
    print(doc[pno].get_text()[:900])
    print()
