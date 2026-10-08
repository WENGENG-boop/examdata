"""Paper structure dumps + precedent searches for the remaining r12 decisions."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
from sqlalchemy import select
from examdata.core.db import get_session_factory, init_db
from examdata.core.models import Document, Paper, Question, QuestionTaxonomy, TaxonomyNode

init_db()
s = get_session_factory()()
out = []


def tags_of(q):
    out = []
    for t in s.scalars(select(QuestionTaxonomy).where(QuestionTaxonomy.question_id == q.id)):
        n = s.get(TaxonomyNode, t.node_id)
        out.append(f"{n.code if n else '?'}({t.source},{t.confidence:.3f})")
    return out


def show_paper(qid):
    q = s.get(Question, qid)
    p = s.get(Paper, q.paper_id)
    d = s.get(Document, p.document_id) if p else None
    out.append(f"### q{qid} paper_id={q.paper_id} doc={d.id if d else '?'} code={d.paper_code if d else '?'} title={(d.title if d else '')[:90]}")
    qs = list(s.scalars(select(Question).where(Question.paper_id == q.paper_id).order_by(Question.page_from, Question.id)))
    for qq in qs:
        stem = (qq.stem_text or "").replace("\n", " ")[:100]
        out.append(f"  q{qq.id} p{qq.page_from} {qq.number_path} m={qq.marks} {stem}")
        out.append(f"      {tags_of(qq)}")


for qid in [68555, 68563, 68440, 68324, 68343, 68412, 68471]:
    show_paper(qid)
    out.append("")

out.append("=== precedent searches ===")
pats = ["%full set of books%", "%hypothesis%", "%depreciation polic%", "%straight line method%",
        "%volunteer sampling%", "%goods stolen%", "%security system%", "%capital accounts of the partners%"]
for pat in pats:
    qs = list(s.scalars(select(Question).where(Question.stem_text.like(pat)).limit(300)))
    out.append(f"--- {pat} ({len(qs)})")
    for q in qs:
        p = s.get(Paper, q.paper_id)
        d = s.get(Document, p.document_id) if p else None
        stem = (q.stem_text or "").replace("\n", " ")[:110]
        out.append(f"  q{q.id} {d.paper_code if d else '?'} p{q.page_from} {q.number_path} :: {stem} :: {tags_of(q)}")

s.close()
(ROOT / "tmp_r12_q3_out.txt").write_text("\n".join(out), encoding="utf-8")
print("written", len(out), "lines")
