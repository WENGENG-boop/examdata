"""IAL review status: per subject, questions with rows but 0 reviewed (read-only)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from examdata.core import models as m

ROOT = Path(__file__).resolve().parent
eng = create_engine(f"sqlite:///{ROOT / '.data' / 'examdata.db'}")
s = Session(eng)

grand = {'questions': 0, 'unrev_only': 0, 'no_rows': 0, 'reviewed_q': 0}
for sub in s.scalars(select(m.Subject).order_by(m.Subject.id)):
    if sub.id < 5:
        continue
    qids = list(s.scalars(
        select(m.Question.id)
        .join(m.Paper, m.Paper.id == m.Question.paper_id)
        .join(m.Document, m.Document.id == m.Paper.document_id)
        .where(m.Document.subject_id == sub.id)))
    if not qids:
        continue
    rows = list(s.execute(
        select(m.QuestionTaxonomy.question_id, m.QuestionTaxonomy.reviewed)
        .where(m.QuestionTaxonomy.question_id.in_(qids))).all())
    rev: dict[int, list[bool]] = {}
    for qid, r in rows:
        rev.setdefault(qid, []).append(bool(r))
    unrev_only = sum(1 for q in qids if rev.get(q) and not any(rev[q]))
    no_rows = sum(1 for q in qids if not rev.get(q))
    reviewed_q = sum(1 for q in qids if rev.get(q) and any(rev[q]))
    grand['questions'] += len(qids)
    grand['unrev_only'] += unrev_only
    grand['no_rows'] += no_rows
    grand['reviewed_q'] += reviewed_q
    print(f'[{sub.slug}] questions={len(qids)} reviewed={reviewed_q} '
          f'unrev_only={unrev_only} no_rows={no_rows}')
print(f"TOTAL {grand}")
