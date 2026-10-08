"""Verify untagged-pass results for one subject: every batch qid has exactly one
reviewed ai-review taxonomy row.

Usage:
  python tmp_verify_subject_tags.py --slug ial18-it
  python tmp_verify_subject_tags.py --slug ial18-physics --batch-root tmp_jev_full_batches_r2
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from examdata.core import models as m
from examdata.tagging.assign import REVIEW_ASSIGNED_BY, REVIEW_SOURCE

ROOT = Path(__file__).resolve().parent
DB_URL = f"sqlite:///{ROOT / '.data' / 'examdata.db'}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--slug', required=True)
    ap.add_argument('--batch-root', default='tmp_jev_untagged_batches')
    args = ap.parse_args()

    batch_dir = ROOT / args.batch_root / args.slug / 'batches'
    files = sorted(glob.glob(str(batch_dir / 'batch-*.jsonl')))
    if not files:
        raise SystemExit(f'no batch files under {batch_dir}')
    qids: list[int] = []
    seen: set[int] = set()
    for f in files:
        for line in open(f, encoding='utf-8'):
            if line.strip():
                qid = json.loads(line)['question_id']
                if qid not in seen:
                    seen.add(qid)
                    qids.append(qid)

    eng = create_engine(DB_URL)
    with Session(eng) as s:
        bad: list[tuple] = []
        n_ok = 0
        papers: set[int] = set()
        total_marks = 0
        for qid in qids:
            q = s.get(m.Question, qid)
            if q is not None:
                papers.add(q.paper_id)
                total_marks += q.marks or 0
            rows = s.execute(
                select(m.QuestionTaxonomy, m.TaxonomyNode.code)
                .join(m.TaxonomyNode, m.QuestionTaxonomy.node_id == m.TaxonomyNode.id)
                .where(m.QuestionTaxonomy.question_id == qid)
            ).all()
            ok = (
                len(rows) == 1
                and rows[0][0].source == REVIEW_SOURCE
                and rows[0][0].assigned_by == REVIEW_ASSIGNED_BY
                and abs((rows[0][0].confidence or 0) - 1.0) < 1e-9
                and bool(rows[0][0].reviewed)
            )
            if ok:
                n_ok += 1
            else:
                bad.append((qid, [
                    (r[1], r[0].source, r[0].assigned_by, r[0].confidence, r[0].reviewed)
                    for r in rows
                ]))

    print(f'[{args.slug}] batch_qids={len(qids)} ok={n_ok} bad={len(bad)} '
          f'papers={len(papers)} marks={total_marks}')
    for qid, rows in bad[:25]:
        print('   BAD', qid, rows)
    if len(bad) > 25:
        print(f'   ... and {len(bad) - 25} more')
    raise SystemExit(1 if bad else 0)


if __name__ == '__main__':
    main()
