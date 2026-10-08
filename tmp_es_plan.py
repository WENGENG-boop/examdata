"""Plan helper for ial-spanish self-judgment: group batch qids by paper/question group.

Usage:
  python -X utf8 tmp_es_plan.py                # overview: papers, counts, anchors
  python -X utf8 tmp_es_plan.py 2124           # detail by paper_id (batch qids + anchors)
  python -X utf8 tmp_es_plan.py 2124 --stems   # also print parent stems (longer)
"""
import glob
import json
import re
import sqlite3
import sys
from collections import defaultdict

def load_batch():
    rows = {}
    for f in sorted(glob.glob('tmp_jev_untagged_batches/ial-spanish/batches/batch-*.jsonl')):
        for line in open(f, encoding='utf-8'):
            r = json.loads(line)
            rows[r['question_id']] = r
    return rows

def db():
    con = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
    con.row_factory = sqlite3.Row
    return con

def top_num(number_path):
    if not number_path:
        return '?'
    mm = re.match(r'^(\d+)', number_path)
    return mm.group(1) if mm else number_path

def main():
    batch = load_batch()
    con = db()
    cur = con.cursor()

    info = {}
    for qid in batch:
        q = cur.execute('SELECT id,paper_id,parent_id,number_label,number_path,kind,marks,stem_text FROM question WHERE id=?', (qid,)).fetchone()
        info[qid] = dict(q) if q else None
    papers = sorted({v['paper_id'] for v in info.values() if v})

    allq = {}
    for pid in papers:
        for r in cur.execute('SELECT id,paper_id,parent_id,number_label,number_path,kind,marks,stem_text FROM question WHERE paper_id=?', (pid,)):
            allq[r['id']] = dict(r)

    tags = defaultdict(list)
    ids = sorted(allq)
    for i in range(0, len(ids), 500):
        chunk = ids[i:i+500]
        ph = ','.join('?'*len(chunk))
        for r in cur.execute(f'''SELECT qt.question_id, tn.code, qt.source, qt.confidence, qt.assigned_by
                                 FROM question_taxonomy qt JOIN taxonomy_node tn ON tn.id=qt.node_id
                                 WHERE qt.question_id IN ({ph})''', chunk):
            tags[r['question_id']].append((r['code'], r['source'], r['confidence'], r['assigned_by']))

    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    flags = {a for a in sys.argv[1:] if a.startswith('--')}

    if not args:
        byp = defaultdict(list)
        for qid in batch:
            byp[info[qid]['paper_id']].append(qid)
        for pid in sorted(byp):
            bq = byp[pid]
            ntag = sum(1 for q in allq if allq[q]['paper_id'] == pid and q in tags)
            print(f'\n== paper_id={pid} batch={len(bq)} tagged_total={ntag}')
            byt = defaultdict(list)
            for qid in bq:
                byt[top_num(info[qid]['number_path'])].append(qid)
            for t in sorted(byt, key=lambda x: int(x) if x.isdigit() else 999):
                qids = sorted(byt[t])
                anch = []
                for q in sorted(allq):
                    if allq[q]['paper_id'] == pid and top_num(allq[q]['number_path']) == t and q in tags:
                        anch.append((q, allq[q]['number_path'], tags[q]))
                ancs = ' | '.join(f"{q}[{np}]=" + '+'.join(f'{c}' for c, s, cf, ab in tl) for q, np, tl in anch[:8])
                print(f'   Q{t}: {len(qids)} qids {sorted(qids)[:2]}... anchors: {ancs}')
    else:
        for a in args:
            pid = int(a)
            bq = [q for q in batch if info[q]['paper_id'] == pid]
            print(f'\n######## paper_id={pid} batch={len(bq)} ########')
            byt = defaultdict(list)
            for qid in bq:
                byt[top_num(info[qid]['number_path'])].append(qid)
            for t in sorted(byt, key=lambda x: int(x) if x.isdigit() else 999):
                qids = sorted(byt[t])
                print(f'\n---- Q{t} :: batch {len(qids)} qids')
                for q in sorted(allq):
                    if allq[q]['paper_id'] == pid and top_num(allq[q]['number_path']) == t and q in tags:
                        print(f'     ANCHOR {q}[{allq[q]["number_path"]}] = ' +
                              ', '.join(f'{c} ({s},{cf},{ab})' for c, s, cf, ab in tags[q]))
                for q in qids:
                    npth = info[q]['number_path']
                    stem = (batch[q].get('stem') or '').replace('\t', ' ').replace('\n', ' | ')
                    stem = re.sub(r'\s+', ' ', stem)
                    lim = 2000 if '--stems' in flags else 200
                    print(f'   {q}[{npth}] {stem[:lim]}')

if __name__ == '__main__':
    main()
