import sqlite3, json, re
con = sqlite3.connect('.data/examdata.db')
con.row_factory = sqlite3.Row
cur = con.cursor()

print("=== p1351 nodes: stem preview + pages + Total-flag ===")
rows = cur.execute("""
SELECT id, parent_id, kind, number_label, number_path, display_order, marks,
       page_from, page_to, length(coalesce(stem_text,'')) AS stem_len,
       stem_text
FROM question WHERE paper_id=1351 ORDER BY display_order
""").fetchall()
for r in rows:
    stem = r['stem_text'] or ''
    flat = re.sub(r'\s+', ' ', stem)[:150]
    totals = re.findall(r'Total for Question (\d+)', stem)
    print(f"id={r['id']} parent={r['parent_id']} kind={r['kind']} label={r['number_label']!r} path={r['number_path']!r} order={r['display_order']} marks={r['marks']} pages={r['page_from']}-{r['page_to']} stemlen={r['stem_len']} totals={totals}")
    print(f"   {flat}")

print("\n=== FULL stem of 45905 ===")
r = cur.execute("SELECT stem_text FROM question WHERE id=45905").fetchone()
print(r['stem_text'])

print("\n=== FULL stem of 45913 ===")
r = cur.execute("SELECT stem_text FROM question WHERE id=45913").fetchone()
print(r['stem_text'])

print("\n=== FULL stem of 45903 (for reference) ===")
r = cur.execute("SELECT stem_text FROM question WHERE id=45903").fetchone()
print(r['stem_text'][:1200])

print("\n=== bbox info 45905 / 45913 ===")
for qid in (45905, 45913, 45914, 45920):
    r = cur.execute("SELECT id,bbox_from,bbox_to FROM question WHERE id=?", (qid,)).fetchone()
    print(dict(r))
con.close()
