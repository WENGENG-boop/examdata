"""Completeness check: per subject x year coverage of parse + tagging (read-only).

Outputs:
- tmp_completeness.txt  (human-readable)
- tmp_completeness.json (machine summary)

Per subject (Edexcel IAL):
- spec points count (examdata corpus)
- QP / MS document counts
- QP with 0 questions (unparsed) + latest parse status
- questions total / tagged / untagged
- untagged reasons: unit-unresolved vs no-candidate; sample dump
- per-year: qp / questions / tagged
- MS entries count

Usage: python tmp_completeness.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from examdata.core import models as m
from examdata.tagging.corpus import load_points, unit_code_from_paper

ROOT = Path(__file__).resolve().parent
DB_URL = f"sqlite:///{ROOT / '.data' / 'examdata.db'}"

POINTS_SUBJECT = {'ial18-mathematics-extra': 'ial18-mathematics'}


def main() -> None:
    eng = create_engine(DB_URL)
    s = Session(eng)

    all_points = load_points(s)
    subjects = list(s.scalars(select(m.Subject).order_by(m.Subject.id)))
    out_lines: list[str] = []
    summary: dict = {}

    def w(line: str = '') -> None:
        out_lines.append(line)

    for sub in subjects:
        if sub.id < 5:  # skip Cambridge subjects (Edexcel IAL subjects start at id 5)
            continue
        slug = sub.slug or ''
        keys = {(sub.code or '').strip().lower(), slug.strip().lower()}
        keys.discard('')
        points = [p for p in all_points if (p.subject or '').strip().lower() in keys]
        by_unit: dict[str, set[str]] = {}
        for p in points:
            by_unit.setdefault(p.unit_code, set()).add(p.code)

        docs = list(s.scalars(select(m.Document).where(m.Document.subject_id == sub.id)))
        qp_docs = [d for d in docs if d.doc_type == 'question_paper']
        ms_docs = [d for d in docs if d.doc_type == 'mark_scheme']

        # questions per QP doc
        q_total = q_tagged = 0
        unparsed: list[tuple] = []
        per_year: dict = defaultdict(lambda: {'qp': 0, 'q': 0, 'tagged': 0})
        untagged_samples: list[str] = []
        untagged_reason: Counter = Counter()
        papers_with_untagged: list[tuple] = []
        for d in qp_docs:
            papers = list(s.scalars(select(m.Paper).where(m.Paper.document_id == d.id)))
            qs: list = []
            for p in papers:
                qs.extend(s.scalars(select(m.Question).where(m.Question.paper_id == p.id)))
            y = d.year
            per_year[y]['qp'] += 1
            if not qs:
                rev = s.execute(
                    select(m.DocumentRevision.parse_status, m.DocumentRevision.parse_error)
                    .where(m.DocumentRevision.document_id == d.id)
                    .order_by(m.DocumentRevision.revision_no.desc()).limit(1)
                ).first()
                unparsed.append((d.id, d.paper_code, y, rev[0] if rev else None,
                                 (rev[1] or '')[:80] if rev else None))
                continue
            untagged_here = 0
            for q in qs:
                q_total += 1
                per_year[y]['q'] += 1
                has_tag = s.execute(
                    select(m.QuestionTaxonomy.id)
                    .where(m.QuestionTaxonomy.question_id == q.id).limit(1)
                ).first()
                if has_tag:
                    q_tagged += 1
                    per_year[y]['tagged'] += 1
                else:
                    untagged_here += 1
                    paper_obj = s.get(m.Paper, q.paper_id)
                    doc_obj = s.get(m.Document, paper_obj.document_id) if paper_obj else None
                    unit = unit_code_from_paper(
                        paper_obj.attrs if paper_obj else None,
                        doc_obj.paper_code if doc_obj else None,
                    )
                    if unit and unit in by_unit:
                        reason = 'unit-ok-no-candidate'
                    elif unit:
                        reason = f'unit-{unit}-not-in-spec'
                    else:
                        reason = 'unit-unresolved'
                    untagged_reason[reason] += 1
                    if len(untagged_samples) < 5:
                        stem = ' '.join((q.stem_text or '').split())[:70]
                        untagged_samples.append(
                            f'    qid={q.id} {d.paper_code} y={y} {q.number_path} '
                            f'kind={q.kind} depth={q.depth} unit={unit} | {stem}'
                        )
            if untagged_here:
                papers_with_untagged.append((d.paper_code, y, len(qs), untagged_here))

        ms_entries = 0
        for d in ms_docs:
            mss = list(s.scalars(select(m.MarkScheme).where(m.MarkScheme.document_id == d.id)))
            for ms in mss:
                ms_entries += s.execute(
                    select(m.MarkSchemeEntry.id).where(m.MarkSchemeEntry.mark_scheme_id == ms.id)
                ).all().__len__()

        w('=' * 100)
        w(f'[{sub.id}] {slug} | {sub.title}')
        w(f'  spec points: {len(points)}  units: {len(by_unit)}')
        w(f'  documents: QP={len(qp_docs)} MS={len(ms_docs)} other={len(docs) - len(qp_docs) - len(ms_docs)}')
        w(f'  questions: total={q_total} tagged={q_tagged} untagged={q_total - q_tagged}')
        if unparsed:
            w(f'  QP with 0 questions: {len(unparsed)}')
            for did, pcode, y, status, err in unparsed[:10]:
                w(f'    doc {did} {pcode} y={y} status={status} err={err}')
        if untagged_reason:
            w(f'  untagged reasons: {dict(untagged_reason)}')
            w(f'  untagged samples:')
            for line in untagged_samples:
                w(line)
        if papers_with_untagged:
            w(f'  papers with untagged>0: {len(papers_with_untagged)}')
            for pcode, y, nq, nu in papers_with_untagged[:10]:
                w(f'    {pcode} y={y} q={nq} untagged={nu}')
        w(f'  MS entries: {ms_entries}')
        w('  per-year (year: qp / questions / tagged):')
        for y in sorted(per_year, key=lambda x: (x is None, x)):
            v = per_year[y]
            w(f'    {y}: {v["qp"]} / {v["q"]} / {v["tagged"]}')
        summary[slug] = {
            'subject_id': sub.id,
            'points': len(points),
            'units': len(by_unit),
            'qp_docs': len(qp_docs),
            'ms_docs': len(ms_docs),
            'questions': q_total,
            'tagged': q_tagged,
            'untagged': q_total - q_tagged,
            'unparsed_qp': len(unparsed),
            'untagged_reasons': dict(untagged_reason),
            'per_year': {str(k): v for k, v in per_year.items()},
            'ms_entries': ms_entries,
        }

    (ROOT / 'tmp_completeness.txt').write_text('\n'.join(out_lines) + '\n', encoding='utf-8')
    (ROOT / 'tmp_completeness.json').write_text(
        json.dumps(summary, ensure_ascii=False, indent=1, sort_keys=True) + '\n',
        encoding='utf-8',
    )
    print('written tmp_completeness.txt / tmp_completeness.json')
    tot_q = sum(v['questions'] for v in summary.values())
    tot_t = sum(v['tagged'] for v in summary.values())
    print(f'subjects={len(summary)} questions={tot_q} tagged={tot_t} untagged={tot_q - tot_t}')


if __name__ == '__main__':
    main()
