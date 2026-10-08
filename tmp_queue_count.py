"""Count unreviewed taxonomy rows per subject (the remaining review queue)."""
import json
from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from examdata.core import models as m

DB = Path(__file__).resolve().parent / ".data" / "examdata.db"
eng = create_engine(f"sqlite:///{DB}")
with Session(eng) as s:
    base = (
        select(m.Subject.slug,
               func.count(m.QuestionTaxonomy.id),
               func.count(func.distinct(m.QuestionTaxonomy.question_id)))
        .select_from(m.QuestionTaxonomy)
        .join(m.Question, m.QuestionTaxonomy.question_id == m.Question.id)
        .join(m.Paper, m.Question.paper_id == m.Paper.id)
        .join(m.Document, m.Paper.document_id == m.Document.id)
        .join(m.Subject, m.Document.subject_id == m.Subject.id)
        .where(m.QuestionTaxonomy.reviewed == False)  # noqa: E712
        .group_by(m.Subject.slug)
        .order_by(m.Subject.slug)
    )
    tot_rows = tot_q = 0
    print("slug                          unreviewed_rows  questions")
    for slug, n, nq in s.execute(base):
        tot_rows += n
        tot_q += nq
        print(f"{slug:<30}{n:>8}  {nq:>8}")
    print(f"{'TOTAL':<30}{tot_rows:>8}  {tot_q:>8}")

    # also: breakdown of unreviewed rows by confidence bucket
    print("\nconfidence buckets of unreviewed rows:")
    rows = s.execute(
        select(m.QuestionTaxonomy.confidence, m.QuestionTaxonomy.assigned_by)
        .where(m.QuestionTaxonomy.reviewed == False)  # noqa: E712
    ).all()
    from collections import Counter
    cnt = Counter()
    for conf, by in rows:
        bucket = "<0.35" if (conf or 0) < 0.35 else ">=0.35"
        cnt[(bucket, by)] += 1
    for k, v in sorted(cnt.items()):
        print("  ", k, v)
