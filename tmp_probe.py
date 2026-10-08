"""Probe utility: question details / spec point details (read-only).

Usage:
  python tmp_probe.py --q 56402 56645 --sib
  python tmp_probe.py --p YLA1-01-1.2.22 YLA1-02-2.3.5
"""
import argparse
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

ap = argparse.ArgumentParser()
ap.add_argument('--q', type=int, nargs='*', default=[])
ap.add_argument('--p', nargs='*', default=[])
ap.add_argument('--sib', action='store_true')
args = ap.parse_args()

pts = load_points(s)
by_code = {p.code: p for p in pts}
node2code = {p.node_id: p.code for p in pts}


def show_cols(obj, prefix, limit=100):
    if obj is None:
        print(f'{prefix} None')
        return
    parts = []
    for c in obj.__table__.columns:
        v = getattr(obj, c.name)
        r = repr(v)
        if len(r) > limit:
            r = r[:limit] + '...'
        parts.append(f'{c.name}={r}')
    print(f'{prefix} ' + ' '.join(parts))


for code in args.p:
    p = by_code.get(code)
    if p is None:
        print(f'POINT {code} NOT FOUND')
    else:
        print(f'POINT {p.code} unit={p.unit_code} name={p.name!r}')

for qid in args.q:
    q = s.get(m.Question, qid)
    if q is None:
        print(f'Q {qid} NOT FOUND')
        continue
    paper = s.get(m.Paper, q.paper_id)
    doc = s.get(m.Document, paper.document_id) if paper else None
    fresh = unit_code_from_paper(paper.attrs if paper else None,
                                 doc.paper_code if doc else None)
    labels = s.execute(select(m.QuestionTaxonomy).where(
        m.QuestionTaxonomy.question_id == qid)).scalars().all()
    print(f'Q {qid} paper={doc.paper_code if doc else "?"} '
          f'number={getattr(q, "number_label", None)!r} marks={q.marks} '
          f'order={q.display_order} parent={q.parent_id} unit={fresh}')
    stem = getattr(q, 'stem_text', '') or ''
    print(f'   stem={stem[:600]!r}')
    for l in labels:
        print(f'   label {node2code.get(l.node_id, l.node_id)} by={l.assigned_by} '
              f'src={l.source} reviewed={l.reviewed} conf={l.confidence}')
    show_cols(paper, '   PAPER')
    show_cols(doc, '   DOC')
    if args.sib and paper:
        sibs = s.execute(select(m.Question).where(
            m.Question.paper_id == q.paper_id).order_by(
            m.Question.display_order)).scalars().all()
        print(f'   -- {len(sibs)} questions on paper {doc.paper_code if doc else "?"} --')
        for sb in sibs[:45]:
            st = (getattr(sb, 'stem_text', '') or '').replace('\n', ' ')
            print(f'   sib {sb.id} #{getattr(sb, "number_label", None)} {sb.marks}mk '
                  f'{st[:90]!r}')
