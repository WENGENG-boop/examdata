import sqlite3, re
con = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
cur = con.cursor()

# 1) full attrs of 8.26 and 8.27
for code in ['WCH12-8.26','WCH12-8.27','WCH12-8.19']:
    cur.execute("SELECT id, code, name, attrs FROM taxonomy_node WHERE code=?", (code,))
    r = cur.fetchone()
    print(f'===== {code} id={r[0]} name={r[2]} =====')
    print(r[3])
    print()

# 2) search WCH12 stems for hot-alkali keywords
def q_with_kw(kw, limit=40):
    cur.execute("""
      SELECT q.id, q.number_label, q.marks,
             (SELECT group_concat(t.code,',') FROM question_taxonomy qt JOIN taxonomy_node t ON t.id=qt.node_id WHERE qt.question_id=q.id),
             substr(q.stem_text,1,200)
      FROM question q
      WHERE q.stem_text LIKE ?
      ORDER BY q.id
    """, ('%'+kw+'%',))
    rows = cur.fetchall()
    print(f'### KW="{kw}": {len(rows)} rows')
    for r in rows[:limit]:
        stem = re.sub(r'\s+', ' ', r[4] or '')
        print(f'  [{r[0]}] n={r[1]} m={r[2]} codes={r[3]}: {stem[:160]}')
    if len(rows) > limit:
        print(f'  ... and {len(rows)-limit} more')
    print()

for kw in ['hot sodium hydroxide', 'hot alkali', 'hot concentrated', 'hot NaOH',
           'concentrated sodium hydroxide', 'hot aqueous', 'sodium hydroxide']:
    q_with_kw(kw)

# 3) 33857 itself + paper siblings around it
cur.execute("SELECT id, number_label, marks, kind, stem_text FROM question WHERE id=33857")
r = cur.fetchone()
print(f'===== 33857 n={r[1]} m={r[2]} kind={r[3]} =====')
print(r[4])
print()
cur.execute("""SELECT t.code, qt.source FROM question_taxonomy qt JOIN taxonomy_node t ON t.id=qt.node_id WHERE qt.question_id=33857""")
print('33857 TAX:', cur.fetchall())
