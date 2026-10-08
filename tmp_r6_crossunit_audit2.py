"""audit2: refined cross-unit label audit for Edexcel IAL (read-only).

Difference vs audit1: resolves the *document's* unit with the same cascade as
the r6 export (fresh -> title -> german -> alias -> pcode alias), restricted to
globally valid unit codes (all IAL points, so ial18-mathematics-extra questions
under subject ial-maths are covered too). Falls back to a unique (or >=80%
majority) node-unit vote, flagged as low confidence. Only then compares every
attached taxonomy row's point unit against the doc unit.

Artifacts from audit1 (paper_code='question-paper' -> 'QUESTION') are filtered
because such candidates are not valid unit codes.

Outputs:
- tmp_r6_crossunit_audit2.jsonl            (true mismatch candidates)
- tmp_r6_crossunit_audit2_unresolved.jsonl (docs whose unit could not be resolved)
"""
from __future__ import annotations

import json
import re
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
OUT = ROOT / 'tmp_r6_crossunit_audit2.jsonl'
OUT_UNRES = ROOT / 'tmp_r6_crossunit_audit2_unresolved.jsonl'

IAL_SLUGS = {
    'ial-accounting', 'ial-arabic', 'ial-englang', 'ial-englit', 'ial-french',
    'ial-geography', 'ial-german', 'ial-greek', 'ial-history', 'ial-law',
    'ial-maths', 'ial-psychology', 'ial-spanish', 'ial18-biology', 'ial18-business',
    'ial18-chemistry', 'ial18-economics', 'ial18-it', 'ial18-mathematics',
    'ial18-physics', 'ial26-computer-science',
}

TITLE_RE = re.compile(r'\(([A-Z]{2,4}\d{2,3})\)')
GERMAN_UNIT1_RE = re.compile(r'Unit\s*1\b', re.I)
UNIT_ALIAS = {'6663A': 'WMA01', '6664A': 'WMA01', '6665A': 'WMA02',
              '6666A': 'WMA02', '6667A': 'WFM01'}
PCODE_ALIAS = {'yla1-01': 'YLA1-01', 'yla1-02': 'YLA1-02'}


