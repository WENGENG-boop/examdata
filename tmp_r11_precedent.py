"""Find precedent questions (same skill) and their current tags."""
from __future__ import annotations
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
from sqlalchemy import select, or_
from sqlalchemy.orm import Session
from examdata.core.db import get_session_factory, init_db
from examdata.core.models import Document, Paper, Question, QuestionTaxonomy, Subject, TaxonomyNode

PATTERNS = ["%Wilcoxon%", "%volunteer sampling%", "%volunteer sample%", "%Spearman%", "%hypothesis for Loreen%", "%non-directional (two-tailed) hypothesis%"]
SPECIFIC_IDS = [68556, 65170, 65171, 65762, 65763, 65764, 66056, 66057, 66066, 66067]

def main():
    init_db()
    session = get_session_factory()()
    seen = {}
    rows = []
    for pat in PATTERNS:
        qs = list(session.scalars(select(Question).where(Question.stem_text.like(pat)).limit(200)))
        for q in qs:
            rows.append((pat, q))
    qs = [session.get(Question, qid) for qid in SPECIFIC_IDS]
    for q in qs:
        if q:
            rows.append(("id", q))
    lines = []
    for pat, q in rows:
        if q.id in seen:
            continue
        seen[q.id] = True
        paper = session.get(Paper, q.paper_id)
        doc = session.get(Document, paper.document_id) if paper else None
        tags = list(session.scalars(select(QuestionTaxonomy).where(QuestionTaxonomy.question_id == q.id)))
        tagstr = []
        for t in tags:
            n = session.get(TaxonomyNode, t.node_id)
            tagstr.append(f"{n.code if n else '?'}({t.source},conf={t.confidence})")
        stem = (q.stem_text or "").replace("\n", " ")[:160]
        lines.append(f"q{q.id} {doc.paper_code if doc else '?'} p{q.page_from} path={q.number_path} :: {stem}")
        lines.append(f"    tags: {tagstr}")
    session.close()
    out = "\n".join(lines)
    (ROOT / "tmp_r11_precedent.txt").write_text(out, encoding="utf-8")
    print(out[:6000])

if __name__ == "__main__":
    main()
