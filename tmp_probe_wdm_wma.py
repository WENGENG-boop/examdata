"""Probe: WDM11/WMA11 title<->pcode swap docs; sibling taxonomy node distribution."""
from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from examdata.core import models as m
from examdata.tagging.corpus import unit_code_from_paper

ROOT = Path(__file__).resolve().parent
DB_URL = f"sqlite:///{ROOT / '.data' / 'examdata.db'}"

PAT = re.compile(r'Unit\s*1\s*\((W[DM]A11)\)', re.I)


def unit_of_code(code: str) -> str:
    return (code or '').split('-', 1)[0]


def main() -> None:
    eng = create_engine(DB_URL)
    s = Session(eng)

    rows = s.execute(
        select(
            m.Document.id, m.Document.title, m.Document.year, m.Document.paper_code,
            m.Subject.slug,
        )
        .join(m.Subject, m.Subject.id == m.Document.subject_id)
        .where(m.Subject.slug.in_(['ial-maths', 'ial18-mathematics']))
    ).all()

    hits = []
    for did, title, year, pcode, slug in rows:
        mm = PAT.search(title or '')
        if not mm:
            continue
        hits.append((did, title, year, pcode, slug, mm.group(1).upper()))

    print(f'docs matching Unit 1 (WDM11|WMA11): {len(hits)}')
    for did, title, year, pcode, slug, tag in sorted(hits, key=lambda r: (r[5], r[2] or 0)):
        # sibling taxonomy node codes in this doc
        qrows = s.execute(
            select(m.Question.id)
            .join(m.Paper, m.Paper.id == m.Question.paper_id)
            .where(m.Paper.document_id == did)
        ).scalars().all()
        nodes = s.execute(
            select(m.TaxonomyNode.code)
            .join(m.QuestionTaxonomy, m.QuestionTaxonomy.node_id == m.TaxonomyNode.id)
            .where(m.QuestionTaxonomy.question_id.in_(qrows))
        ).scalars().all() if qrows else []
        unitc = Counter(unit_of_code(c) for c in nodes)
        fresh = unit_code_from_paper(None, pcode)
        # fresh needs paper attrs; re-derive per paper below
        print(f'doc={did} slug={slug} year={year} pcode={pcode} title={title[:70]!r}')
        print(f'   title_tag={tag} fresh_from_pcode(None)={fresh} sibling_units={dict(unitc)} n_q={len(qrows)} n_tagged={len(nodes)}')
        # per-paper fresh
        prows = s.execute(
            select(m.Paper.id, m.Paper.attrs)
            .where(m.Paper.document_id == did)
        ).all()
        for pid, attrs in prows:
            f = unit_code_from_paper(attrs, pcode)
            print(f'   paper={pid} fresh={f}')

    # Also: what does the fresh unit resolve to for the reverse set?
    print('\n--- reverse: pcode wdm11/wma11 docs, titles ---')
    for did, title, year, pcode, slug in rows:
        if (pcode or '').lower() in ('wdm11-01', 'wma11-01'):
            print(f'doc={did} pcode={pcode} year={year} slug={slug} title={(title or "")[:70]!r}')


if __name__ == '__main__':
    main()
