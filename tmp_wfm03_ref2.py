import sqlite3
con = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
con.row_factory = sqlite3.Row

def sample(label, sql, n=12):
    print(f"\n=== {label} ===")
    for r in con.execute(sql).fetchall()[:n]:
        print(f"  [{r['id']}] {r['code']} | {(r['t'] or '')[:150].replace(chr(10),' / ')}")

sample("5.3 samples", """
SELECT q.id, tn.code, substr(q.stem_text,1,200) t FROM question_taxonomy qt
JOIN taxonomy_node tn ON tn.id=qt.node_id JOIN question q ON q.id=qt.question_id
WHERE tn.code='WFM03-5.3' ORDER BY q.id LIMIT 12""")

sample("shortest distance plane questions", """
SELECT q.id, tn.code, substr(q.stem_text,1,200) t FROM question_taxonomy qt
JOIN taxonomy_node tn ON tn.id=qt.node_id JOIN question q ON q.id=qt.question_id
WHERE tn.code LIKE 'WFM03-5.%' AND q.stem_text LIKE '%distance%' ORDER BY q.id LIMIT 12""")

sample("4.3/4.4 samples (substitution)", """
SELECT q.id, tn.code, substr(q.stem_text,1,150) t FROM question_taxonomy qt
JOIN taxonomy_node tn ON tn.id=qt.node_id JOIN question q ON q.id=qt.question_id
WHERE tn.code IN ('WFM03-4.3','WFM03-4.4') AND q.stem_text LIKE '%substitution%' ORDER BY q.id LIMIT 16""")

print("\n=== family of 37720 (Q8 substitution chain) ===")
for f in [37720,37721,37722]:
    r = con.execute("SELECT id, number_label, substr(stem_text,1,300) t FROM question WHERE id=?", (f,)).fetchone()
    tax = con.execute("""SELECT tn.code FROM question_taxonomy qt JOIN taxonomy_node tn ON tn.id=qt.node_id
        WHERE qt.question_id=?""", (f,)).fetchall()
    print(f"  [{f}] {r['number_label']}: {(r['t'] or '')[:200].replace(chr(10),' / ')}")
    print("      TAX:", "; ".join(t['code'] for t in tax) or "--")

sample("6.1 samples", """
SELECT q.id, tn.code, substr(q.stem_text,1,150) t FROM question_taxonomy qt
JOIN taxonomy_node tn ON tn.id=qt.node_id JOIN question q ON q.id=qt.question_id
WHERE tn.code='WFM03-6.1' ORDER BY q.id LIMIT 10""")

sample("image of vector / matrix transform samples", """
SELECT q.id, tn.code, substr(q.stem_text,1,200) t FROM question_taxonomy qt
JOIN taxonomy_node tn ON tn.id=qt.node_id JOIN question q ON q.id=qt.question_id
WHERE tn.code LIKE 'WFM03-6.%' AND q.stem_text LIKE '%image%' ORDER BY q.id LIMIT 12""")
con.close()
