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
           " GROUP BY n.code ORDER BY count(*) DESC LIMIT 7")
    try:
        for code, cnt, ids in cur.execute(sql, (like,)):
            print(f'{code}: {cnt}  [{ids}]')
    except Exception as e:
        print('ERR', e)
    print()

q('isomer', '%isomer%')
q('chiral/optical', '%optical isomer%')
q('condensation polymer', '%condensation polymer%')
q('catalys (WCH15-17.26)', '%catalys%', " AND n.code LIKE 'WCH15-17.2%'")
q('free chloride', '%free chloride%')
q('chloride ion', '%chloride ion%')
q('HPLC/chromatograph', '%chromatograph%')
q('plot', '%plot%')

print('===== stems of 31922 32903 31694 29621 31262 32536 29938 =====')
for qid in (31922, 32903, 31694, 29621, 31262, 32536, 29938):
    row = cur.execute("SELECT id, kind, substr(stem_text,1,200) FROM question WHERE id=?", (qid,)).fetchone()
    print(row)
