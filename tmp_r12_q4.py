"""Round 2: verify the 48 list, MS entries for pending qids, full stems, goodwill precedents."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
from sqlalchemy import select, or_
from examdata.core.db import get_session_factory, init_db
from examdata.core.models import (
    Document, Paper, Question, QuestionTaxonomy, TaxonomyNode, MarkSchemeEntry,
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


low = json.loads((ROOT / "tmp_r8_new_lowconf.json").read_text(encoding="utf-8"))
out.append(f"### lowconf count = {len(low)}")
for item in low:
    qid = item.get("question_id")
    out.append(
        f"  q{qid} {item.get('paper_code')} {item.get('number_path')} top={item.get('top_confidence')} "
        f":: {str(item.get('stem_text') or item.get('stem') or '')[:90]}"
    )

pend = [68324, 68343, 68412, 68414, 68440, 68471, 68472, 68470, 68555, 68563, 68494,
        68570, 68544, 68549, 68529, 68531, 68525, 68512]
out.append("### MS entries")
for qid in pend:
    entries = list(s.scalars(select(MarkSchemeEntry).where(MarkSchemeEntry.question_id == qid)))
    if entries:
        for e in entries:
            out.append(f"  q{qid} {e.number_path} m={e.marks} :: {repr((e.answer_text or '')[:500])}")
    else:
        out.append(f"  q{qid} :: (no MS entry)")

for qid in [68338, 68341, 68342, 68343, 68469, 68470, 68471, 68472]:
    q = s.get(Question, qid)
    if q:
        out.append(f"### full stem q{qid} {q.number_path} m={q.marks} page={q.page_from}")
        out.append((q.stem_text or "")[:2500])

qs = list(s.scalars(select(Question).where(Question.stem_text.like('%goodwill%')).limit(200)))
out.append(f"### goodwill questions ({len(qs)})")
for q in qs:
    p = s.get(Paper, q.paper_id)
    d = s.get(Document, p.document_id) if p else None
    out.append(f"  q{q.id} {d.paper_code if d else '?'} p{q.page_from} {q.number_path} :: {(q.stem_text or '')[:100]!r} :: {tags_of(q)}")

docs = list(s.scalars(select(Document).where(or_(Document.title.like('%booklet%'), Document.title.like('%Source%'))).limit(100)))
out.append(f"### booklet docs ({len(docs)})")
for d in docs:
    out.append(f"  doc{d.id} {d.paper_code} {d.title}")

s.close()
(ROOT / "tmp_r12_q4_out.txt").write_text("\n".join(out), encoding="utf-8")
print("written", len(out))
