import sqlite3

con = sqlite3.connect('.data/examdata.db')
cur = con.cursor()
series = [53471, 53562, 53754, 53893, 54080, 54354, 54678, 54765]
for lo in series:
    print('=== series root', lo)
    rows = cur.execute(
        "select q.id, q.parent_id, q.number_label, coalesce(t.code,'-'), "
        "substr(replace(replace(q.stem_text, char(10), ' '), char(9), ' '),1,95) "
        "from question q left join question_taxonomy qt on qt.question_id = q.id "
        "left join taxonomy_node t on t.id = qt.node_id "
        "where q.id between ? and ? order by q.id", (lo, lo + 13)).fetchall()
    for r in rows:
        print(r[0], '|parent', r[1], '|', repr(r[2]), '|', r[3], '|', r[4])
    print()
con.close()
