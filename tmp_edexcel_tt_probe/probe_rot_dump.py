import pymupdf
doc = pymupdf.open('downloads/edexcel/intgcse/2020-01.pdf')
page = doc[3]
if page.rotation:
    page.set_rotation(0)
for ti, t in enumerate(page.find_tables()):
    rows = t.extract()
    print(f"== p4 t{ti}: {len(rows)}x{len(rows[0]) if rows else 0}")
    for ri, r in enumerate(rows):
        print(f"  r{ri}: {r[0]!r} | {r[1]!r} | {r[2]!r}")
