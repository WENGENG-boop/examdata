import sqlite3
con = sqlite3.connect('.data/examdata.db')
con.row_factory = sqlite3.Row
cur = con.cursor()
WIT12_PAPERS = (1327,1328,1335,1338,1342,1344,1348,1353)
print('===== questions >=18 marks in WIT12 papers =====')
for r in cur.execute("""
    SELECT q.id, q.paper_id, q.number_label, q.marks, tn.code,
           replace(substr(q.stem_text,1,120),char(10),' ') AS stem
    FROM question q
    LEFT JOIN question_taxonomy qt ON qt.question_id=q.id
    LEFT JOIN taxonomy_node tn ON tn.id=qt.node_id
    WHERE q.paper_id IN (1327,1328,1335,1338,1342,1344,1348,1353) AND q.marks>=18
    ORDER BY q.paper_id, q.display_order"""):
    print(f"  {r['id']} p{r['paper_id']} #{r['number_label']} {r['marks']}mk [{r['code']}] {r['stem']}")
print()
print('===== stems mentioning liquid/responsive/fixed width =====')
for kw in ('liquid','fixed width','responsive'):
    print(f'--- {kw} ---')
    for r in cur.execute("""
        SELECT q.id, q.paper_id, q.number_label, q.marks, tn.code,
               replace(substr(q.stem_text,1,150),char(10),' ') AS stem
        FROM question q
        LEFT JOIN question_taxonomy qt ON qt.question_id=q.id
        LEFT JOIN taxonomy_node tn ON tn.id=qt.node_id
        WHERE q.paper_id IN (1327,1328,1335,1338,1342,1344,1348,1353) AND q.stem_text LIKE ?
        ORDER BY q.paper_id, q.display_order""", (f'%{kw}%',)):
        print(f"  {r['id']} p{r['paper_id']} #{r['number_label']} {r['marks']}mk [{r['code']}] {r['stem']}")
