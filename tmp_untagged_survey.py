"""Survey of untagged questions (zero taxonomy rows) in IAL scope (read-only).

Prints, per slug: count; then per (slug, fresh_unit, paper_code, doc title) groups
so we can design unit resolution for the Jev direct pass.
"""
from __future__ import annotations

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

IAL_SLUGS = {
    'ial-accounting', 'ial-arabic', 'ial-englang', 'ial-englit', 'ial-french',
    'ial-geography', 'ial-german', 'ial-greek', 'ial-history', 'ial-law',
    'ial-maths', 'ial-psychology', 'ial-spanish', 'ial18-biology', 'ial18-business',
    'ial18-chemistry', 'ial18-economics', 'ial18-it', 'ial18-mathematics',
    'ial18-physics', 'ial26-computer-science',
}


def main() -> None:
    eng = create_engine(DB_URL)
    s = Session(eng)

    # sanity: distinct assigned_by values
    ab = s.execute(
        select(m.QuestionTaxonomy.assigned_by, m.QuestionTaxonomy.id)
    ).all()
    print('assigned_by counter:', dict(Counter(r[0] for r in ab)))

    tagged_ids = set(s.scalars(select(m.QuestionTaxonomy.question_id).distinct()))
    print('questions with >=1 taxonomy row:', len(tagged_ids))

    all_points = load_points(s)
    by_subj: dict[str, set[str]] = defaultdict(set)
    for p in all_points:
        by_subj[(p.subject or '').strip().lower()].add(p.unit_code)

    rows = s.execute(
        select(
            m.Question.id, m.Question.number_label, m.Question.kind, m.Question.marks,
            m.Paper.attrs, m.Document.paper_code, m.Document.title, m.Document.year,
            m.Document.doc_type, m.Subject.slug, m.Subject.id, m.Document.id,
            m.Paper.id,
        )
        .join(m.Paper, m.Paper.id == m.Question.paper_id)
        .join(m.Document, m.Document.id == m.Paper.document_id)
        .join(m.Subject, m.Subject.id == m.Document.subject_id)
    ).all()

    per_slug: Counter = Counter()
    groups: dict[tuple, list] = defaultdict(list)
    doc_info: dict[int, dict] = {}
    untagged_rows = []
    for (qid, num, kind, marks, attrs, pcode, title, year, dtype, slug, sid, did, pid) in rows:
        if qid in tagged_ids:
            continue
        if slug not in IAL_SLUGS:
            continue
        fresh = unit_code_from_paper(attrs, pcode)
        per_slug[slug] += 1
        untagged_rows.append((qid, slug, fresh, pcode, title, year, num, kind))
        groups[(slug, fresh, pcode, (title or '')[:70])].append(qid)
        if did not in doc_info:
            doc_info[did] = {
                'slug': slug, 'title': title, 'year': year, 'dtype': dtype,
                'papers': {}, 'n': 0,
            }
        di = doc_info[did]
        di['n'] += 1
        di['papers'].setdefault(pid, {'pcode': pcode, 'attrs_unit': (attrs or {}).get('unit_code') if isinstance(attrs, dict) else None, 'n': 0})
        di['papers'][pid]['n'] += 1

    print('\n=== untagged per slug ===')
    for slug, n in per_slug.most_common():
        own = len(by_subj.get(slug, ()))
        print(f'  {slug}: {n}  (own units={sorted(by_subj.get(slug, ()))})')

    print('\n=== groups (slug, fresh, paper_code, title) ===')
    for key in sorted(groups, key=lambda k: (-len(groups[k]), k)):
        slug, fresh, pcode, title = key
        ids = groups[key]
        print(f'  {len(ids):5d}  {slug}  fresh={fresh!r}  pcode={pcode!r}  {title!r}')

    print('\n=== docs with untagged (n>=1), sorted by n ===')
    for did, di in sorted(doc_info.items(), key=lambda kv: -kv[1]['n']):
        papers = '; '.join(
            f"pid={pid} {p['pcode']!r} attrs_unit={p['attrs_unit']!r} n={p['n']}"
            for pid, p in di['papers'].items())
        print(f"  doc {did} {di['slug']} y={di['year']} n={di['n']} {di['title']!r}")
        print(f"      {papers}")

    print('\n=== sample untagged questions (first 40) ===')
    for qid, slug, fresh, pcode, title, year, num, kind in untagged_rows[:40]:
        print(f'  qid={qid} {slug} fresh={fresh!r} {pcode!r} y={year} num={num!r} kind={kind} {title[:50]!r}')


if __name__ == '__main__':
    main()
