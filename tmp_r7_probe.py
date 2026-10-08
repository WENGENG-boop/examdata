"""r7 probe: authoritative unit for affected docs + full row listings (read-only)."""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from examdata.core import models as m
from examdata.tagging.corpus import load_points

ROOT = Path(__file__).resolve().parent
DB_URL = f"sqlite:///{ROOT / '.data' / 'examdata.db'}"

AFFECTED = {
    'ial-accounting': [1728, 1737, 1752, 1753],
    'ial-geography': [2342],
    'ial-german': [2378],
    'ial-maths': [3250, 3255, 3256, 3257, 3263, 3268, 3270, 3271, 3273, 3274,
                  3290, 3291, 3294, 3297, 3318, 3319],
}


def main() -> None:
    eng = create_engine(DB_URL)
    s = Session(eng)

    points = load_points(s)
    point_by_node = {p.node_id: p for p in points}
    # unit -> list of points
    by_unit: dict[str, list] = defaultdict(list)
    for p in points:
        if p.unit_code:
            by_unit[p.unit_code.upper()].append(p)

    print('=== all units (global) ===')
    for u in sorted(by_unit):
        print(f'  {u}: {len(by_unit[u])} points')

    subjects = {sub.id: sub for sub in s.scalars(select(m.Subject))}
    slug_by_id = {sub.id: sub.slug for sub in subjects.values()}

    # --- law: dump all docs + revisions ---
    print()
    print('=== law docs ===')
    law = next(sub for sub in subjects.values() if sub.slug == 'ial-law')
    docs = list(s.scalars(select(m.Document).where(m.Document.subject_id == law.id)))
    for d in sorted(docs, key=lambda x: x.id):
        revs = list(s.scalars(select(m.DocumentRevision).where(m.DocumentRevision.document_id == d.id)))
        urls = [r.source_url for r in revs if r.source_url]
        papers = list(s.scalars(select(m.Paper).where(m.Paper.document_id == d.id)))
        qs = [q for p in papers for q in s.scalars(select(m.Question).where(m.Question.paper_id == p.id))]
        qids = [q.id for q in qs]
        rows = list(s.scalars(select(m.QuestionTaxonomy).where(m.QuestionTaxonomy.question_id.in_(qids)))) if qids else []
        units = Counter()
        for r in rows:
            p = point_by_node.get(r.node_id)
            units[(p.unit_code or '?').upper() if p else '?'] += 1
        urlfile = ''
        if urls:
            urlfile = urls[0].rsplit('/', 1)[-1]
        print(f'  doc{d.id} {d.title!r} pc={d.paper_code} attrs={json.dumps(d.attrs, ensure_ascii=False)[:200]} '
              f'q={len(qs)} rows={len(rows)} units={dict(units)} url={urlfile}')

    # --- affected non-law docs: full row units ---
    for slug, doc_ids in AFFECTED.items():
        sub = next(sub for sub in subjects.values() if sub.slug == slug)
        print()
        print(f'=== {slug} affected docs ===')
        for did in doc_ids:
            d = s.get(m.Document, did)
            if d is None or d.subject_id != sub.id:
                print(f'  doc{did} MISSING/mismatch subject')
                continue
            papers = list(s.scalars(select(m.Paper).where(m.Paper.document_id == d.id)))
            qs = [q for p in papers for q in s.scalars(select(m.Question).where(m.Question.paper_id == p.id))]
            qids = [q.id for q in qs]
            rows = list(s.scalars(select(m.QuestionTaxonomy).where(m.QuestionTaxonomy.question_id.in_(qids)))) if qids else []
            units = Counter()
            byq = Counter()
            for r in rows:
                p = point_by_node.get(r.node_id)
                units[(p.unit_code or '?').upper() if p else '?'] += 1
                byq[r.question_id] += 1
            multi = sum(1 for v in byq.values() if v > 1)
            print(f'  doc{d.id} {d.title!r} pc={d.paper_code} attrs={json.dumps(d.attrs, ensure_ascii=False)[:160]} '
                  f'q={len(qs)} rows={len(rows)} multirow_q={multi} units={dict(units)}')
            print(f'    paper attrs: ' + json.dumps([p.attrs for p in papers], ensure_ascii=False)[:400])

    # --- doc3114 (law 2016 P2 no URL) ---
    print()
    print('=== law doc3114 detail ===')
    d = s.get(m.Document, 3114)
    print(' title', d.title, 'pc', d.paper_code, 'spec', getattr(d, 'spec', None))
    revs = list(s.scalars(select(m.DocumentRevision).where(m.DocumentRevision.document_id == d.id)))
    for r in revs:
        print('  rev', r.id, 'url', r.source_url)
    papers = list(s.scalars(select(m.Paper).where(m.Paper.document_id == d.id)))
    for p in papers:
        print('  paper', p.id, p.attrs)
        qs = list(s.scalars(select(m.Question).where(m.Question.paper_id == p.id)))
        for q in qs:
            rows = list(s.scalars(select(m.QuestionTaxonomy).where(m.QuestionTaxonomy.question_id == q.id)))
            labs = []
            for r in rows:
                pt = point_by_node.get(r.node_id)
                labs.append(f'{pt.code}({pt.unit_code})' if pt else '?')
            print(f'    q{q.id} {q.number_label}: {labs}')


if __name__ == '__main__':
    main()
