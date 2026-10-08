import pymupdf, os, struct

BASE = "ielts-data/runs/20261003T140007Z-repair/scratch/s18"
FDIR = os.path.join(BASE, "fonts")
os.makedirs(FDIR, exist_ok=True)

doc = pymupdf.open("tmp_audit_ielts/downloads/book_10.pdf")
for xref, tag in ((1378, "STSSTH"), (1701, "FJRRHL"), (1383, "DKXCSF")):
    base, ext, subtype, buf = doc.extract_font(xref)
    path = os.path.join(FDIR, f"{tag}.{ext}")
    with open(path, "wb") as f:
        f.write(buf)
    print(f"xref {xref} {base} ext={ext} subtype={subtype} bytes={len(buf)} -> {path}")
    # quick table directory parse
    if len(buf) >= 12:
        n = struct.unpack(">H", buf[4:6])[0]
        print(f"  tables: {n}")
        for i in range(n):
            off = 12 + 16*i
            tag4 = buf[off:off+4].decode('latin1')
            toff, tlen = struct.unpack(">II", buf[off+8:off+16])
            print(f"    {tag4} off={toff} len={tlen}")
doc.close()
