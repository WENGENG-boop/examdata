"""Apply out-of-batch taxonomy corrections (mirror of tmp_jev_full_apply change semantics).

Deletes ALL taxonomy rows of the question, inserts one reviewed ai-review row.
Usage:
  python tmp_psych_fix.py --subject ial-psychology --fix 62293=WPS01-2.1.2 --fix 62296=WPS01-1.1.3
  python tmp_psych_fix.py --subject ial-psychology --fix 62293=WPS01-2.1.2 --fix 62296=WPS01-1.1.3 --write
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from examdata.core import models as m
from examdata.tagging.assign import REVIEW_ASSIGNED_BY, REVIEW_SOURCE
from examdata.tagging.corpus import load_points, unit_code_from_paper

ROOT = Path(__file__).resolve().parent
DB_URL = f"sqlite:///{ROOT / '.data' / 'examdata.db'}"
LOG_PATH = ROOT / 'tmp_psych_fix_log.jsonl'

ap = argparse.ArgumentParser()
ap.add_argument('--subject', required=True)
ap.add_argument('--fix', action='append', default=[], metavar='QID=CODE')
ap.add_argument('--write', action='store_true')
args = ap.parse_args()

eng = create_engine(DB_URL)
s = Session(eng)

sub = s.execute(select(m.Subject).where(m.Subject.slug == args.subject)).scalar()
if sub is None:
    raise SystemExit(f'subject {args.subject} not found')
keys = {(sub.code or '').strip().lower(), (sub.slug or '').strip().lower()}
keys.discard('')
points = [p for p in load_points(s) if (p.subject or '').strip().lower() in keys]
by_code = {p.code: p for p in points}
by_unit = {}
for p in points:
    by_unit.setdefault(p.unit_code, set()).add(p.code)

log = []
for spec in args.fix:
    qid_s, _, code = spec.partition('=')
    qid = int(qid_s)
    code = code.strip()
    row = {'question_id': qid, 'code': code, 'subject': args.subject, 'mode': 'WRITE' if args.write else 'dry-run'}
    q = s.get(m.Question, qid)
    if q is None:
        row['status'] = 'error'; row['error'] = 'question not found'; log.append(row); print(row); continue
    paper = s.get(m.Paper, q.paper_id)
    doc = s.get(m.Document, paper.document_id) if paper else None
    point = by_code.get(code)
    if point is None:
        row['status'] = 'error'; row['error'] = f'code {code} not a point of {args.subject}'; log.append(row); print(row); continue
    fresh = unit_code_from_paper(paper.attrs, doc.paper_code) if paper and doc else None
    unit = fresh if fresh in by_unit else None
    if unit and point.unit_code and point.unit_code.upper() != unit.upper():
        row['status'] = 'error'; row['error'] = f'code unit {point.unit_code} != question unit {unit}'; log.append(row); print(row); continue
    old = list(s.scalars(select(m.QuestionTaxonomy).where(m.QuestionTaxonomy.question_id == qid)))
    row['old'] = [{'code': s.get(m.TaxonomyNode, r.node_id).code if s.get(m.TaxonomyNode, r.node_id) else None,
                   'source': r.source, 'assigned_by': r.assigned_by, 'confidence': r.confidence} for r in old]
    row['unit'] = unit
    if args.write:
        for r in old:
            s.delete(r)
        s.flush()
        s.add(m.QuestionTaxonomy(question_id=qid, node_id=point.node_id, source=REVIEW_SOURCE,
                                 confidence=1.0, assigned_by=REVIEW_ASSIGNED_BY, reviewed=True))
        row['status'] = 'applied'
    else:
        row['status'] = 'dry-run'
    log.append(row)
    print(row)

if args.write:
    s.flush()
    s.commit()
    with open(LOG_PATH, 'a', encoding='utf-8') as fh:
        for entry in log:
            fh.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + '\n')
    print(f'log appended -> {LOG_PATH}')
s.close()
