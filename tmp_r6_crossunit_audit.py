"""Cross-unit label audit for Edexcel IAL (read-only).

For every IAL question, resolve the paper's unit via
unit_code_from_paper(paper.attrs, document.paper_code) and compare with the
unit of each attached taxonomy point (via load_points node_id -> unit_code).
Report rows whose point unit differs from the resolved paper unit.

Outputs:
- tmp_r6_crossunit_audit.jsonl  (one record per mismatching row)
- stdout summary per subject

Usage:
  ./.venv/Scripts/python.exe -X utf8 tmp_r6_crossunit_audit.py
  ./.venv/Scripts/python.exe -X utf8 tmp_r6_crossunit_audit.py --only-reviewed
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from examdata.core import models as m
from examdata.tagging.corpus import load_points, unit_code_from_paper

ROOT = Path(__file__).resolve().parent
DB_URL = f"sqlite:///{ROOT / '.data' / 'examdata.db'}"
OUT = ROOT / 'tmp_r6_crossunit_audit.jsonl'


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--only-reviewed', action='store_true',
                    help='only report rows with reviewed=1')
    args = ap.parse_args()

    eng = create_engine(DB_URL)
    s = Session(eng)

    all_points = load_points(s)
    subjects = list(s.scalars(select(m.Subject).order_by(m.Subject.id)))
    total_rows = 0
    total_mismatch = 0
    out_records: list[dict] = []

    for sub in subjects:
        if sub.id < 5:
            continue
        keys = {(sub.code or '').strip().lower(), (sub.slug or '').strip().lower()}
        keys.discard('')
        points = [p for p in all_points if (p.subject or '').strip().lower() in keys]
        if not points:
            continue
        point_by_node = {p.node_id: p for p in points}
        docs = list(s.scalars(select(m.Document).where(m.Document.subject_id == sub.id)))
        doc_ids = [d.id for d in docs]
        if not doc_ids:
            continue
        papers = list(s.scalars(select(m.Paper).where(m.Paper.document_id.in_(doc_ids))))
        paper_by_id = {p.id: p for p in papers}
        doc_by_id = {d.id: d for d in docs}
        if not paper_by_id:
            continue
        questions = list(s.scalars(select(m.Question).where(
            m.Question.paper_id.in_(list(paper_by_id)))))
        q_by_id = {q.id: q for q in questions}
        if not q_by_id:
            continue
        tax = list(s.scalars(select(m.QuestionTaxonomy).where(
            m.QuestionTaxonomy.question_id.in_(list(q_by_id)))))
        mism = Counter()
        sub_rows = 0
        for row in tax:
            p = point_by_node.get(row.node_id)
            if p is None:
                continue
            q = q_by_id[row.question_id]
            paper = paper_by_id[q.paper_id]
            doc = doc_by_id.get(paper.document_id)
            resolved = unit_code_from_paper(paper.attrs, doc.paper_code if doc else None)
            if not resolved or not p.unit_code:
                continue
            sub_rows += 1
            if args.only_reviewed and not row.reviewed:
                continue
            if p.unit_code.upper() != resolved.upper():
                mism[(resolved, p.unit_code)] += 1
                total_mismatch += 1
                out_records.append({
                    'subject': sub.slug,
                    'question_id': q.id,
                    'paper_code': doc.paper_code if doc else None,
                    'number': q.number_label,
                    'resolved_unit': resolved,
                    'label_code': p.code,
                    'label_unit': p.unit_code,
                    'reviewed': bool(row.reviewed),
                    'assigned_by': row.assigned_by,
                })
        total_rows += sub_rows
        if mism:
            print(f'[{sub.slug}] rows={sub_rows} mismatches={sum(mism.values())} '
                  f'top={mism.most_common(6)}')
        else:
            print(f'[{sub.slug}] rows={sub_rows} mismatches=0')

    with open(OUT, 'w', encoding='utf-8') as fh:
        for rec in out_records:
            fh.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + '\n')
    print(f'TOTAL rows={total_rows} mismatches={total_mismatch} -> {OUT.name}')
    if out_records:
        print('sample:')
        for rec in out_records[:15]:
            print('  ', rec)


if __name__ == '__main__':
    main()
