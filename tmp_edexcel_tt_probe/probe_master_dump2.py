import pymupdf
doc = pymupdf.open('downloads/edexcel/intgcse/2022-01.pdf')
for pno in [6,7,8]:
    page = doc[pno]
    if page.rotation:
        page.set_rotation(0)
    for ti, t in enumerate(page.find_tables()):
        rows = t.extract()
        print(f"== p{pno+1} t{ti}: {len(rows)}x{len(rows[0]) if rows else 0}")
        for r in rows[:5]:
            print("   ", r)
        if len(rows) > 5:
            print("   ... total", len(rows), "rows")