def main() -> None:
    eng = create_engine(DB_URL)
    s = Session(eng)

    points = load_points(s)
    point_by_node = {p.node_id: p for p in points}
    all_units = {p.unit_code.upper() for p in points if p.unit_code}

    subjects = list(s.scalars(select(m.Subject)))
    subjects_by_slug = {sub.slug: sub for sub in subjects}

    out_records: list[dict] = []
    unres_records: list[dict] = []
    grand_rows = 0
    grand_mismatch = 0
    grand_missing = 0
    method_total: Counter = Counter()

    for slug in sorted(IAL_SLUGS):
        sub = subjects_by_slug.get(slug)
        if sub is None:
            print(f'[{slug}] subject missing')
            continue
        docs = list(s.scalars(select(m.Document).where(m.Document.subject_id == sub.id)))
        if not docs:
            continue
        doc_by_id = {d.id: d for d in docs}
        papers = list(s.scalars(select(m.Paper).where(m.Paper.document_id.in_(list(doc_by_id)))))
        paper_by_id = {p.id: p for p in papers}
        papers_by_doc: dict[int, list] = defaultdict(list)
        for p in papers:
            papers_by_doc[p.document_id].append(p)
        questions = list(s.scalars(select(m.Question).where(
            m.Question.paper_id.in_(list(paper_by_id)))))
        qs_by_doc: dict[int, list] = defaultdict(list)
        for q in questions:
            pap = paper_by_id[q.paper_id]
            qs_by_doc[pap.document_id].append(q)
        tax = list(s.scalars(select(m.QuestionTaxonomy).where(
            m.QuestionTaxonomy.question_id.in_([q.id for q in questions]))))
        rows_by_q: dict[int, list] = defaultdict(list)
        for r in tax:
            rows_by_q[r.question_id].append(r)

        def resolve_doc_unit(doc, plist, qs):
            fresh = None
            for p in plist:
                f = unit_code_from_paper(p.attrs, doc.paper_code)
                if f:
                    fresh = f
                    break
            if fresh and fresh.upper() in all_units:
                return fresh.upper(), 'fresh'
            mm = TITLE_RE.search(doc.title or '')
            if mm and mm.group(1).upper() in all_units:
                return mm.group(1).upper(), 'title'
            if slug == 'ial-german' and GERMAN_UNIT1_RE.search(doc.title or '') \
                    and 'WGN01' in all_units:
                return 'WGN01', 'german-unit1'
            if fresh:
                alias = UNIT_ALIAS.get(fresh)
                if alias and alias in all_units:
                    return alias, 'unit-alias'
            alias = PCODE_ALIAS.get((doc.paper_code or '').lower())
            if alias and alias in all_units:
                return alias, 'pcode-alias'
            votes = Counter()
            for q in qs:
                for r in rows_by_q.get(q.id, []):
                    p = point_by_node.get(r.node_id)
                    if p and p.unit_code:
                        votes[p.unit_code.upper()] += 1
            if len(votes) == 1:
                return next(iter(votes)), 'node-vote'
            if votes:
                top = votes.most_common(2)
                tot = sum(votes.values())
                if top[0][1] >= 3 and top[0][1] / tot >= 0.8:
                    return top[0][0], 'node-vote-majority'
            return None, ('unresolved:' + ','.join(f'{k}={v}' for k, v in votes.most_common(4))
                          if votes else 'unresolved:no-rows')

        sub_rows = 0
        sub_mism = 0
        sub_docs = 0
        sub_unres = 0
        for doc in docs:
            plist = papers_by_doc.get(doc.id, [])
            if not plist:
                continue
            sub_docs += 1
            qs = qs_by_doc.get(doc.id, [])
            doc_unit, method = resolve_doc_unit(doc, plist, qs)
            method_total[method] += 1
            if doc_unit is None:
                sub_unres += 1
                unres_records.append({
                    'subject': slug, 'doc_id': doc.id, 'title': doc.title,
                    'paper_code': doc.paper_code, 'reason': method,
                    'questions': len(qs),
                })
                continue
            for q in qs:
                for r in rows_by_q.get(q.id, []):
                    p = point_by_node.get(r.node_id)
                    if p is None:
                        grand_missing += 1
                        continue
                    sub_rows += 1
                    if (p.unit_code or '').upper() != doc_unit:
                        sub_mism += 1
                        out_records.append({
                            'subject': slug, 'doc_id': doc.id, 'doc_title': doc.title,
                            'paper_code': doc.paper_code, 'method': method,
                            'doc_unit': doc_unit, 'question_id': q.id,
                            'number': q.number_label, 'label_code': p.code,
                            'label_unit': p.unit_code, 'reviewed': bool(r.reviewed),
                            'assigned_by': r.assigned_by, 'confidence': r.confidence,
                        })
        grand_rows += sub_rows
        grand_mismatch += sub_mism
        if sub_mism or sub_unres:
            print(f'[{slug}] docs={sub_docs} rows={sub_rows} mismatches={sub_mism} unresolved_docs={sub_unres}')
        else:
            print(f'[{slug}] docs={sub_docs} rows={sub_rows} mismatches=0')

    with open(OUT, 'w', encoding='utf-8') as fh:
        for rec in out_records:
            fh.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + '\n')
    with open(OUT_UNRES, 'w', encoding='utf-8') as fh:
        for rec in unres_records:
            fh.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + '\n')

    print(f'TOTAL rows={grand_rows} mismatches={grand_mismatch} '
          f'missing_points={grand_missing} unresolved_docs={len(unres_records)}')
    print('doc resolution methods:', dict(method_total))
    if out_records:
        print('--- mismatch sample:')
        for rec in out_records[:20]:
            print('  ', rec)
    if unres_records:
        print('--- unresolved docs:')
        for rec in unres_records[:30]:
            print('  ', rec)


if __name__ == '__main__':
    main()
