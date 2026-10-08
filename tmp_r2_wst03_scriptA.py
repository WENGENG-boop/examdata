import json, re
pack = open('tmp_selfjudge/r2/ial18-mathematics/WST03-p01.txt', encoding='utf-8').read()
qids = {int(m.group(2)) for m in re.finditer(r'^\[(\d+)\] (\d+)', pack, re.M)}
rows = []
for l in open('tmp_r2_math_scratch/all.jsonl', encoding='utf-8'):
    r = json.loads(l)
    if r.get('qid') in qids:
        m = re.search(r'置信度 ([\d.]+)', r.get('reason') or '')
        rows.append((r['qid'], r.get('number'), r.get('old'), r.get('cur'), float(m.group(1)) if m else None))
print('rows', len(rows))
for q, n, o, c, cf in sorted(rows, key=lambda x: (x[4] is None, x[4])):
    print(q, n, 'old=', repr(o), 'cur=', c, 'conf=', cf)
