"""Apply full-pass Jev decisions (second classification) for all slugs.

Extends tmp_apply_920.py / apply_review semantics to questions that already
carry reviewed rows (first-pass outcomes):

- keep:
    - unreviewed algorithm rows present -> mark them reviewed=True ("kept")
    - none -> no-op ("confirmed": already reviewed, Jev agrees)
- change:
    - validate code in the points subject's point list (POINTS_SUBJECT) and
      unit match when the unit is resolvable
    - delete ALL taxonomy rows of the question (any source/assigned_by)
    - insert source="ai-review" / assigned_by="ai-review-v1" /
      confidence=1.0 / reviewed=True row
- drop: not produced by the full pass; reported as error if seen.

Scope check: the question must be part of the exported batch set.
Applied log: <decisions-root>/{slug}/applied.jsonl

Usage:
  python tmp_jev_full_apply.py --subject all            # dry run (validate only)
  python tmp_jev_full_apply.py --subject all --write    # apply + log
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from examdata.core import models as m
from examdata.tagging.assign import ASSIGNED_BY, REVIEW_ASSIGNED_BY, REVIEW_SOURCE
from examdata.tagging.corpus import load_points, unit_code_from_paper

ROOT = Path(__file__).resolve().parent
DB_URL = f"sqlite:///{ROOT / '.data' / 'examdata.db'}"

SLUGS = [
    'ial-accounting', 'ial-englang', 'ial-englit', 'ial-french', 'ial-geography',
    'ial-german', 'ial-greek', 'ial-history', 'ial-law', 'ial-maths',
    'ial-psychology', 'ial-spanish', 'ial18-biology', 'ial18-business',
    'ial18-chemistry', 'ial18-economics', 'ial18-it', 'ial18-mathematics',
    'ial18-mathematics-extra', 'ial18-physics',
]

POINTS_SUBJECT = {'ial18-mathematics-extra': 'ial18-mathematics'}
DECISIONS = {'keep', 'change', 'drop'}


def apply_slug(session: Session, slug: str, *, batch_root: Path, decisions_root: Path,
               write: bool) -> dict:
    points_slug = POINTS_SUBJECT.get(slug, slug)
    sub_row = session.execute(select(m.Subject).where(m.Subject.slug == points_slug)).scalar()
    if sub_row is None:
        print(f'[{slug}] ERROR subject {points_slug} not found')
        return {'slug': slug, 'error': 'subject not found'}
    keys = {(sub_row.code or '').strip().lower(), (sub_row.slug or '').strip().lower()}
    keys.discard('')
    points = [p for p in load_points(session) if (p.subject or '').strip().lower() in keys]
    point_by_code = {p.code: p for p in points}

    scope: set[int] = set()
    scope_unit: dict[int, str] = {}
    for bf in sorted((batch_root / slug / 'batches').glob('batch-*.jsonl')):
        for line in open(bf, encoding='utf-8'):
            if line.strip():
                item = json.loads(line)
                scope.add(item['question_id'])
                if item.get('unit_code'):
                    scope_unit[item['question_id']] = item['unit_code']
    if not scope:
        print(f'[{slug}] ERROR empty scope')
        return {'slug': slug, 'error': 'empty scope'}

    decisions: list[dict] = []
    for f in sorted((decisions_root / slug).glob('batch-*.jsonl')):
        for line in open(f, encoding='utf-8'):
            if line.strip():
                decisions.append(json.loads(line))

    stats = {'kept': 0, 'confirmed': 0, 'changed': 0, 'dropped': 0}
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

        question = session.get(m.Question, qid)
        if question is None:
            fail(row, 'question not found')
            continue
        paper = session.get(m.Paper, question.paper_id)
        document = session.get(m.Document, paper.document_id) if paper else None
        if paper is None or document is None:
            fail(row, 'paper/document missing')
            continue

        all_rows = list(session.scalars(select(m.QuestionTaxonomy).where(
            m.QuestionTaxonomy.question_id == qid,
        )))
        algo_rows = [r for r in all_rows
                     if r.assigned_by == ASSIGNED_BY and not r.reviewed]

        if decision == 'keep':
            if algo_rows:
                stats['kept'] += 1
                if write:
                    for link in algo_rows:
                        link.reviewed = True
                status = 'applied' if write else 'dry-run'
            else:
                if not all_rows:
                    fail(row, 'no taxonomy rows at all')
                    continue
                stats['confirmed'] += 1
                status = 'confirmed'
        elif decision == 'change':
            code = str(row.get('code') or '').strip()
            point = point_by_code.get(code)
            if point is None:
                fail(row, f'code {code!r} is not a point of this subject')
                continue
            fresh = unit_code_from_paper(paper.attrs, document.paper_code)
            subject_units = {p.unit_code for p in points}
            unit = fresh if fresh in subject_units else scope_unit.get(qid)
            if unit and point.unit_code and point.unit_code.upper() != unit.upper():
                fail(row, f'code {code} belongs to unit {point.unit_code}, question is in {unit}')
                continue
            stats['changed'] += 1
            if write:
                for link in all_rows:
                    session.delete(link)
                session.flush()
                session.add(m.QuestionTaxonomy(
                    question_id=qid,
                    node_id=point.node_id,
                    source=REVIEW_SOURCE,
                    confidence=1.0,
                    assigned_by=REVIEW_ASSIGNED_BY,
                    reviewed=True,
                ))
            status = 'applied' if write else 'dry-run'
        else:  # drop
            stats['dropped'] += 1
            if write:
                for link in all_rows:
                    session.delete(link)
            status = 'applied' if write else 'dry-run'

        applied.append({
            'question_id': qid,
            'decision': decision,
            'code': row.get('code'),
            'reason': row.get('reason'),
            'status': status,
        })

    if write:
        session.flush()
        session.commit()
        log_path = decisions_root / slug / 'applied.jsonl'
        with open(log_path, 'w', encoding='utf-8') as fh:
            for entry in applied:
                fh.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + '\n')

    print(f'[{slug}] decisions={len(decisions)} kept={stats["kept"]} '
          f'confirmed={stats["confirmed"]} changed={stats["changed"]} '
          f'dropped={stats["dropped"]} errors={len(errors)}')
    for e in errors[:20]:
        print('   ERROR', e)
    return {'slug': slug, 'decisions': len(decisions), **stats, 'errors': len(errors)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--subject', required=True, help="slug or 'all'")
    ap.add_argument('--write', action='store_true')
    ap.add_argument('--batch-root', default='tmp_jev_full_batches')
    ap.add_argument('--decisions-root', default='tmp_jev_full_decisions')
    args = ap.parse_args()

    slugs = SLUGS if args.subject == 'all' else [args.subject]
    batch_root = ROOT / args.batch_root
    decisions_root = ROOT / args.decisions_root

    eng = create_engine(DB_URL)
    session = Session(eng)
    summary = []
    for slug in slugs:
        try:
            summary.append(apply_slug(
                session, slug, batch_root=batch_root,
                decisions_root=decisions_root, write=args.write,
            ))
        except Exception as exc:
            session.rollback()
            print(f'[{slug}] EXCEPTION {type(exc).__name__}: {exc}')
            summary.append({'slug': slug, 'error': f'{type(exc).__name__}: {exc}'})

    dec = sum(x.get('decisions', 0) for x in summary)
    kept = sum(x.get('kept', 0) for x in summary)
    conf = sum(x.get('confirmed', 0) for x in summary)
    chg = sum(x.get('changed', 0) for x in summary)
    err = sum(x.get('errors', 0) for x in summary)
    errs = [x for x in summary if x.get('error')]
    print(f'TOTAL decisions={dec} kept={kept} confirmed={conf} changed={chg} '
          f'errors={err} subject_errors={len(errs)} mode={"WRITE" if args.write else "dry-run"}')
    for x in errs:
        print('  SUBJECT ERROR', x)


if __name__ == '__main__':
    main()
