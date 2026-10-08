"""Unit-resolution validity check for the pending self-judgment sets (read-only)."""
import json
import glob
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from examdata.core import models as m
from examdata.tagging.corpus import load_points, unit_code_from_paper

ROOT = Path(__file__).resolve().parent
eng = create_engine(f"sqlite:///{ROOT / '.data' / 'examdata.db'}")
s = Session(eng)

R2 = ['ial18-chemistry', 'ial18-economics', 'ial18-it', 'ial18-mathematics',
      'ial18-mathematics-extra', 'ial18-physics']
UNT = ['ial-accounting', 'ial-french', 'ial-geography', 'ial-german', 'ial-law',
       'ial-maths', 'ial-psychology', 'ial-spanish', 'ial18-biology',
       'ial18-business', 'ial18-chemistry', 'ial18-economics', 'ial18-it',
       'ial18-mathematics', 'ial18-mathematics-extra', 'ial18-physics']


def check(tag, slug, batch_root):
    points_slug = 'ial18-mathematics' if slug == 'ial18-mathematics-extra' else slug
    sub_row = s.execute(select(m.Subject).where(m.Subject.slug == points_slug)).scalar()
    keys = {(sub_row.code or '').strip().lower(), (sub_row.slug or '').strip().lower()}
    keys.discard('')
    points = [p for p in load_points(s) if (p.subject or '').strip().lower() in keys]
    by_unit = {}
    for p in points:
        by_unit.setdefault(p.unit_code, []).append(p)
    bad = 0
    n = 0
    fresh_diff = 0
    badq = []
    for f in glob.glob(f'{batch_root}/{slug}/batches/batch-*.jsonl'):
        for line in open(f, encoding='utf-8'):
            r = json.loads(line)
            n += 1
            qid = r['question_id']
            unit = r.get('unit_code')
            q = s.get(m.Question, qid)
            if q is None:
                bad += 1
                badq.append((qid, 'missing'))
                continue
            paper = s.get(m.Paper, q.paper_id)
            doc = s.get(m.Document, paper.document_id) if paper else None
            fresh = unit_code_from_paper(paper.attrs if paper else None,
                                         doc.paper_code if doc else None)
            if fresh and fresh in by_unit:
                if fresh != unit:
                    fresh_diff += 1
                unit = fresh
            elif unit not in by_unit:
                bad += 1
                badq.append((qid, f'unit {unit!r} fresh {fresh!r}'))
    print(f'{tag} {slug}: n={n} invalid_unit={bad} fresh_diff={fresh_diff}')
    for x in badq[:6]:
        print('    ', x)


print('=== round2 sets ===')
for slug in R2:
    check('r2', slug, 'tmp_jev_full_batches_r2')
print()
print('=== untagged sets ===')
for slug in UNT:
    check('unt', slug, 'tmp_jev_untagged_batches')
