"""Fix duplicate-copy questions' labels to match their originals (batch-001 follow-up).

64522/64525/64531 were kept as reviewed=True in an earlier batch, so review-apply
can no longer change them. Set them directly to match their originals' final labels.
64532/64501 already match; not touched.
"""
import datetime
import json
import re
from pathlib import Path

from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session

from examdata.core import models as m

ROOT = Path(__file__).resolve().parent
DB = ROOT / ".data" / "examdata.db"
LOG = ROOT / ".data" / "tagging" / "review-export" / "ial-psychology" / "decisions" / "fixups-dup-copies.jsonl"

PAIRS = [
    (61319, 64522, "WPS01-1.2.6"),
    (61322, 64525, "WPS01-1.2.6"),
    (61328, 64531, "WPS01-2.2.6"),
]


def norm(t):
    return re.sub(r"\s+", " ", (t or "")).strip()


engine = create_engine(f"sqlite:///{DB}")
logrows = []
with Session(engine) as s:
    for orig, dup, code in PAIRS:
        qo = s.get(m.Question, orig)
        qd = s.get(m.Question, dup)
        so, sd = norm(qo.stem_text), norm(qd.stem_text)
        assert so and so == sd, f"stems differ for {orig}/{dup}"
        node = s.execute(select(m.TaxonomyNode).where(m.TaxonomyNode.code == code)).scalar_one()
        before = [
            r[0]
            for r in s.execute(
                select(m.TaxonomyNode.code)
                .join(m.QuestionTaxonomy, m.QuestionTaxonomy.node_id == m.TaxonomyNode.id)
                .where(m.QuestionTaxonomy.question_id == dup)
            ).all()
        ]
        s.execute(delete(m.QuestionTaxonomy).where(m.QuestionTaxonomy.question_id == dup))
        s.add(
            m.QuestionTaxonomy(
                question_id=dup,
                node_id=node.id,
                source="ai-review",
                confidence=1.0,
                assigned_by="ai-review-v1",
                reviewed=True,
            )
        )
        logrows.append(
            {
                "dup_question_id": dup,
                "orig_question_id": orig,
                "before": before,
                "after": code,
                "at": datetime.datetime.now().isoformat(timespec="seconds"),
            }
        )
        print(f"{dup} <- {orig}: {before} -> [{code}]")
    s.commit()
    print("--- readback ---")
    for _, dup, code in PAIRS:
        codes = [
            r[0]
            for r in s.execute(
                select(m.TaxonomyNode.code)
                .join(m.QuestionTaxonomy, m.QuestionTaxonomy.node_id == m.TaxonomyNode.id)
                .where(m.QuestionTaxonomy.question_id == dup)
            ).all()
        ]
        print(dup, codes, "ok=", codes == [code])

with LOG.open("a", encoding="utf-8") as f:
    for r in logrows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print("logged ->", LOG)
