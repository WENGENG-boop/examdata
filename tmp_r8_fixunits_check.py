"""read-only: dump current question_taxonomy rows for the 24 questions in scope."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'src'))
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from examdata.core import models as m

ROOT = Path(__file__).resolve().parent
DB_URL = f"sqlite:///{ROOT / '.data' / 'examdata.db'}"

QIDS = [
    68429, 68430, 68437, 68438, 68440, 68441, 68442, 68443, 68444, 68445,
    68446, 68448, 68449, 68450,
    68453, 68454, 68455, 68456, 68457, 68458,
    68517, 68520, 68525, 68531,
]


def main() -> None:
    eng = create_engine(DB_URL)
    s = Session(eng)
    stmt = (
        select(
            m.QuestionTaxonomy.id, m.QuestionTaxonomy.question_id,
            m.QuestionTaxonomy.node_id, m.QuestionTaxonomy.source,
            m.QuestionTaxonomy.assigned_by, m.QuestionTaxonomy.confidence,
            m.QuestionTaxonomy.reviewed, m.TaxonomyNode.code, m.TaxonomyNode.name,
            m.Question.number_label, m.Document.id.label('doc_id'),
        )
        .join(m.TaxonomyNode, m.TaxonomyNode.id == m.QuestionTaxonomy.node_id)
        .join(m.Question, m.Question.id == m.QuestionTaxonomy.question_id)
        .join(m.Paper, m.Paper.id == m.Question.paper_id)
        .join(m.Document, m.Document.id == m.Paper.document_id)
        .where(m.QuestionTaxonomy.question_id.in_(QIDS))
        .order_by(m.QuestionTaxonomy.question_id, m.QuestionTaxonomy.id)
    )
    n = 0
    for row in s.execute(stmt):
        n += 1
        print(
            f"row{row.id} q{row.question_id} doc{row.doc_id} [{row.number_label}] "
            f"{row.code} {row.name[:45]} src={row.source} by={row.assigned_by} "
            f"conf={row.confidence} rev={row.reviewed}"
        )
    print(f"total rows={n}")
    # also count per question
    from collections import Counter
    c = Counter(r.question_id for r in s.execute(stmt))
    print('per-question:', dict(sorted(c.items())))
    s.close()


if __name__ == '__main__':
    main()
