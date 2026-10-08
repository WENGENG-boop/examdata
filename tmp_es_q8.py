import sqlite3, sys

con = sqlite3.connect('.data/examdata.db')
cur = con.cursor()
pids = [int(a) for a in sys.argv[1:]]
for pid in pids:
    cur.execute("select d.title from paper p join document d on d.id=p.document_id where p.id=?", (pid,))
    print(f"===== paper {pid}: {cur.fetchone()[0]}")
    cur.execute("""select q.id, q.number_path, q.marks, tn.code, qt.source, q.stem_text
                   from question q
                   left join question_taxonomy qt on qt.question_id=q.id
                   left join taxonomy_node tn on tn.id=qt.node_id
                   where q.paper_id=? and (q.number_path like '8%' or q.number_path like '9%')
                   order by q.display_order, q.id""", (pid,))
    for qid, np, mk, code, src, stem in cur.fetchall():
        s = ' '.join((stem or '').split())
        print(f"  {qid} [{np}] {mk}mk {code or '-'}({src or '-'}) :: {s[:220]}")
