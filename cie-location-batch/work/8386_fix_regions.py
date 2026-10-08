"""8386/2026-Jun-11: fix 13 failed regions flagged by visual verification.

QP fix (5 regions): footer clipped at left edge -> extend x0 92.4 -> 70.4
(footer text starts at x=72.4; passing peer regions use x0=70.4/70.8).
  Q1 p3 [92.4,58.8,541.2,748.4], Q1(c) p3, Q1(c)(ii) p3, Q4 p9, Q4(e) p9.

MS fix (8 regions): spurious header-only bands [58.4, y0, 102.0, 729.2]
(visible top band of page shows only PUBLISHED + table column headers; the
questions' content is fully covered by their other, passing regions and does
not continue onto these pages - confirmed visually on MS p8, p11, p12, p13, p15).
Remove from: 1(b)/p8, 1(b)(iii)/p8, 2/p11, 2(b)/p11, 2(b)(ii)/p11, 3/p12,
4(c)/p13, 5(b)/p15.
"""
import hashlib
import json
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(BASE, 'indexes', '8386', '2026-Jun-11', 'cie-index.json')
BACKUP = os.path.join(BASE, 'work', 'index-backups',
                      '8386-2026-Jun-11-before-fix2.json')

QP_FIX = {  # (question, page): old bbox -> new x0
    ('1', 3): 70.4,
    ('1(c)', 3): 70.4,
    ('1(c)(ii)', 3): 70.4,
    ('4', 9): 70.4,
    ('4(e)', 9): 70.4,
}
MS_REMOVE = [
    ('1(b)', 8, [58.4, 63.6, 102.0, 729.2]),
    ('1(b)(iii)', 8, [58.4, 63.6, 102.0, 729.2]),
    ('2', 11, [58.4, 147.6, 102.0, 729.2]),
    ('2(b)', 11, [58.4, 147.6, 102.0, 729.2]),
    ('2(b)(ii)', 11, [58.4, 147.6, 102.0, 729.2]),
    ('3', 12, [58.4, 64.8, 102.0, 729.2]),
    ('4(c)', 13, [58.4, 76.0, 102.0, 729.2]),
    ('5(b)', 15, [58.4, 147.6, 102.0, 729.2]),
]


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

    qp_fixed = 0
    ms_removed = 0
    by_q = {q['question']: q for q in doc['questions']}

    for (qno, page), new_x0 in QP_FIX.items():
        q = by_q[qno]
        hits = 0
        for r in q.get('qp', []):
            b = r['bbox']
            if r['page'] == page and b[0] == 92.4 and b[2] == 541.2 and b[3] == 748.4:
                r['bbox'] = [new_x0, b[1], b[2], b[3]]
                qp_fixed += 1
                hits += 1
        if hits != 1:
            print(f'ERROR: QP fix expected 1 hit for {qno} p{page}, got {hits}')
            sys.exit(3)

    for qno, page, bbox in MS_REMOVE:
        q = by_q[qno]
        before = len(q.get('ms', []))
        q['ms'] = [r for r in q.get('ms', [])
                   if not (r['page'] == page and r['bbox'] == bbox)]
        removed = before - len(q['ms'])
        if removed != 1:
            print(f'ERROR: MS remove expected 1 hit for {qno} p{page}, got {removed}')
            sys.exit(3)
        ms_removed += removed

    tmp = INDEX + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
        f.write('\n')
    os.replace(tmp, INDEX)

    new_sha = sha256_file(INDEX)
    total = sum(len(q.get('qp', [])) + len(q.get('ms', [])) for q in doc['questions'])
    print('qp regions fixed:', qp_fixed)
    print('ms regions removed:', ms_removed)
    print('old sha:', old_sha)
    print('new sha:', new_sha)
    print('question count:', len(doc['questions']), 'total regions:', total)
    for qno in ('1', '1(c)', '1(c)(ii)', '4', '4(e)',
                '1(b)', '1(b)(iii)', '2', '2(b)', '2(b)(ii)', '3', '4(c)', '5(b)'):
        q = by_q[qno]
        print(qno, 'qp:', [(r['page'], r['bbox']) for r in q.get('qp', [])],
              'ms:', [(r['page'], r['bbox']) for r in q.get('ms', [])])


if __name__ == '__main__':
    main()
