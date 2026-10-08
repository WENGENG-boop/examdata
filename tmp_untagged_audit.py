"""Sample audit of the untagged-question Jev pass (read-only).

Draws N random questions per slug from tmp_jev_untagged_decisions/{slug}/batch-*.jsonl
and dumps: decision + reason, final DB tags, stem, MS entries, official answers.
For manual/LLM review of classification correctness on the newly tagged set.

Usage:
  python tmp_untagged_audit.py                 # 2 per slug
  python tmp_untagged_audit.py --n 3 --seed 7
Output: tmp_untagged_audit.txt
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from examdata.core import models as m

ROOT = Path(__file__).resolve().parent
DB = ROOT / ".data" / "examdata.db"
DEC_ROOT = ROOT / "tmp_jev_untagged_decisions"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=2, help="per slug")
    ap.add_argument("--seed", type=int, default=20261004)
    ap.add_argument("--out", default="tmp_untagged_audit.txt")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    engine = create_engine(f"sqlite:///{DB}")
    lines: list[str] = []
    total = 0
    with Session(engine) as s:
        for slug_dir in sorted(p for p in DEC_ROOT.iterdir() if p.is_dir()):
            slug = slug_dir.name
            # collect all decisions for the slug
            rows: list[dict] = []
            for f in sorted((DEC_ROOT / slug).glob("batch-*.jsonl")):
                for line in open(f, encoding="utf-8"):
                    if line.strip():
                        rows.append(json.loads(line))
            if not rows:
                continue
            pick = rng.sample(rows, min(args.n, len(rows)))
            for row in pick:
                qid = row["question_id"]
                total += 1
                q = s.get(m.Question, qid)
                if q is None:
                    lines.append(f"[{total}] {slug} qid={qid} MISSING QUESTION")
                    continue
                paper = s.get(m.Paper, q.paper_id)
                doc = s.get(m.Document, paper.document_id) if paper else None
                subj = s.get(m.Subject, doc.subject_id) if doc and doc.subject_id else None
                series = s.get(m.ExamSeries, doc.series_id) if doc and doc.series_id else None
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
                    f"[{total}] {slug} | {doc.paper_code if doc else '?'} | "
                    f"year={doc.year if doc else '?'} "
                    f"session={series.session if series else None} | qid={qid} "
                    f"| {q.number_path} | marks={q.marks} | kind={q.kind} depth={q.depth}"
                )
                lines.append(
                    f"DECISION: {row.get('decision')} code={row.get('code')} | "
                    f"{row.get('reason')}"
                )
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
