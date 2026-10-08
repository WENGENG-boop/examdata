import sqlite3, re
con = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
cur = con.cursor()

# search WCH12 questions (those having any WCH12 taxonomy) with normalized stem
def q_with_kw(kw, limit=60):
    cur.execute("""
      SELECT DISTINCT q.id, q.number_label, q.marks,
             (SELECT group_concat(t2.code,',') FROM question_taxonomy qt2 JOIN taxonomy_node t2 ON t2.id=qt2.node_id WHERE qt2.question_id=q.id),
             substr(q.stem_text,1,220)
      FROM question q
      JOIN question_taxonomy qt ON qt.question_id=q.id
      JOIN taxonomy_node t ON t.id=qt.node_id
      WHERE t.code LIKE 'WCH12%'
        AND REPLACE(REPLACE(q.stem_text, char(10), ' '), char(13), ' ') LIKE ?
      ORDER BY q.id
    """, ('%'+kw+'%',))
    rows = cur.fetchall()
    print(f'### KW="{kw}": {len(rows)} rows')
    for r in rows[:limit]:
        stem = re.sub(r'\s+', ' ', r[4] or '')
        print(f'  [{r[0]}] n={r[1]} m={r[2]} codes={r[3]}: {stem[:170]}')
    if len(rows) > limit:
        print(f'  ... and {len(rows)-limit} more')
    print()

for kw in ['hot sodium hydroxide', 'hot alkali', 'hot concentrated', 'hot NaOH',
           'concentrated sodium hydroxide', 'hot aqueous', 'hot potassium hydroxide',
           'hot hydroxide', 'disproportionation']:
    q_with_kw(kw)

# all questions currently coded 8.26 or 8.27 in WCH12
for code in ['WCH12-8.26','WCH12-8.27']:
    cur.execute("""
      SELECT q.id, q.number_label, q.marks, substr(q.stem_text,1,150)
      FROM question q JOIN question_taxonomy qt ON qt.question_id=q.id
      JOIN taxonomy_node t ON t.id=qt.node_id
      WHERE t.code=? ORDER BY q.id
    """, (code,))
    rows = cur.fetchall()
    print(f'===== all coded {code}: {len(rows)} =====')
    for r in rows:
        stem = re.sub(r'\s+', ' ', r[3] or '')
        print(f'  [{r[0]}] n={r[1]} m={r[2]}: {stem[:130]}')
    print()
