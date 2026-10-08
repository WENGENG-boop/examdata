import pymupdf
doc = pymupdf.open('downloads/edexcel/intgcse/2022-01.pdf')
print("pages:", doc.page_count)
for pno in [3]:
    page = doc[pno]
    if page.rotation:
        page.set_rotation(0)
    for ti, t in enumerate(page.find_tables()):
        rows = t.extract()
        print(f"== p{pno+1} t{ti}: {len(rows)}x{len(rows[0]) if rows else 0}")
        for r in rows[:6]:
            print("   ", r)
        if len(rows) > 6:
            print("   ...")
            for r in rows[-3:]:
                print("   ", r)
