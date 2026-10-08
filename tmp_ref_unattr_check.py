# check unattributed MS-ref candidates vs current labels
import sqlite3
c = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
c.execute('PRAGMA temp_store=MEMORY')

cands = [
    (52165, '1.3.3.1'), (52165, '1.3.3.1'),
    (52171, '1.3.5.2'), (52171, '1.4.1.3'),
    (52172, '1.4.1.3'),
    (52184, '1.4.4.3'),
    (52263, '1.3.2.3'),
    (52270, '1.3.5.2'), (52270, '1.3.5.2'),
    (52552, '1.3.3.2'), (52552, '1.3.3.1'),
    (52559, '1.3.5.3'), (52559, '1.3.5.3'), (52559, '1.3.5.2'),
    (52564, '1.3.5.2'),
    (52566, '1.4.3.1'), (52566, '1.4.3.1'),
    (52573, '1.4.4.3'),
    (52578, '1.4.5.2'),
    (52582, '1.4.2.2'),
    (52583, '1.4.2.2'),
    (52675, '1.3.5.1'), (52675, '1.3.5.2'),
    (52680, '1.3.5.2'),
    (52682, '1.4.2.2'),
    (52687, '1.4.3.1'),
    (52688, '1.4.3.3'),
    (52689, '1.4.4.1'), (52689, '1.4.4.1'), (52689, '1.4.4.1'),
    (52694, '1.4.4.2'),
    (52695, '1.4.4.3'),
    (52696, '1.3.4.2'),
    (52697, '1.3.4.2'),
    (52699, '1.4.1.1'),
    (52700, '1.4.1.1'),
]

seen = {}
for qid, ref in cands:
    node = '.'.join(ref.split('.')[:3])
    if qid not in seen:
        rows = list(c.execute(
            "select tn.code, tn.name from question_taxonomy qt join taxonomy_node tn on tn.id=qt.node_id "
            "where qt.question_id=? order by tn.code", (qid,)))
        num = c.execute("select number_label from question where id=?", (qid,)).fetchone()
        seen[qid] = (rows, num[0] if num else '?')
    rows, num = seen[qid]
    labnodes = [r[0].split('-')[-1] for r in rows]
    flag = 'OK ' if node in labnodes else 'MISMATCH'
    print(f"{flag} q={qid} #{num} ref=({ref})->{node} labels={[r[0] for r in rows]}")
