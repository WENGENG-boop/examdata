import sqlite3, sys
con = sqlite3.connect('.data/examdata.db')
con.row_factory = sqlite3.Row
cur = con.cursor()
for qid in sys.argv[1:]:
    r = cur.execute("""SELECT q.id, q.paper_id, q.parent_id, q.number_label, q.marks,
                       q.stem_text FROM question q WHERE q.id=?""", (qid,)).fetchone()
    if not r:
        print(f'Q {qid} NOT FOUND'); continue
    print(f"########## Q {r['id']} p{r['paper_id']} parent={r['parent_id']} #{r['number_label']} {r['marks']}mk")
    print(r['stem_text'][:2600])
    print()
