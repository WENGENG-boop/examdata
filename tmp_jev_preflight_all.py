"""Preflight all remaining subjects: load spec points, units, batch units, problems."""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, r'C:/Users/weo/Desktop/api/examdata')
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from examdata.core import models as m
from examdata.tagging.corpus import load_points

DB = 'sqlite:///C:/Users/weo/Desktop/api/examdata/.data/examdata.db'
ROOT = Path('C:/Users/weo/Desktop/api/examdata')

SLUGS = ['ial-spanish', 'ial18-biology', 'ial18-chemistry', 'ial18-economics',
         'ial18-mathematics', 'ial18-physics', 'ial18-it', 'ial-accounting',
         'ial-german', 'ial-maths']

# batches to process per subject (from reconciliation); None = all batches in dir
ONLY = {
    'ial-spanish': ['003'],
    'ial18-biology': ['003', '004', '005', '006', '007', '008', '009', '010', '011', '012', '013'],
    'ial18-chemistry': None,
    'ial18-economics': None,
    'ial18-mathematics': [f'{i:03d}' for i in range(2, 63) if i != 38],
    'ial18-physics': None,
    'ial18-it': None,
    'ial-accounting': ['021', '028'],
    'ial-german': ['009'],
    'ial-maths': ['025'],
}

eng = create_engine(DB)
s = Session(eng)
all_points = load_points(s)

for slug in SLUGS:
    sub_row = s.execute(select(m.Subject).where(m.Subject.slug == slug)).scalar()
    if not sub_row:
        print(f'{slug}: NO SUBJECT ROW')
        continue
    keys = {(sub_row.code or '').strip().lower(), (sub_row.slug or '').strip().lower()}
    keys.discard('')
    points = [p for p in all_points if (p.subject or '').strip().lower() in keys]
    by_unit = {}
    for p in points:
        by_unit.setdefault(p.unit_code, []).append(p)
    print(f'{slug}: code={sub_row.code!r} title={(sub_row.title or "")[:40]!r} '
          f'points={len(points)}')
    print('   units:', {k: len(v) for k, v in sorted(by_unit.items())})

    # batch rows unit distribution
    bdir = ROOT / '.data/tagging/review-export' / slug / 'batches'
    only = ONLY.get(slug)
    files = sorted(bdir.glob('batch-*.jsonl'))
    if only is not None:
        files = [f for f in files if f.stem.split('-')[1] in set(only)]
    uc = Counter()
    nrows = 0
    problems = []
    for f in files:
        for line in open(f, encoding='utf-8'):
            rec = json.loads(line)
            nrows += 1
            u = rec.get('unit_code')
            uc[u] += 1
            if u not in by_unit:
                problems.append((f.name, rec.get('question_id'), f'unit {u!r} not in points'))
    print(f'   batches={len(files)} rows={nrows} units_in_batches={dict(uc)}')
    for pr in problems[:10]:
        print('   PROBLEM', pr)
    # sample codes per unit (first 3)
    for u in sorted(by_unit)[:2]:
        sample = [p.code for p in by_unit[u][:4]]
        print(f'    {u} sample codes: {sample}')
    print()
