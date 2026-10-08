"""Dump #4: stem+tags for reference qids; parent contexts; WPS02 hypothesis questions."""
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from examdata.core import models as m

ROOT = Path(__file__).resolve().parent
DB = ROOT / ".data" / "examdata.db"
OUT = ROOT / "tmp_psy004_query4b.txt"

engine = create_engine(f"sqlite:///{DB}")


def tagstr(s, qid):
    rows = s.execute(
        select(m.TaxonomyNode.code)
        .join(m.QuestionTaxonomy, m.QuestionTaxonomy.node_id == m.TaxonomyNode.id)
        .where(m.QuestionTaxonomy.question_id == qid)
        .order_by(m.TaxonomyNode.code)
    ).scalars().all()
    return ",".join(rows) or "-"


REF = [61823, 64280, 64405, 64728, 64564, 65500, 61801, 61413, 64253, 61411,
       64318, 65934, 64952, 64710, 64441, 64569, 64906, 64865, 64989, 64990,
       64746, 64818, 64826, 64941, 64760, 65021, 64940, 65123, 64968, 65008,
       64822, 64890, 64778, 64987, 65067, 65122, 64897, 65005, 65007, 65071,
       65072, 65073, 65094, 65101, 65103, 65124, 65048, 65049]

PARENT_CTX = [61913, 64400, 65557, 65890, 64507, 64257, 61856, 61870]

lines = []
with Session(engine) as s:
    lines.append("===== REF QIDS =====")
    for qid in REF:
        q = s.get(m.Question, qid)
        if not q:
            lines.append(f"[{qid}] MISSING")
            continue
        paper = s.get(m.Paper, q.paper_id)
        doc = s.get(m.Document, paper.document_id)
        pc = (doc.paper_code or "").lower()
        stem = (q.stem_text or "").replace("\n", " ")
        lines.append(f"[{qid}] {pc} {q.number_path} m={q.marks}: {tagstr(s, qid)}")
        lines.append(f"    {stem[:170]}")

    lines.append("")
    lines.append("===== PARENT CONTEXTS =====")
    for qid in PARENT_CTX:
        q = s.get(m.Question, qid)
        paper = s.get(m.Paper, q.paper_id)
        doc = s.get(m.Document, paper.document_id)
        pc = (doc.paper_code or "").lower()
        stem = (q.stem_text or "").replace("\n", " ")
        lines.append(f"[{qid}] {pc} {q.number_path}: {tagstr(s, qid)}")
        lines.append(f"    STEM: {stem[:260]}")
        kids = s.execute(
            select(m.Question).where(m.Question.parent_id == qid).order_by(m.Question.id)
        ).scalars().all()
        for k in kids:
            kstem = (k.stem_text or "").replace("\n", " ")
            lines.append(f"    kid [{k.id}] {k.number_path}: {tagstr(s, k.id)}")
            lines.append(f"        {kstem[:110]}")

    lines.append("")
    lines.append("===== WPS02 hypothesis questions =====")
    qs = s.execute(
        select(m.Question).where(m.Question.stem_text.like("%hypothesis%"))
    ).scalars().all()
    for q in qs:
        paper = s.get(m.Paper, q.paper_id)
        doc = s.get(m.Document, paper.document_id)
        pc = (doc.paper_code or "").lower()
        if not pc.startswith("wps02"):
            continue
        stem = (q.stem_text or "").replace("\n", " ")
        lines.append(f"[{q.id}] {pc} {q.number_path}: {tagstr(s, q.id)}")
        lines.append(f"    {stem[:150]}")

OUT.write_text("\n".join(lines), encoding="utf-8")
print(f"written {len(lines)} lines -> {OUT}")
