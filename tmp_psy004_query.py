"""Dump info needed to finalize ial-psychology batch-004 decisions."""
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from examdata.core import models as m

ROOT = Path(__file__).resolve().parent
DB = ROOT / ".data" / "examdata.db"
OUT = ROOT / "tmp_psy004_query.txt"

UNDECIDED = [64778, 64822, 64890, 64897, 64968, 64987, 65005, 65007,
             65008, 65048, 65049, 65067, 65071, 65072, 65073, 65094,
             65101, 65103, 65122, 65124]
STYLE = [65359, 65298, 64250, 64251, 64659, 64660]

CODES = [
    "WPS04-9.1.9", "WPS04-9.1.11", "WPS04-9.1.13", "WPS04-9.1.16",
    "WPS04-9.1.17", "WPS04-9.2.1", "WPS04-9.3.1", "WPS04-9.3.2",
    "WPS04-9.3.3", "WPS04-9.3.4", "WPS04-9.3.5", "WPS04-9.3.6",
    "WPS04-9.3.7", "WPS04-9.3.8", "WPS04-9.3.9", "WPS04-9.3.10",
    "WPS04-9.3.11",
    "WPS01-1.4.1", "WPS01-2.4.1", "WPS01-1.2.3", "WPS01-2.2.11",
    "WPS02-3.2.7", "WPS02-3.3.3", "WPS02-3.3.4", "WPS02-4.2.5",
    "WPS02-4.2.8",
    "WPS03-5.3.1", "WPS03-5.3.4", "WPS03-5.4.2", "WPS03-6.3.1",
    "WPS03-6.3.3", "WPS03-7.3.1", "WPS03-7.3.3",
]

# qid whose paper should be dumped at top level
PAPER_QIDS = [64822, 65122, 65048, 65094, 64890, 64987, 65005, 65067, 64968]

engine = create_engine(f"sqlite:///{DB}")


def tagstr(s, qid):
    rows = s.execute(
        select(m.TaxonomyNode.code, m.TaxonomyNode.name)
        .join(m.QuestionTaxonomy, m.QuestionTaxonomy.node_id == m.TaxonomyNode.id)
        .where(m.QuestionTaxonomy.question_id == qid)
        .order_by(m.TaxonomyNode.code)
    ).all()
    return " | ".join(f"{c} {n}" for c, n in rows)


def doc_title(s, paper):
    doc = s.get(m.Document, paper.document_id)
    t = getattr(doc, "title", None)
    if not t:
        t = (getattr(doc, "attrs", None) or {}).get("title")
    return t or f"doc#{doc.id}"


lines = []
with Session(engine) as s:
    lines.append("=========== STYLE REFS ===========")
    for qid in STYLE:
        q = s.get(m.Question, qid)
        lines.append(f"[{qid}] {q.number_path} :: {tagstr(s, qid)}")
        lines.append(f"    stem: {(q.stem_text or '')[:220]}")

    lines.append("")
    lines.append("=========== UNDECIDED QUESTIONS ===========")
    for qid in UNDECIDED:
        q = s.get(m.Question, qid)
        paper = s.get(m.Paper, q.paper_id)
        title = doc_title(s, paper)
        lines.append("")
        lines.append(f"##### [{qid}] {title} :: {q.number_path} (marks={q.marks})")
        lines.append(f"  current: {tagstr(s, qid)}")
        stem = (q.stem_text or "").replace("\n", " ")
        lines.append(f"  stem: {stem[:900]}")
        kids = s.execute(
            select(m.Question).where(m.Question.parent_id == qid)
            .order_by(m.Question.id)
        ).scalars().all()
        for k in kids:
            kstem = (k.stem_text or "").replace("\n", " ")
            lines.append(f"    kid {k.number_label}: {kstem[:150]}")

    lines.append("")
    lines.append("=========== PAPER TOP-LEVEL DUMPS ===========")
    seen_papers = set()
    for qid in PAPER_QIDS:
        q = s.get(m.Question, qid)
        paper = s.get(m.Paper, q.paper_id)
        if paper.id in seen_papers:
            continue
        seen_papers.add(paper.id)
        title = doc_title(s, paper)
        lines.append("")
        lines.append(f"===== PAPER {title} (paper#{paper.id}) =====")
        tops = s.execute(
            select(m.Question)
            .where(m.Question.paper_id == paper.id, m.Question.parent_id.is_(None))
            .order_by(m.Question.id)
        ).scalars().all()
        for t in tops:
            stem = (t.stem_text or "").replace("\n", " ")
            lines.append(f"  {t.number_path} (m={t.marks}): {stem[:90]}")

    lines.append("")
    lines.append("=========== TAXONOMY TITLES ===========")
    rows = s.execute(
        select(m.TaxonomyNode.code, m.TaxonomyNode.name)
        .where(m.TaxonomyNode.code.in_(CODES))
        .order_by(m.TaxonomyNode.code)
    ).all()
    for c, n in rows:
        lines.append(f"{c}  {n}")

OUT.write_text("\n".join(lines), encoding="utf-8")
print(f"written {len(lines)} lines -> {OUT}")
