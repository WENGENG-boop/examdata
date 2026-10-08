"""Analyze ial-maths 920 limbo rows: batch coverage vs the 9 affected papers; WPS*I5 tree rows."""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from examdata.core import models as m

ROOT = Path(__file__).resolve().parent
DB = ROOT / ".data" / "examdata.db"
REVIEW = ROOT / ".data" / "tagging" / "review-export" / "ial18-mathematics"

PAPERS9 = ["wst01-01", "wst02-01", "wme01-01", "wfm01-01", "wme02-01",
           "wfm03-01", "wme03-01", "wst03-01", "wfm02-01"]

engine = create_engine(f"sqlite:///{DB}")
with Session(engine) as s:
    # 1) covered qids -> (paper_code, year)
    covered_qids = set()
    for p in sorted(REVIEW.glob("batches/batch-*.jsonl")):
        for line in p.read_text(encoding="utf-8").split("\n"):
            if line.strip():
                covered_qids.add(json.loads(line)["question_id"])
    print(f"batch qids: {len(covered_qids)}")

    cov = s.execute(
        select(m.Document.paper_code, m.Document.year, m.Question.id)
        .select_from(m.Question)
        .join(m.Paper, m.Paper.id == m.Question.paper_id)
        .join(m.Document, m.Document.id == m.Paper.document_id)
        .where(m.Question.id.in_(covered_qids))
    ).all()
    covered_py = defaultdict(set)  # (paper,year) -> qids
    for pc, yr, qid in cov:
        covered_py[(pc, yr)].add(qid)
    covered_pairs = set(covered_py)
    print(f"covered (paper,year) pairs: {len(covered_pairs)}")

    # 2) all (paper,year,subject) combos for the 9 papers with taxonomy row stats
    rows = s.execute(
        select(
            m.Document.paper_code, m.Document.year, m.Document.subject_id,
            m.QuestionTaxonomy.reviewed, m.QuestionTaxonomy.assigned_by,
            m.Question.id,
        )
        .select_from(m.QuestionTaxonomy)
        .join(m.Question, m.Question.id == m.QuestionTaxonomy.question_id)
        .join(m.Paper, m.Paper.id == m.Question.paper_id)
        .join(m.Document, m.Document.id == m.Paper.document_id)
        .where(m.Document.paper_code.in_(PAPERS9))
    ).all()
    stat = defaultdict(lambda: Counter())
    qids_in = defaultdict(set)
    for pc, yr, sid, rev, ab, qid in rows:
        key = (pc, yr, sid)
        stat[key]["total"] += 1
        stat[key]["unrev" if not rev else "rev"] += 1
        if not rev:
            stat[key][f"unrev::{ab}"] += 1
        qids_in[key].add(qid)
    print("\n-- 9 papers: (paper, year, subject) row stats --")
    print(f"{'paper':10} {'year':5} {'subj':5} {'total':6} {'rev':5} {'unrev':6}  covered_by_batches  unrev_assigned_by")
    for key in sorted(stat, key=lambda k: (k[0], k[1] or 0)):
        pc, yr, sid = key
        c = stat[key]
        in_cov = "YES" if (pc, yr) in covered_pairs else "no"
        unrev_by = {k.split("::")[1]: v for k, v in c.items() if k.startswith("unrev::")}
        print(f"{pc:10} {yr!s:5} {sid!s:5} {c['total']:6} {c['rev']:5} {c['unrev']:6}  {in_cov:18}  {unrev_by}")

    # 3) which batch (paper,year) pairs exist but with only partial years covered?
    print("\n-- coverage pairs involving the 9 paper codes --")
    for pc, yr in sorted((p for p in covered_pairs if p[0] in PAPERS9), key=lambda k: (k[0], k[1] or 0)):
        print(f"  {pc} {yr}  nq={len(covered_py[(pc, yr)])}")

    # 4) WPS*I5 rows
    print("\n-- WPS*I5 taxonomy rows --")
    i5 = s.execute(
        select(
            m.TaxonomyNode.code, m.QuestionTaxonomy.question_id, m.QuestionTaxonomy.reviewed,
            m.QuestionTaxonomy.assigned_by, m.QuestionTaxonomy.confidence,
            m.QuestionTaxonomy.created_at,
            m.Document.paper_code, m.Document.year, m.Document.subject_id,
        )
        .select_from(m.QuestionTaxonomy)
        .join(m.TaxonomyNode, m.TaxonomyNode.id == m.QuestionTaxonomy.node_id)
        .join(m.Question, m.Question.id == m.QuestionTaxonomy.question_id)
        .join(m.Paper, m.Paper.id == m.Question.paper_id)
        .join(m.Document, m.Document.id == m.Paper.document_id)
        .where(m.TaxonomyNode.code.like("%I5%"))
        .order_by(m.TaxonomyNode.code, m.QuestionTaxonomy.question_id)
    ).all()
    print(f"total I5 rows: {len(i5)}")
    for code, qid, rev, ab, conf, created, pc, yr, sid in i5:
        print(f"  {code:14} q{qid:6} rev={int(rev)} by={ab} conf={conf:.3f} created={created} {pc} {yr} subj={sid}")

    # 5) sanity: do the 920 rows' qids appear in ANY review-export batch of any subject?
    unrev920 = s.execute(
        select(m.QuestionTaxonomy.question_id)
        .select_from(m.QuestionTaxonomy)
        .join(m.Question, m.Question.id == m.QuestionTaxonomy.question_id)
        .join(m.Paper, m.Paper.id == m.Question.paper_id)
        .join(m.Document, m.Document.id == m.Paper.document_id)
        .where(m.Document.paper_code.in_(PAPERS9))
        .where(m.QuestionTaxonomy.reviewed == False)  # noqa: E712
        .where(m.QuestionTaxonomy.assigned_by == "edexcel-bm25-v1")
    ).scalars().all()
    uq = set(unrev920)
    print(f"\nunreviewed bm25 qids on 9 papers: {len(uq)}")
    all_batch_qids = set()
    for slug_dir in (ROOT / ".data" / "tagging" / "review-export").iterdir():
        bp = slug_dir / "batches"
        if bp.is_dir():
            for p in bp.glob("*.jsonl"):
                for line in p.read_text(encoding="utf-8").split("\n"):
                    if line.strip():
                        all_batch_qids.add(json.loads(line)["question_id"])
    inter = uq & all_batch_qids
    print(f"of those, present in some subject's batch: {len(inter)}")
    # which subjects
    for slug_dir in sorted((ROOT / ".data" / "tagging" / "review-export").iterdir()):
        bp = slug_dir / "batches"
        if bp.is_dir():
            s_q = set()
            for p in bp.glob("*.jsonl"):
                for line in p.read_text(encoding="utf-8").split("\n"):
                    if line.strip():
                        s_q.add(json.loads(line)["question_id"])
            n = len(uq & s_q)
            if n:
                print(f"  {slug_dir.name}: {n}")
