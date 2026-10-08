import sqlite3, re, fitz
con = sqlite3.connect('.data/examdata.db'); con.row_factory = sqlite3.Row
cur = con.cursor()

stem = cur.execute("SELECT stem_text FROM question WHERE id=23711").fetchone()['stem_text']
ns = re.sub(r'\s+', ' ', stem)
for m in re.finditer(r'Total for Question', ns):
    print("...context:", ns[max(0,m.start()-120):m.start()+80].strip())
    print("---")

path = '.data/artifacts/1b/38/1b386a4681c9e6a743fbe2707d95d024a947c9f3d0932d2729347cf9dcba9031.pdf'
doc = fitz.open(path)
print("\n\n=== PDF pages 4-11 (1-indexed) ===")
for pno in range(3, 11):
    page = doc[pno]
    txt = page.get_text()
    lines = [l for l in txt.splitlines() if l.strip()]
    print(f"\n----- PAGE {pno+1} ----- ({len(lines)} lines)")
    for l in lines:
        ls = l.strip()
        if re.match(r'^\(?\d{1,2}\)?\s*$', ls) or 'Total for Question' in ls or re.match(r'^(Total|BLANK|QUESTION|\*|Turn over)', ls) or re.match(r'^\d+\s', ls) or re.match(r'^\([a-z]+\)', ls) or re.match(r'^\(i+\)', ls) or re.match(r'^\([ivx]+\)', ls):
            print("   >", ls[:110])
con.close()
