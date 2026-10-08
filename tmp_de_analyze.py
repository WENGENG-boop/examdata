import re, glob, sqlite3, os, json
from collections import defaultdict, Counter

root2qids = defaultdict(list)
for f in sorted(glob.glob('tmp_selfjudge/unt/ial-german/*.ans.txt.draft')):
    base = os.path.basename(f)
    unit = base[:5]
    for line in open(f, encoding='utf-8'):
        m = re.match(r'^# TODO (\d+) (NOLABEL|TIE\b.*?) root=(\d+)', line)
        if m:
            qid = int(m.group(1)); kind = m.group(2); rid = int(m.group(3))
            root2qids[rid].append((qid, kind, unit))

print('unique roots in TODO lines:', len(root2qids))

con = sqlite3.connect('.data/examdata.db'); cur = con.cursor()
ids = sorted(root2qids)
rows = cur.execute('SELECT question_id, node_id FROM question_taxonomy WHERE question_id IN (%s)' % ','.join('?' * len(ids)), ids).fetchall()
nid2code = {}
if rows:
    nids = list({r[1] for r in rows})
    nid2code = {r[0]: r[1] for r in cur.execute('SELECT id, code FROM taxonomy_node WHERE id IN (%s)' % ','.join('?' * len(nids)), nids)}
tagged = {qid: nid2code.get(nid) for qid, nid in rows}
print('roots WITH db tag:', tagged)
untagged = [i for i in ids if i not in tagged]
print('roots WITHOUT db tag:', len(untagged))

# split by unit
for unit in ('WGN01', 'WGN02', 'WGN04'):
    us = sorted(rid for rid in untagged if root2qids[rid][0][2] == unit)
    print(unit, 'untagged roots:', len(us))
    print(us)

# check TIE lines
ties = {rid: [(q, k) for q, k, u in v if k.startswith('TIE')] for rid, v in root2qids.items()}
ties = {r: v for r, v in ties.items() if v}
print('roots with TIE children:', ties)
