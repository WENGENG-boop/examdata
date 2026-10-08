"""Round 3: remaining pending verdicts — current tags, precedents (depreciation policy,
stolen/theft/security), partner statement in paper 1358, Eva scenario in paper 1412."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
from sqlalchemy import select, or_
from examdata.core.db import get_session_factory, init_db
from examdata.core.models import (
    Document, Paper, Question, QuestionTaxonomy, TaxonomyNode,
)

init_db()
s = get_session_factory()()
out = []


def tags_of(q):
    res = []
    for t in s.scalars(select(QuestionTaxonomy).where(QuestionTaxonomy.question_id == q.id)):
        n = s.get(TaxonomyNode, t.node_id)
        res.append(f"{n.code if n else '?'}({t.source},{t.confidence:.3f})")
    return res


def qinfo(qid):
    q = s.get(Question, qid)
    if not q:
        return f"q{qid} MISSING"
    p = s.get(Paper, q.paper_id)
    d = s.get(Document, p.document_id) if p else None
    return (f"q{qid} {d.paper_code if d else '?'} p{q.page_from} {q.number_path} m={q.marks} "
            f":: {tags_of(q)}")


out.append("### current tags of pending qids")
for qid in [68324, 68343, 68440, 68470, 68471, 68472, 68412, 68414]:
    out.append(qinfo(qid))

out.append("### depreciation policy precedents")
for qid in [46402, 48434, 68384, 68477]:
    q = s.get(Question, qid)
    if q:
        out.append(f"--- q{qid} {q.number_path} m={q.marks}")
        out.append((q.stem_text or "")[:600])
        out.append(f"    tags: {tags_of(q)}")

out.append("### WAC11 stolen/theft/security questions")
qs = list(s.scalars(select(Question).where(or_(
    Question.stem_text.like('%stolen%'),
    Question.stem_text.like('%theft%'),
    Question.stem_text.like('%security%'),
    Question.stem_text.like('%burglar%'),
)).limit(300)))
for q in qs:
    p = s.get(Paper, q.paper_id)
    d = s.get(Document, p.document_id) if p else None
    code = d.paper_code if d else "?"
    if code and ("wac" in code or "wge" in code):
        out.append(f"  q{q.id} {code} p{q.page_from} {q.number_path} :: {(q.stem_text or '')[:150]!r} :: {tags_of(q)}")

out.append("### paper 1358 questions pages 28-38 (find partner statement)")
qs = list(s.scalars(select(Question).where(Question.paper_id == 1358).order_by(Question.page_from, Question.id)))
for q in qs:
    if q.page_from and 28 <= q.page_from <= 38:
        out.append(f"--- q{q.id} p{q.page_from} {q.number_path} m={q.marks}")
        out.append((q.stem_text or "")[:700])

out.append("### paper 1412 questions pages 16-24 (Eva scenario)")
qs = list(s.scalars(select(Question).where(Question.paper_id == 1412).order_by(Question.page_from, Question.id)))
for q in qs:
    if q.page_from and 16 <= q.page_from <= 24:
        out.append(f"--- q{q.id} p{q.page_from} {q.number_path} m={q.marks}")
        out.append((q.stem_text or "")[:900])

s.close()
(ROOT / "tmp_r12_q5_out.txt").write_text("\n".join(out), encoding="utf-8")
print("written", len(out))
