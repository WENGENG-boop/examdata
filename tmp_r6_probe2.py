"""r6 focused probe: ambiguous docs — real current tags + stems (no cross join).

Docs: 1754(acct WAC01), 1911(englang WEN03), 2441/2458/2467/2481/2483(greek),
      3190/3214/3239/3254/3258/3265/3298/3299/3305/3310(maths),
      471/774/802/820/951/1120/1336(maths18)
"""
from __future__ import annotations

import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from examdata.core import models as m
from examdata.tagging.corpus import unit_code_from_paper

ROOT = Path(__file__).resolve().parent
DB_URL = f'sqlite:///{ROOT / ".data" / "examdata.db"}'

DOCS = [1754, 1911, 2441, 2458, 2467, 2481, 2483,
        3190, 3214, 3239, 3254, 3258, 3265, 3298, 3299, 3305, 3310,
        471, 774, 802, 820, 951, 1120, 1336]


def main() -> None:
    eng = create_engine(DB_URL)
    s = Session(eng)

    reviewed = set(s.scalars(select(m.QuestionTaxonomy.question_id).distinct().where(
        m.QuestionTaxonomy.reviewed == 1)))

    for did in DOCS:
        doc = s.get(m.Document, did)
        if doc is None:
            print(f'doc {did} NOT FOUND'); continue
        paper = s.scalar(select(m.Paper).where(m.Paper.document_id == did).order_by(m.Paper.id).limit(1))
        pid = paper.id if paper else None
        pattrs = paper.attrs if paper else None
        fresh = unit_code_from_paper(pattrs, doc.paper_code)
        qs = s.execute(
            select(m.Question.id, m.Question.number_label, m.Question.stem_text, m.Question.marks)
            .where(m.Question.paper_id == pid).order_by(m.Question.display_order, m.Question.id)
        ).all() if pid else []
        unrev = [q for q in qs if q[0] not in reviewed]
        # tag distribution (correct join)
        tagc = Counter()
        per_q = {}
        for qid, *_ in qs:
            rows = s.execute(
                select(m.TaxonomyNode.code)
                .join(m.QuestionTaxonomy, m.QuestionTaxonomy.node_id == m.TaxonomyNode.id)
                .where(m.QuestionTaxonomy.question_id == qid)
            ).all()
            codes = [r[0] for r in rows]
            per_q[qid] = codes
            for c in codes:
                tagc[c] += 1
        tagc_simple = Counter()
        for c, n in tagc.items():
            tagc_simple['-'.join(c.split('-')[:2]) if '-' in c else c] += n
        print(f'== doc {did} paper {pid} | pcode={doc.paper_code} | fresh={fresh!r} | '
              f'qs={len(qs)} unrev={len(unrev)}')
        print(f'   title: {(doc.title or "")[:100]}')
        print(f'   tags(top20): {tagc_simple.most_common(20)}')
        for qid, num, stem, mk in unrev[:6]:
            print(f'   [{qid}] {num!r} {mk}mk cur={per_q.get(qid)} | {(stem or "")[:130]}')
        print()


if __name__ == '__main__':
    main()
