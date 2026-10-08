import sqlite3, json, glob, collections

con = sqlite3.connect('.data/examdata.db')
cur = con.cursor()
allr = []
for f in glob.glob('tmp_jev_untagged_batches/ial-spanish/batches/*.jsonl'):
    allr += [json.loads(l) for l in open(f, encoding='utf-8')]
qset = set(r['question_id'] for r in allr)
qids = sorted(qset)
cur.execute('select distinct paper_id from question where id in (%s)' % ','.join('?' * len(qids)), qids)
pids = sorted(r[0] for r in cur.fetchall())
byp = collections.defaultdict(list)
cur.execute('''select q.id, q.paper_id, q.number_path, q.marks, tn.code from question q
  left join question_taxonomy qt on qt.question_id=q.id
  left join taxonomy_node tn on tn.id=qt.node_id''')
for r in cur.fetchall():
    byp[r[1]].append(r)
for pid in pids:
    unt = collections.Counter(); tag = collections.Counter()
    for qid, p, np, mk, code in byp[pid]:
        if qid in qset: unt[np] += 1
        elif code: tag[np] += 1
    print(f'paper {pid}:')
    print('   untagged:', dict(sorted(unt.items())))
    print('   tagged  :', dict(sorted(tag.items())))
