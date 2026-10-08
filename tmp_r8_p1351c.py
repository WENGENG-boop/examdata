import sqlite3, json, re
con = sqlite3.connect('.data/examdata.db')
con.row_factory = sqlite3.Row
cur = con.cursor()

def norm(s):
    return re.sub(r'\s+', ' ', s or '').strip()

stems = {}
for r in cur.execute("SELECT id, stem_text FROM question WHERE paper_id=1351"):
    stems[r['id']] = r['stem_text'] or ''

print("=== tail 3000 of 45905 stem ===")
print(stems[45905][-3000:])
print("\n=== FULL 45913 stem (14794) ===")
print(stems[45913])
