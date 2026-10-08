# -*- coding: utf-8 -*-
"""Compare r2 vs r3 batch roots per subject: row counts + set diff of question_ids."""
import glob
import json
import os

R2 = 'tmp_jev_full_batches_r2'
R3 = 'tmp_jev_full_batches_r3'


def load(root, slug):
    out = {}
    for f in glob.glob(f'{root}/{slug}/batches/batch-*.jsonl'):
        for line in open(f, encoding='utf-8'):
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            out[rec['question_id']] = rec
    return out


subjects = sorted(d for d in os.listdir(R3) if os.path.isdir(os.path.join(R3, d)))
for slug in subjects:
    r2 = load(R2, slug) if os.path.isdir(f'{R2}/{slug}') else {}
    r3 = load(R3, slug)
    added = set(r3) - set(r2)
    removed = set(r2) - set(r3)
    print(f'{slug}: r2={len(r2)} r3={len(r3)} added={len(added)} removed={len(removed)}')
    if added:
        # summarize added by unit
        units = {}
        for q in added:
            units[r3[q].get('unit_code')] = units.get(r3[q].get('unit_code'), 0) + 1
        print('   added by unit:', units)
