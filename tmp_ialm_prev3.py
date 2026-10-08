import sqlite3, re
con = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
cur = con.cursor()
q = """select t.code, q.id, q.paper_id, substr(q.stem_text,1,110), qt.source, qt.confidence
    from question_taxonomy qt
    join taxonomy_node t on t.id=qt.node_id
    join question q on q.id=qt.question_id
    join paper p on p.id=q.paper_id
    join document d on d.id=p.document_id
    where d.subject_id=16 and t.code like 'WMA02-%'"""
rows = cur.execute(q).fetchall()

def search(name, pat):
    rx = re.compile(pat, re.I)
    print(f"\n##### {name} #####")
    for r in rows:
        if rx.search(r[3] or ''):
            print(f"{r[0]}\t{r[1]}\tp{r[2]}\t{r[4]}/{r[5]}\t{(r[3] or '').replace(chr(10),' ')[:100]}")

search("table", r"complete the table")
search("maximum/minimum value", r"(maximum|minimum) value")
search("time taken", r"time taken")
search("find the value of k", r"value of k\b")
search("state value of", r"state the value")
search("explain", r"explain")
