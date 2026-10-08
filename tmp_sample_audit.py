"""Sample questions for independent audit of Jev-applied tags (>=20 questions).

Draws stratified random samples from the decision files of the 102 applied
batches, and dumps question context + final DB tags + answers for manual review.

Usage:
  python tmp_sample_audit.py                 # 4 per subject -> 24 questions
  python tmp_sample_audit.py --n 5 --seed 42
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from examdata.core import models as m

ROOT = Path(__file__).resolve().parent
DB = ROOT / ".data" / "examdata.db"
REVIEW = ROOT / ".data" / "tagging" / "review-export"

SUBJECTS = {
    "ial-spanish": ["003"],
    "ial18-biology": [f"{i:03d}" for i in range(3, 14)],
    "ial18-chemistry": [f"{i:03d}" for i in range(1, 10)],
    "ial18-economics": [f"{i:03d}" for i in range(1, 12)],
    "ial18-physics": [f"{i:03d}" for i in range(1, 11)],
    "ial18-mathematics": [f"{i:03d}" for i in range(2, 63) if i != 38],
    "ial18-mathematics-extra": [f"{i:03d}" for i in range(1, 14)],
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=4, help="per subject")
    ap.add_argument("--seed", type=int, default=20261003)
    ap.add_argument("--out", default="tmp_sample_audit.txt")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    engine = create_engine(f"sqlite:///{DB}")
    lines: list[str] = []
    total = 0
    with Session(engine) as s:
        for slug, batches in SUBJECTS.items():
            qids: set[int] = set()
            for b in batches:
                p = REVIEW / slug / "decisions" / f"batch-{b}.jsonl"
                for line in open(p, encoding="utf-8"):
                    if line.strip():
                        qids.add(json.loads(line)["question_id"])
            pick = rng.sample(sorted(qids), min(args.n, len(qids)))
            for qid in pick:
                total += 1
                q = s.get(m.Question, qid)
                paper = s.get(m.Paper, q.paper_id)
                doc = s.get(m.Document, paper.document_id)
                subj = s.get(m.Subject, doc.subject_id) if doc.subject_id else None
                series = s.get(m.ExamSeries, doc.series_id) if doc.series_id else None
                tags = s.execute(
                    select(m.TaxonomyNode.code, m.TaxonomyNode.name,
                           m.QuestionTaxonomy.confidence, m.QuestionTaxonomy.assigned_by,
                           m.QuestionTaxonomy.reviewed)
                    .join(m.QuestionTaxonomy, m.QuestionTaxonomy.node_id == m.TaxonomyNode.id)
                    .where(m.QuestionTaxonomy.question_id == qid)
                    .order_by(m.TaxonomyNode.code)
                ).all()
                entries = s.execute(
                    select(m.MarkSchemeEntry.answer_text, m.MarkSchemeEntry.number_path,
                           m.MarkSchemeEntry.marks)
                    .where(m.MarkSchemeEntry.question_id == qid)
                ).all()
                answers = s.execute(
                    select(m.OfficialAnswer.content, m.OfficialAnswer.source)
                    .where(m.OfficialAnswer.question_id == qid)
                ).all()
                lines.append("=" * 100)
                lines.append(
                    f"[{total}] {slug} | {doc.paper_code} | year={doc.year} "
                    f"session={series.session if series else None} | qid={qid} "
                    f"| {q.number_path} | marks={q.marks} | kind={q.kind} depth={q.depth}"
                )
                lines.append(f"SUBJECT: {subj.code if subj else None} ({subj.title if subj else ''})")
                for code, name, conf, by, rev in tags:
                    lines.append(f"TAG: {code} | conf={conf} | by={by} | reviewed={rev}")
                    lines.append(f"     NAME: {name}")
                stem = " ".join((q.stem_text or "").split())
                lines.append(f"STEM: {stem[:700]}")
                for text, np, mk in entries[:3]:
                    txt = " ".join((text or "").split())
                    lines.append(f"MS[{np} marks={mk}]: {txt[:400]}")
                for content, source in answers[:2]:
                    txt = " ".join((content or "").split())
                    lines.append(f"ANS[{source}]: {txt[:300]}")
                lines.append("")
    out = ROOT / args.out
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"sampled {total} questions -> {out}")


if __name__ == "__main__":
    main()
