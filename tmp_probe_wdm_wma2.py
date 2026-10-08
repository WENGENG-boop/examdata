"""Probe 2: siblings for docs titled (WDM11) but pcode=wma11-01, plus Unit C1 doc 841."""
from __future__ import annotations
import sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from examdata.core import models as m

ROOT = Path(__file__).resolve().parent
DB_URL = f"sqlite:///{ROOT / '.data' / 'examdata.db'}"

def unit_of_code(code: str) -> str:
    return (code or '').split('-', 1)[0]

def main() -> None:
    eng = create_engine(DB_URL)
    s = Session(eng)
    for did in [992, 708, 1322, 841, 1154, 1523, 1355, 1380, 1405, 1454, 1476, 1516]:
        doc = s.get(m.Document, did)
        if doc is None:
            print(f'doc={did} MISSING'); continue
        qrows = s.execute(
            select(m.Question.id, m.Question.number_label)
            .join(m.Paper, m.Paper.id == m.Question.paper_id)
            .where(m.Paper.document_id == did)
        ).all()
        qids = [q[0] for q in qrows]
        if qids:
            nodes = s.execute(
                select(m.TaxonomyNode.code)
                .join(m.QuestionTaxonomy, m.QuestionTaxonomy.node_id == m.TaxonomyNode.id)
                .where(m.QuestionTaxonomy.question_id.in_(qids))
            ).scalars().all()
        else:
            nodes = []
        unitc = Counter(unit_of_code(c) for c in nodes)
        print(f'doc={did} y={doc.year} dtype={doc.doc_type} pcode={doc.paper_code} title={(doc.title or "")[:65]!r}')
        print(f'   n_q={len(qids)} n_tagged={len(nodes)} sibling_units={dict(unitc)} sample={sorted(set(nodes))[:8]}')

if __name__ == '__main__':
    main()
