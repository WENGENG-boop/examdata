import sqlite3
con = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
con.row_factory = sqlite3.Row

print("=== WFM03 label distribution ===")
rows = con.execute("""SELECT tn.code, count(*) c FROM question_taxonomy qt
    JOIN taxonomy_node tn ON tn.id=qt.node_id WHERE tn.code LIKE 'WFM03-%'
    GROUP BY tn.code ORDER BY tn.code""").fetchall()
for r in rows: print(f"  {r['code']}: {r['c']}")

def sample(label, sql, n=4):
    print(f"\n=== {label} ===")
    for r in con.execute(sql).fetchall()[:n]:
        print(f"  [{r['id']}] {r['code']} | {(r['t'] or '')[:130].replace(chr(10),' / ')}")

sample("cosh/sinh equation questions", """
SELECT q.id, tn.code, substr(q.stem_text,1,200) t FROM question_taxonomy qt
JOIN taxonomy_node tn ON tn.id=qt.node_id JOIN question q ON q.id=qt.question_id
WHERE tn.code LIKE 'WFM03-%' AND (q.stem_text LIKE '%cosh%' OR q.stem_text LIKE '%sinh%')
ORDER BY q.id LIMIT 30""", 30)

sample("hyperbola a,b questions", """
SELECT q.id, tn.code, substr(q.stem_text,1,200) t FROM question_taxonomy qt
JOIN taxonomy_node tn ON tn.id=qt.node_id JOIN question q ON q.id=qt.question_id
WHERE tn.code LIKE 'WFM03-2.%' AND q.stem_text LIKE '%hyperbola%'
ORDER BY q.id LIMIT 20""", 20)
con.close()
