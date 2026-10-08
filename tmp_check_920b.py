"""Deeper look v2: subj16/subj24 structure, duplicate check, 920-row landscape (ancestor-chain based)."""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session

from examdata.core import models as m

ROOT = Path(__file__).resolve().parent
DB = ROOT / ".data" / "examdata.db"

engine = create_engine(f"sqlite:///{DB}")
with Session(engine) as s:
    board = s.execute(select(m.Board).where(m.Board.key == "edexcel")).scalar()
    nodes = list(s.scalars(select(m.TaxonomyNode).where(m.TaxonomyNode.board_id == board.id)).all())
    by_id = {n.id: n for n in nodes}

    def root_code(node_id: int) -> str:
        cur = by_id.get(node_id)
        seen = 0
        while cur is not None and cur.parent_id and seen < 12:
            cur = by_id.get(cur.parent_id, cur)
            seen += 1
        return cur.code if cur else "?"

    # 1) subjects
    print("-- subjects --")
    for sid, title, slug in s.execute(select(m.Subject.id, m.Subject.title, m.Subject.slug).where(m.Subject.id.in_([16, 24, 17]))).all():
        n_docs = s.execute(select(func.count()).select_from(m.Document).where(m.Document.subject_id == sid)).scalar()
        print(f"  id={sid} slug={slug} title={title!r} docs={n_docs}")

    # units under subject roots ial-maths / ial18-mathematics
    print("\n-- units under each subject root --")
    for root in ("ial-maths", "ial18-mathematics"):
        rn = [n for n in nodes if n.code == root]
        print(f"  root {root}: nodes named {len(rn)}")
        if rn:
            kids = [n for n in nodes if n.parent_id == rn[0].id]
            for k in sorted(kids, key=lambda x: x.code):
                npts = sum(1 for n in nodes if n.node_type == "point" and n.parent_id == k.id)
                print(f"    {k.code:10} type={k.node_type:8} points(direct)={npts} name={k.name[:50]!r}")

    # 2) docs per paper x subject x year for key papers
    print("\n-- docs per paper x subject x year (key papers) --")
    docs = s.execute(
        select(m.Document.paper_code, m.Document.subject_id, m.Document.year, m.Document.id)
        .where(m.Document.paper_code.in_(["wst01-01","wst02-01","wst03-01","wme01-01","wme02-01","wme03-01","wfm01-01","wfm02-01","wfm03-01","wma01-01","wma02-01","wdm01-01"]))
        .order_by(m.Document.paper_code, m.Document.subject_id, m.Document.year)
    ).all()
    for pc, sid, yr, did in docs:
        nq = s.execute(select(func.count()).select_from(m.Question).join(m.Paper, m.Paper.id == m.Question.paper_id).where(m.Paper.document_id == did)).scalar()
        print(f"  {pc:10} subj={sid!s:3} {yr}  doc={did} nq={nq}")

    # 3) wfm01-01 2020 duplicate check
    print("\n-- wfm01-01 2020 docs detail --")
    for did, sid, title, ik in s.execute(
        select(m.Document.id, m.Document.subject_id, m.Document.title, m.Document.identity_key)
        .where(m.Document.paper_code == "wfm01-01", m.Document.year == 2020)
    ).all():
        qmin, qmax = s.execute(
            select(func.min(m.Question.id), func.max(m.Question.id)).select_from(m.Question).join(m.Paper, m.Paper.id == m.Question.paper_id)
            .where(m.Paper.document_id == did)
        ).one()
        stems = s.execute(
            select(m.Question.number_path, func.substr(m.Question.stem_text, 1, 50)).select_from(m.Question).join(m.Paper, m.Paper.id == m.Question.paper_id)
            .where(m.Paper.document_id == did).order_by(m.Question.display_order).limit(2)
        ).all()
        print(f"  doc={did} subj={sid} key={ik}")
        print(f"    title={title!r} qids {qmin}-{qmax}")
        for np_, st in stems:
            print(f"    {np_!r}: {(st or '').strip()[:50]!r}")

    # 4) ial-maths batches paper coverage
    print("\n-- ial-maths batches: paper coverage --")
    mp = ROOT / ".data" / "tagging" / "review-export" / "ial-maths" / "batches"
    pcs = Counter()
    for p in sorted(mp.glob("*.jsonl")):
        for line in p.read_text(encoding="utf-8").split("\n"):
            if line.strip():
                pcs[json.loads(line)["paper_code"]] += 1
    for pc, n in sorted(pcs.items()):
        print(f"  {pc}: {n}")

    # 5) the conf<0.35 unrev bm25 rows: landscape
    print("\n-- conf<0.35 unreviewed bm25 rows (whole DB) --")
    rows = s.execute(
        select(
            m.QuestionTaxonomy.id, m.QuestionTaxonomy.question_id, m.QuestionTaxonomy.confidence,
            m.QuestionTaxonomy.node_id, m.Document.subject_id, m.Document.paper_code, m.Document.year,
        )
        .select_from(m.QuestionTaxonomy)
        .join(m.Question, m.Question.id == m.QuestionTaxonomy.question_id)
        .join(m.Paper, m.Paper.id == m.Question.paper_id)
        .join(m.Document, m.Document.id == m.Paper.document_id)
        .where(m.QuestionTaxonomy.reviewed == False)  # noqa: E712
        .where(m.QuestionTaxonomy.assigned_by == "edexcel-bm25-v1")
        .where(m.QuestionTaxonomy.confidence < 0.35)
    ).all()
    print(f"  total rows: {len(rows)}")
    print(f"  by doc subject: {dict(Counter(r[4] for r in rows))}")
    print(f"  by node root:   {dict(Counter(root_code(r[3]) for r in rows))}")
    print(f"  by (paper,year): {dict(sorted(Counter((r[5], r[6]) for r in rows).items(), key=lambda kv: (kv[0][0], kv[0][1])))}")
    qids = {r[1] for r in rows}
    print(f"  distinct questions: {len(qids)}")
    per_q = defaultdict(list)
    for r in s.execute(
        select(m.QuestionTaxonomy.question_id, m.QuestionTaxonomy.reviewed, m.QuestionTaxonomy.confidence, m.TaxonomyNode.id)
        .select_from(m.QuestionTaxonomy)
        .join(m.TaxonomyNode, m.TaxonomyNode.id == m.QuestionTaxonomy.node_id)
        .where(m.QuestionTaxonomy.question_id.in_(qids))
    ).all():
        per_q[r[0]].append((r[1], r[2], r[3]))
    print(f"  rows per question: min={min(len(v) for v in per_q.values())} max={max(len(v) for v in per_q.values())}")
    print(f"  questions w/ >=1 reviewed row: {sum(1 for v in per_q.values() if any(x[0] for x in v))}")
    print(f"  questions w/ >=1 conf>=0.35 unrev row: {sum(1 for v in per_q.values() if any((not x[0]) and x[1] >= 0.35 for x in v))}")
    print(f"  unit dist: {dict(Counter(root_code(r[3]) for r in rows))}")
    # roots of codes for the 920
    print(f"  code unit dist: {dict(Counter(r[3] and by_id[r[3]].code.split('-')[0] for r in rows))}")
