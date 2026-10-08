"""Dump #2 needed to finalize ial-psychology batch-004 decisions."""
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from examdata.core import models as m

ROOT = Path(__file__).resolve().parent
DB = ROOT / ".data" / "examdata.db"
OUT = ROOT / "tmp_psy004_query2.txt"

PREFIXES = [
    "WPS01-1.2", "WPS01-2.2", "WPS01-1.3", "WPS01-2.3", "WPS01-1.4", "WPS01-2.4",
    "WPS02-3.2", "WPS02-4.2", "WPS02-3.3", "WPS02-4.3", "WPS02-3.4", "WPS02-4.4",
    "WPS03-5.1", "WPS03-5.2", "WPS03-5.3", "WPS03-5.4", "WPS03-6.3", "WPS03-7.3",
    "WPS04-8.2", "WPS04-8.3", "WPS04-8.4", "WPS04-9.1", "WPS04-9.2", "WPS04-9.3",
]

CTX = [
    (64778, "1"), (64778, "2"), (64778, "3"),
    (64822, "3"), (64897, "2"), (64968, "7"), (64987, "3"),
    (65005, "1"), (65005, "2"), (65048, "6"),
    (65067, "3"), (65067, "5"), (65094, "8"), (65094, "10"),
    (64890, "9"),
]

Q55 = [64737, 64746, 64760, 64776, 64778, 64779, 64781, 64783, 64784, 64791,
       64796, 64809, 64818, 64822, 64826, 64865, 64890, 64897, 64898, 64899,
       64900, 64906, 64907, 64908, 64910, 64918, 64919, 64921, 64940, 64941,
       64952, 64968, 64987, 64989, 64990, 65005, 65007, 65008, 65021, 65048,
       65049, 65060, 65067, 65071, 65072, 65073, 65094, 65101, 65103, 65106,
       65111, 65122, 65124, 65140, 65144]

engine = create_engine(f"sqlite:///{DB}")


def tagstr(s, qid):
    rows = s.execute(
        select(m.TaxonomyNode.code)
        .join(m.QuestionTaxonomy, m.QuestionTaxonomy.node_id == m.TaxonomyNode.id)
        .where(m.QuestionTaxonomy.question_id == qid)
        .order_by(m.TaxonomyNode.code)
    ).scalars().all()
    return ",".join(rows) or "-"


def doc_title(s, paper):
    doc = s.get(m.Document, paper.document_id)
    t = getattr(doc, "title", None) or (getattr(doc, "attrs", None) or {}).get("title")
    return t or f"doc#{doc.id}"


lines = []
with Session(engine) as s:
    lines.append("========== TAXONOMY TREES ==========")
    for pre in PREFIXES:
        rows = s.execute(
            select(m.TaxonomyNode.code, m.TaxonomyNode.name)
            .where(m.TaxonomyNode.code.like(pre + "%"))
            .order_by(m.TaxonomyNode.code)
        ).all()
        lines.append(f"--- {pre} ({len(rows)}) ---")
        for c, n in rows:
            lines.append(f"{c}  {n}")

    lines.append("")
    lines.append("========== PARENTS IN BATCH-004 PAPERS ==========")
    seen_pid = {}
    for qid in Q55:
        q = s.get(m.Question, qid)
        seen_pid[q.paper_id] = q
    for pid, q in seen_pid.items():
        paper = s.get(m.Paper, pid)
        title = doc_title(s, paper)
        parents = s.execute(
            select(m.Question)
            .where(m.Question.paper_id == pid, m.Question.parent_id.is_(None))
            .order_by(m.Question.id)
        ).scalars().all()
        for p in parents:
            kids = s.execute(
                select(m.Question.id).where(m.Question.parent_id == p.id)
            ).scalars().all()
            if not kids:
                continue
            rev = s.execute(
                select(m.QuestionTaxonomy.reviewed)
                .where(m.QuestionTaxonomy.question_id == p.id)
            ).scalars().all()
            lines.append(
                f"[{p.id}] {title} :: {p.number_path} kids={len(kids)} "
                f"rev={all(rev) if rev else None} :: {tagstr(s, p.id)}"
            )

    lines.append("")
    lines.append("========== CONTEXT DUMPS ==========")
    seen = set()
    for rep, prefix in CTX:
        q = s.get(m.Question, rep)
        pid = q.paper_id
        key = (pid, prefix)
        if key in seen:
            continue
        seen.add(key)
        paper = s.get(m.Paper, pid)
        title = doc_title(s, paper)
        rows = s.execute(
            select(m.Question)
            .where(m.Question.paper_id == pid)
            .order_by(m.Question.id)
        ).scalars().all()
        sel = [r for r in rows
               if r.number_path == prefix or (r.number_path or "").startswith(prefix + "(")]
        lines.append(f"##### {title} :: prefix {prefix} ({len(sel)})")
        for r in sel:
            stem = (r.stem_text or "").replace("\n", " ")
            lines.append(f"  [{r.id}] {r.number_path} m={r.marks} cur={tagstr(s, r.id)}")
            lines.append(f"      {stem[:600]}")

OUT.write_text("\n".join(lines), encoding="utf-8")
print(f"written {len(lines)} lines -> {OUT}")
