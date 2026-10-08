"""Apply Jev review decisions for the 920 legacy shared-unit rows.

One-off script. Replicates the semantics of examdata.tagging.review.apply_review
for the ``ial18-mathematics-extra`` batch set, with exactly one deliberate
difference: the per-row scope check.

``apply_review`` requires ``document.subject_id == subject_row.id``. These 637
questions live on documents with ``subject_id=16`` (ial-maths legacy) while their
taxonomy nodes belong to ``ial18-mathematics`` (the shared unit codes WST/WME/WFM01-03
were overwritten by the later spec load), so neither subject's export/apply can
reach them. The scope check here is instead: the question must be part of the
exported ``ial18-mathematics-extra`` batch set (the 637 qids) - exactly the set
of questions this run is entitled to resolve.

Everything else matches apply_review: keep -> mark unreviewed algorithm rows
reviewed; change -> validate code in ial18 points + unit match, delete algorithm
rows, insert source="ai-review" / assigned_by="ai-review-v1" / confidence=1.0 /
reviewed=True row if (qid, node_id) not already present; drop -> delete rows.
The applied log is written to review-export/ial18-mathematics-extra/applied.jsonl.

Usage:
  python tmp_apply_920.py            # dry run: validate only, no DB writes, no log
  python tmp_apply_920.py --write    # apply and log
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, r'C:/Users/weo/Desktop/api/examdata')
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from examdata.core import models as m
from examdata.tagging.assign import ASSIGNED_BY, REVIEW_ASSIGNED_BY, REVIEW_SOURCE
from examdata.tagging.corpus import load_points, unit_code_from_paper

ROOT = Path(r'C:/Users/weo/Desktop/api/examdata')
DB_URL = f"sqlite:///{ROOT / '.data' / 'examdata.db'}"
REVIEW = ROOT / '.data' / 'tagging' / 'review-export'
SLUG = 'ial18-mathematics-extra'
POINTS_SLUG = 'ial18-mathematics'
DECISIONS = {'keep', 'change', 'drop'}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()
    dry_run = not args.write

    eng = create_engine(DB_URL)
    s = Session(eng)

    scope: set[int] = set()
    for f in sorted((REVIEW / SLUG / 'batches').glob('batch-*.jsonl')):
        for line in f.read_text(encoding='utf-8').splitlines():
            if line.strip():
                scope.add(json.loads(line)['question_id'])
    print(f'scope: {len(scope)} questions')

    sub_row = s.execute(select(m.Subject).where(m.Subject.slug == POINTS_SLUG)).scalar()
    keys = {(sub_row.code or '').strip().lower(), (sub_row.slug or '').strip().lower()}
    keys.discard('')
    points = [p for p in load_points(s) if (p.subject or '').strip().lower() in keys]
    point_by_code = {p.code: p for p in points}
    print(f'points: {len(points)}')

    decisions: list[dict] = []
    for f in sorted((REVIEW / SLUG / 'decisions').glob('batch-*.jsonl')):
        for line in f.read_text(encoding='utf-8').splitlines():
            if line.strip():
                decisions.append(json.loads(line))
    print(f'decisions: {len(decisions)}')

    stats = {'kept': 0, 'changed': 0, 'dropped': 0}
    errors: list[str] = []
    applied: list[dict] = []
    seen: set[int] = set()

    def fail(row: dict, message: str) -> None:
        errors.append(f"question {row.get('question_id')}: {message}")
        applied.append({
            'question_id': row.get('question_id'),
            'decision': row.get('decision'),
            'code': row.get('code'),
            'reason': row.get('reason'),
            'status': 'error',
            'message': message,
        })

    for row in decisions:
        qid = row.get('question_id')
        decision = str(row.get('decision') or '').strip().lower()
        if not isinstance(qid, int):
            fail(row, 'question_id must be an integer')
            continue
        if qid in seen:
            fail(row, 'duplicate decision for this question')
            continue
        seen.add(qid)
        if decision not in DECISIONS:
            fail(row, f'unknown decision {decision!r}')
            continue
        if qid not in scope:
            fail(row, 'question is not part of the exported batch scope')
            continue

        question = s.get(m.Question, qid)
        if question is None:
            fail(row, 'question not found')
            continue
        paper = s.get(m.Paper, question.paper_id)
        document = s.get(m.Document, paper.document_id) if paper else None
        if paper is None or document is None:
            fail(row, 'paper/document missing')
            continue

        algo_rows = list(s.scalars(select(m.QuestionTaxonomy).where(
            m.QuestionTaxonomy.question_id == qid,
            m.QuestionTaxonomy.assigned_by == ASSIGNED_BY,
            m.QuestionTaxonomy.reviewed.is_(False),
        )))
        if not algo_rows:
            fail(row, 'no unreviewed algorithm tags to act on')
            continue

        if decision == 'keep':
            stats['kept'] += 1
            if not dry_run:
                for link in algo_rows:
                    link.reviewed = True
        elif decision == 'change':
            code = str(row.get('code') or '').strip()
            point = point_by_code.get(code)
            if point is None:
                fail(row, f'code {code!r} is not a point of this subject')
                continue
            unit = unit_code_from_paper(paper.attrs, document.paper_code)
            if unit and point.unit_code and point.unit_code.upper() != unit.upper():
                fail(row, f'code {code} belongs to unit {point.unit_code}, question is in {unit}')
                continue
            stats['changed'] += 1
            if not dry_run:
                for link in algo_rows:
                    s.delete(link)
                s.flush()
                existing = s.scalar(select(m.QuestionTaxonomy.id).where(
                    m.QuestionTaxonomy.question_id == qid,
                    m.QuestionTaxonomy.node_id == point.node_id,
                ))
                if existing is None:
                    s.add(m.QuestionTaxonomy(
                        question_id=qid,
                        node_id=point.node_id,
                        source=REVIEW_SOURCE,
                        confidence=1.0,
                        assigned_by=REVIEW_ASSIGNED_BY,
                        reviewed=True,
                    ))
        else:  # drop
            stats['dropped'] += 1
            if not dry_run:
                for link in algo_rows:
                    s.delete(link)

        applied.append({
            'question_id': qid,
            'decision': decision,
            'code': row.get('code'),
            'reason': row.get('reason'),
            'status': 'applied' if not dry_run else 'dry-run',
        })

    print(f"dry_run={dry_run} kept={stats['kept']} changed={stats['changed']} "
          f"dropped={stats['dropped']} errors={len(errors)}")
    for e in errors[:30]:
        print('  ERROR', e)

    if not dry_run:
        s.flush()
        s.commit()
        log_path = REVIEW / SLUG / 'applied.jsonl'
        with open(log_path, 'w', encoding='utf-8') as fh:
            for entry in applied:
                fh.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + '\n')
        print(f'log -> {log_path}')


if __name__ == '__main__':
    main()
