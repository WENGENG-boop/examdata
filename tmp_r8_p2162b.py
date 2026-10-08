import sqlite3, re, fitz
con = sqlite3.connect('.data/examdata.db'); con.row_factory = sqlite3.Row
cur = con.cursor()

for qid in (64527, 64529, 64523, 64525):
    stem = cur.execute("SELECT stem_text FROM question WHERE id=?", (qid,)).fetchone()['stem_text'] or ''
    print(f"\n########## {qid} stem len={len(stem)} — tail 2600 ##########")
    print(stem[-2600:])

path = '.data/artifacts/bd/8d/bd8dd8c5e00d0b7d9a5890c95e56785c68d51ab1a6d954c6931714079a1a4c9f.pdf'
doc = fitz.open(path)
print(f"\n\n=== PDF pages 11-15 ===")
for pno in range(10, 15):
    page = doc[pno]
    lines = [l.strip() for l in page.get_text().splitlines() if l.strip()]
    print(f"\n----- PAGE {pno+1} -----")
    for l in lines:
        if re.match(r'^\(?\d{1,2}\)?\s*$', l) or 'Total for Question' in l or re.match(r'^(Total|BLANK|QUESTION|\*|Turn over)', l) or re.match(r'^\d{1,2}\s', l) or re.match(r'^\([a-z]+\)', l) or re.match(r'^\(i+\)', l) or re.match(r'^\([ivx]+\)', l):
            print("   >", l[:110])
con.close()
