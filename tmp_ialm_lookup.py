import json, sqlite3, sys

qids = [56934,56941,56943,56944,56953,56964,56965,57764,57768,57777,57795,57796,57801,57802,58336,58337,58339,58357,58370,58572,58578,58579,58583,58590,58592,58885,58922,58937,58941,58942,58943,58953,
        59375,59379,59381,59384,59393,59394,59396,59399,59404,59407,59409,59410,59834,59845,59849,59857,60363,60379,60394,60399,60685,60689,60716,60725,60727,60897,60898,60899,60907,60921,60925,60982,60986,60990,60991,60993,61027]
qs = set(qids)
print("total qids:", len(qids), "unique:", len(qs))

# 1) r2 batches
r2 = {}
import glob
for f in glob.glob('tmp_jev_full_batches_r2/ial-maths/batches/*.jsonl'):
    for line in open(f, encoding='utf-8'):
        try: d = json.loads(line)
        except: continue
        if d.get('question_id') in qs:
            r2[d['question_id']] = d
print("=== r2 entries found:", len(r2))
for q in qids:
    if q in r2:
        d = r2[q]
        cur = d.get('current') or []
        curcodes = [c.get('code') if isinstance(c,dict) else c for c in cur]
        print(f"R2 {q} {d.get('number_label')} {curcodes}  unit={d.get('unit_code')}")

# 2) untagged batches membership
mem = {}
for f in glob.glob('tmp_jev_untagged_batches/ial-maths/batches/*.jsonl'):
    for line in open(f, encoding='utf-8'):
        try: d = json.loads(line)
        except: continue
        if d.get('question_id') in qs:
            mem[d['question_id']] = (f.split('batch-')[-1], d.get('unit_code'), d.get('number_label'))
print("=== untagged membership:", len(mem), "missing:", sorted(qs - set(mem)))
