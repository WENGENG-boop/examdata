"""Dump #3: same-phrase question tags + context parent tags."""
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from examdata.core import models as m

ROOT = Path(__file__).resolve().parent
DB = ROOT / ".data" / "examdata.db"
OUT = ROOT / "tmp_psy004_query3.txt"

engine = create_engine(f"sqlite:///{DB}")


def tagstr(s, qid):
    rows = s.execute(
        select(m.TaxonomyNode.code)
        .join(m.QuestionTaxonomy, m.QuestionTaxonomy.node_id == m.TaxonomyNode.id)
        .where(m.QuestionTaxonomy.question_id == qid)
        .order_by(m.TaxonomyNode.code)
    ).scalars().all()
    return ",".join(rows) or "-"


def paperinfo(s, qid):
    q = s.get(m.Question, qid)
    paper = s.get(m.Paper, q.paper_id)
    doc = s.get(m.Document, paper.document_id)
    return q, doc


lines = []
with Session(engine) as s:
    # subject id for psychology
    subj = s.execute(select(m.Subject).where(m.Subject.slug == "ial-psychology")).scalar()
    lines.append(f"subject: {subj.id if subj else None} {subj.slug if subj else ''}")

    def dump_phrase(title, like, cap=80):
        lines.append("")
        lines.append(f"===== {title} =====")
        n = 0
        rows = s.execute(
            select(m.Question).where(m.Question.stem_text.like(like)).order_by(m.Question.id)
        ).scalars().all()
        for q in rows:
            # filter psychology papers: paper_code of document
            paper = s.get(m.Paper, q.paper_id)
            doc = s.get(m.Document, paper.document_id)
            pc = (doc.paper_code or "").lower()
            if not pc.startswith("wps"):
                continue
            n += 1
            if n <= cap:
                stem = (q.stem_text or "").replace("\n", " ")
                lines.append(f"[{q.id}] {pc} {q.number_path}: {tagstr(s, q.id)}")
                lines.append(f"    {stem[:150]}")
        lines.append(f"count {n}")

    dump_phrase("'Justify' stems", "%Justify%")
    dump_phrase("'procedure' stems", "%procedure%")
    dump_phrase("'conclusion' stems", "%conclusion%")
    dump_phrase("'chosen contemporary study' stems", "%chosen contemporary study%")
    dump_phrase("'operationalised' stems", "%operationalised%")
    dump_phrase("'weakness' stems in WPS04", "%weakness%")

    lines.append("")
    lines.append("===== CONTEXT QIDS =====")
    for qid in [64775, 64776, 64777, 64780, 64782, 64783, 64784, 64821, 64823,
                64889, 64891, 64967, 64969, 64970, 64971, 65004, 65006, 65009,
                65010, 65046, 65047, 65050, 65091, 65092, 65093, 65099, 65100,
                65102, 65123, 64985, 64986, 64894, 64895, 64896, 64898, 64899,
                64900, 65122, 65124]:
        q, doc = paperinfo(s, qid)
        pc = (doc.paper_code or "").lower()
        lines.append(f"[{qid}] {pc} {q.number_path} m={q.marks}: {tagstr(s, qid)}")

OUT.write_text("\n".join(lines), encoding="utf-8")
print(f"written {len(lines)} lines -> {OUT}")
