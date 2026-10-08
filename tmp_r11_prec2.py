from __future__ import annotations
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
from sqlalchemy import select
from sqlalchemy.orm import Session
from examdata.core.db import get_session_factory, init_db
from examdata.core.models import Document, Paper, Question, QuestionTaxonomy, TaxonomyNode

def main():
    init_db()
    s = get_session_factory()()
    lines = []
    for pat in ["%hypothesis%", "%operationalised%"]:
        qs = list(s.scalars(select(Question).where(Question.stem_text.like(pat)).limit(300)))
        for q in qs:
            paper = s.get(Paper, q.paper_id)
            doc = s.get(Document, paper.document_id) if paper else None
            code = doc.paper_code if doc else "?"
            if not (code or "").startswith("wps02"):
                continue
            tags = list(s.scalars(select(QuestionTaxonomy).where(QuestionTaxonomy.question_id == q.id)))
            tagstr = []
            for t in tags:
                n = s.get(TaxonomyNode, t.node_id)
                tagstr.append(f"{n.code if n else '?'}({t.source},{t.confidence})")
            stem = (q.stem_text or "").replace("\n", " ")[:130]
            lines.append(f"q{q.id} {code} p{q.page_from} path={q.number_path} :: {stem}")
            lines.append(f"    tags: {tagstr}")
    s.close()
    print("\n".join(lines))
if __name__ == "__main__":
    main()
