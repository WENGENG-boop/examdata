import sqlite3, re
con = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
cur = con.cursor()

# 1) hex dump around 'hot' in 33857 stem
cur.execute("SELECT stem_text FROM question WHERE id=33857")
s = cur.fetchone()[0]
i = s.find('hot')
print('context repr:', repr(s[i-20:i+60]))
print('codepoints:', [hex(ord(c)) for c in s[i:i+30]])
print()

# 2) attrs of 8.7
for code in ['WCH12-8.7','WCH12-8.8']:
    cur.execute("SELECT id, code, name, attrs FROM taxonomy_node WHERE code=?", (code,))
    r = cur.fetchone()
    print(f'===== {code} id={r[0]} =====')
    print(r[3])
    print()

# 3) MS for 33857
cur.execute("""SELECT answer_text FROM mark_scheme_entry WHERE question_id=33857""")
rows = cur.fetchall()
print(f'===== MS 33857: {len(rows)} entries =====')
for r in rows:
    print(r[0][:800])
print()

# 4) search WCH12 for any stem containing 'hot' (normalized), print codes
cur.execute("""
  SELECT DISTINCT q.id, q.number_label,
         (SELECT group_concat(t2.code,',') FROM question_taxonomy qt2 JOIN taxonomy_node t2 ON t2.id=qt2.node_id WHERE qt2.question_id=q.id),
         substr(q.stem_text,1,200)
  FROM question q JOIN question_taxonomy qt ON qt.question_id=q.id
  JOIN taxonomy_node t ON t.id=qt.node_id
  WHERE t.code LIKE 'WCH12%'
    AND REPLACE(REPLACE(q.stem_text, char(10), ' '), char(13), ' ') LIKE '%hot %'
  ORDER BY q.id
""")
rows = cur.fetchall()
print(f'===== WCH12 stems with "hot ": {len(rows)} =====')
for r in rows:
    stem = re.sub(r'\s+', ' ', r[3] or '')
    print(f'  [{r[0]}] n={r[1]} codes={r[2]}: {stem[:150]}')
print()

# 5) iodine + hydroxide co-occurrence
cur.execute("""
  SELECT DISTINCT q.id, q.number_label,
         (SELECT group_concat(t2.code,',') FROM question_taxonomy qt2 JOIN taxonomy_node t2 ON t2.id=qt2.node_id WHERE qt2.question_id=q.id),
         substr(q.stem_text,1,200)
  FROM question q JOIN question_taxonomy qt ON qt.question_id=q.id
  JOIN taxonomy_node t ON t.id=qt.node_id
  WHERE t.code LIKE 'WCH12%'
    AND REPLACE(REPLACE(q.stem_text, char(10), ' '), char(13), ' ') LIKE '%iodine%'
    AND REPLACE(REPLACE(q.stem_text, char(10), ' '), char(13), ' ') LIKE '%hydroxide%'
  ORDER BY q.id
""")
rows = cur.fetchall()
print(f'===== WCH12 iodine+hydroxide: {len(rows)} =====')
for r in rows:
    stem = re.sub(r'\s+', ' ', r[3] or '')
    print(f'  [{r[0]}] n={r[1]} codes={r[2]}: {stem[:150]}')
