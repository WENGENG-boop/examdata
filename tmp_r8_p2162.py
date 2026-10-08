import sqlite3, re, fitz
con = sqlite3.connect('.data/examdata.db'); con.row_factory = sqlite3.Row
cur = con.cursor()

print("=== p2162 structure ===")
rows = cur.execute("SELECT id,parent_id,kind,number_label,number_path,marks,display_order,page_from,page_to,length(stem_text) as L, stem_text FROM question WHERE paper_id=2162 ORDER BY display_order").fetchall()
for r in rows:
    flat = re.sub(r'\s+',' ', r['stem_text'] or '')[:95]
    print(f"id={r['id']} par={r['parent_id']} {r['kind']:8s} {r['number_path']:10s} m={str(r['marks']):4s} p={r['page_from']}-{r['page_to']} L={r['L']:6d} | {flat}")

path = '.data/artifacts/bd/8d/bd8dd8c5e00d0b7d9a5890c95e56785c68d51ab1a6d954c6931714079a1a4c9f.pdf'
doc = fitz.open(path)
print(f"\n=== PDF pages 5-10 (of {doc.page_count}) ===")
for pno in range(4, 10):
    page = doc[pno]
    lines = [l.strip() for l in page.get_text().splitlines() if l.strip()]
    print(f"\n----- PAGE {pno+1} -----")
    for l in lines:
        if re.match(r'^\(?\d{1,2}\)?\s*$', l) or 'Total for Question' in l or re.match(r'^(Total|BLANK|QUESTION|\*|Turn over)', l) or re.match(r'^\d{1,2}\s', l) or re.match(r'^\([a-z]+\)', l) or re.match(r'^\(i+\)', l) or re.match(r'^\([ivx]+\)', l):
            print("   >", l[:110])
con.close()
