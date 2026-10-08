import sqlite3
con = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
cur = con.cursor()
rows = cur.execute("""select t.code, q.id, q.paper_id, q.number_label, substr(q.stem_text,1,90)
    from question_taxonomy qt
    join taxonomy_node t on t.id=qt.node_id
    join question q on q.id=qt.question_id
    where t.code like 'WMA02-%'
    order by t.code, q.paper_id, q.id""").fetchall()
print('total WMA02 labeled:', len(rows))
import collections
cnt = collections.Counter(r[0] for r in rows)
print(cnt)
with open('tmp_ialm_prev.txt','w',encoding='utf-8') as f:
    for r in rows:
        f.write(f"{r[0]}\t{r[1]}\tp{r[2]}\t{r[3]}\t{(r[4] or '').replace(chr(10),' ')}\n")
print('written tmp_ialm_prev.txt')
