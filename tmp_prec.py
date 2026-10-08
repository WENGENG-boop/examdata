"""Search WIT12 stems for keywords; print qid, paper, label, tax code, stem snippet.
Usage: python tmp_prec.py kw:tabindex kw:attribute tax:WIT12-7.1
"""
import sqlite3, sys
con = sqlite3.connect('.data/examdata.db')
con.row_factory = sqlite3.Row
cur = con.cursor()

WIT12_PAPERS = (1327,1328,1335,1338,1342,1344,1348,1353)

for arg in sys.argv[1:]:
    if arg == 'tables':
        for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
            print(r[0])
        continue
    if arg.startswith('tax:'):
        code = arg[4:]
        for r in cur.execute("SELECT code, name FROM taxonomy_node WHERE code LIKE ? ORDER BY code", (code+'%',)):
            print(f"TAX {r['code']} | {r['name']}")
        continue
    kw = arg[3:] if arg.startswith('kw:') else arg
    print(f"===== keyword: {kw} =====")
    rows = cur.execute("""
        SELECT q.id, q.paper_id, q.number_label,
               replace(substr(q.stem_text,1,230),char(10),' ') AS stem,
               tn.code AS tax
        FROM question q
        LEFT JOIN question_taxonomy qt ON qt.question_id=q.id
        LEFT JOIN taxonomy_node tn ON tn.id=qt.node_id
        WHERE q.stem_text LIKE ? AND q.paper_id IN (1327,1328,1335,1338,1342,1344,1348,1353)
        ORDER BY q.id
    """, (f'%{kw}%',)).fetchall()
    for r in rows:
        print(f"  {r['id']} p{r['paper_id']} #{r['number_label']} [{r['tax'] or '-'}] {r['stem']}")
    print(f"  ({len(rows)} rows)")
