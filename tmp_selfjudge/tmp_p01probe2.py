import sqlite3, re
con = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
cur = con.cursor()

def q_with_kw(kw, limit=40, unit='WCH12'):
    cur.execute("""
      SELECT q.id, q.number_label, q.marks, t.code, substr(q.stem_text,1,120)
      FROM question q
      JOIN question_taxonomy qt ON qt.question_id=q.id
      JOIN taxonomy_node t ON t.id=qt.node_id
      WHERE t.code LIKE ? AND q.stem_text LIKE ?
      ORDER BY q.id
    """, (unit+'%', '%'+kw+'%'))
    rows = cur.fetchall()
    print(f'### KW="{kw}" in {unit}: {len(rows)} rows')
    for r in rows[:limit]:
        stem = re.sub(r'\s+', ' ', r[4] or '')
        print(f'  [{r[0]}] n={r[1]} m={r[2]} {r[3]}: {stem[:110]}')
    if len(rows) > limit:
        print(f'  ... and {len(rows)-limit} more')
    print()

for kw in ['atomisation', 'bond enthalpy', 'mean bond', 'percentage purity', 'Avogadro',
           'decomposes on heating', 'decomposes', 'Benedict', 'shape', 'vaporisation',
           'moles of', 'sodium hydroxide solution', 'flame test', 'precipitate']:
    q_with_kw(kw)
