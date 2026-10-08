import sqlite3
c = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
c.execute('PRAGMA temp_store=MEMORY')
# find parents of interest and list children with labels
parents = [52171, 52263, 52552, 52566, 52573, 52582, 52682, 52696, 52287]
for pid in parents:
    r = c.execute("select id, number_label, marks, parent_id from question where id=?", (pid,)).fetchone()
    print(f"=== parent candidate q={pid} num={r[1]} marks={r[2]} parent_id={r[3]} ===")
    kids = list(c.execute(
        "select id, number_label, marks from question where parent_id=? order by id", (pid,)))
    if not kids:
        # maybe pid is child; get its parent
        if r[3]:
            pr = c.execute("select id, number_label, marks from question where id=?", (r[3],)).fetchone()
            print(f"  (this is a CHILD; parent = {pr})")
    for kid, kl, km in kids:
        labs = list(c.execute("select tn.code from question_taxonomy qt join taxonomy_node tn on tn.id=qt.node_id where qt.question_id=? order by tn.code", (kid,)))
        print(f"  child {kid} #{kl} marks={km} labels={[l[0] for l in labs]}")
    labs = list(c.execute("select tn.code from question_taxonomy qt join taxonomy_node tn on tn.id=qt.node_id where qt.question_id=? order by tn.code", (pid,)))
    print(f"  SELF labels={[l[0] for l in labs]}")
