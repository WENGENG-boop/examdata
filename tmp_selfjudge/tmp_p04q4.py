import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')
con = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
cur = con.cursor()
def q(label, like, extra=''):
    print(f'===== {label} =====')
    sql = ("SELECT n.code, count(*), substr(group_concat(q.id),1,150) FROM question q "
           "JOIN question_taxonomy t ON q.id=t.question_id "
           "JOIN taxonomy_node n ON t.node_id=n.id "
           "WHERE q.stem_text LIKE ? AND n.code LIKE 'WCH15%' " + extra +
           " GROUP BY n.code ORDER BY count(*) DESC LIMIT 8")
    for code, cnt, ids in cur.execute(sql, (like,)):
        print(f'{code}: {cnt}  [{ids}]')
    print()
q('13C NMR', '%13C%')
q('carbon environments', '%carbon environment%')
q('number of peaks', '%number of peaks%')
q('NMR peaks', '%peaks on the%')
print('=== details of 13C examples ===')
for qid in (29902,29903,32179,32180,33423,33736,34136,31932):
    row = cur.execute("SELECT id, kind, substr(stem_text,1,150) FROM question WHERE id=?", (qid,)).fetchone()
    print(row)
