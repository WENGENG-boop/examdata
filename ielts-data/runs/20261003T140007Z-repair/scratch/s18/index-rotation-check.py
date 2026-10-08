# -*- coding: utf-8 -*-
import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
R = 'ielts-data/runs/20261003T140007Z-repair'
P = 'tmp_audit_ielts/completeness_20261003'

def pteq(path):
    d = json.load(open(path, encoding='utf-8'))
    return {q['number']: q.get('answer') for q in (d.get('questions') or [])}

def ent(path):
    d = json.load(open(path, encoding='utf-8'))
    return {e['number']: e.get('value') for e in d['entries']}

def norm(v):
    return str(v).strip().lower() if v is not None else None

for n in (1, 2, 3, 4):
    for skill, idx_key, pte_key in (('listening','listening_shared','listening'), ('reading','reading_academic','reading')):
        idx = ent(f'{R}/scratch/s18/answers/book_11/test_{n}_{idx_key}.json')
        pte = pteq(f'{P}/pte-11-{n}-{pte_key}.json')
        same = 0; both = 0; mism = []
        for q in range(1, 41):
            a, b = norm(idx.get(q)), norm(pte.get(q))
            if a is not None and b is not None:
                both += 1
                if a == b: same += 1
                else: mism.append((q, idx.get(q), pte.get(q)))
        print(f'INDEX t{n} {skill}: both_present={both} exact_same={same} mismatches={len(mism)}')
        for m in mism[:8]:
            print('   ', m)
