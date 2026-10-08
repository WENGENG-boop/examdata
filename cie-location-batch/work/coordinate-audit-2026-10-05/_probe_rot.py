import pymupdf
p = r"C:/Users/weo/Desktop/api/cie-location-batch/tmp/8238/2025-Jun-32/8238_s25_ms_32.pdf"
doc = pymupdf.open(p)
for i in (0,1,7):
    page = doc[i]
    print(f"--- page {i+1} rot={page.rotation} rect={page.rect} mediabox={page.mediabox} cropbox={page.cropbox} rotation_matrix={page.rotation_matrix}")
    bs = page.get_text("blocks")
    print("  first3 blocks:", [(round(b[0],1),round(b[1],1),round(b[2],1),round(b[3],1),b[4][:40].replace('\n',' ')) for b in bs[:3]])
    page.set_rotation(0)
    print(f"  after set_rotation(0): rot={page.rotation} rect={page.rect} mediabox={page.mediabox}")
    bs2 = page.get_text("blocks")
    print("  first3 blocks(rot0):", [(round(b[0],1),round(b[1],1),round(b[2],1),round(b[3],1),b[4][:40].replace('\n',' ')) for b in bs2[:3]])
