"""9715/2023-Nov-21: remove generic-page MS regions (p2-5 full-page) from parent Q1-Q5.

Evidence (window 61/62): MS p2-5 are generic marking-principle pages
(p2 "Generic Marking Principles 1-4", p3 "GENERIC MARKING PRINCIPLE 5",
p4 "Annotations", p5 general marking principles table) with no question numbers.
They were attached as full-page [0,0,612,792] regions to parents 1-5 (20 regions).
Decision: delete only these 20 regions; keep all content-page strips unchanged.
"""
import hashlib
import json
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(BASE, 'indexes', '9715', '2023-Nov-21', 'cie-index.json')
BACKUP = os.path.join(BASE, 'work', 'index-backups',
                      '9715-2023-Nov-21-before-remove-generic.json')
GENERIC_BBOX = [0.0, 0.0, 612.0, 792.0]
GENERIC_PAGES = {2, 3, 4, 5}
TARGET_PARENTS = {'1', '2', '3', '4', '5'}


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    old_sha = sha256_file(INDEX)
    with open(INDEX, encoding='utf-8') as f:
        doc = json.load(f)

    if os.path.exists(BACKUP):
        print('BACKUP ALREADY EXISTS, refusing to overwrite:', BACKUP)
        sys.exit(2)
    os.makedirs(os.path.dirname(BACKUP), exist_ok=True)
    with open(BACKUP, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
        f.write('\n')

    removed = 0
    for q in doc['questions']:
        if q.get('parent') is not None:
            continue
        if q.get('question') not in TARGET_PARENTS:
            continue
        kept = []
        for r in q.get('ms', []):
            if r.get('page') in GENERIC_PAGES and r.get('bbox') == GENERIC_BBOX:
                removed += 1
            else:
                kept.append(r)
        q['ms'] = kept

    tmp = INDEX + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
        f.write('\n')
    os.replace(tmp, INDEX)

    new_sha = sha256_file(INDEX)
    print('removed regions:', removed)
    print('old sha:', old_sha)
    print('new sha:', new_sha)
    print('question count:', len(doc['questions']))
    for q in doc['questions']:
        if q.get('parent') is None:
            print('parent', q['question'], 'ms pages:',
                  [(r['page'], r['bbox']) for r in q.get('ms', [])])


if __name__ == '__main__':
    main()
