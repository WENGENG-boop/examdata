"""r6 probe: current unreviewed questions (>=1 taxonomy row, 0 reviewed rows) in IAL scope.

Prints per (slug, doc, paper) breakdown with fresh unit resolution and existing tag units.
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
DB_URL = f'sqlite:///{ROOT / ".data" / "examdata.db"}'

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

    # questions with >=1 taxonomy row
    tagged = set(s.scalars(select(m.QuestionTaxonomy.question_id).distinct()))
    # questions with >=1 reviewed row
    reviewed = set(s.scalars(select(m.QuestionTaxonomy.question_id).distinct().where(m.QuestionTaxonomy.reviewed == 1)))
    target = tagged - reviewed
    print(f'tagged={len(tagged)} reviewed={len(reviewed)} unreviewed={len(target)}')

    rows = s.execute(
        select(
            m.Question.id, m.Question.number_label,
            m.Paper.id, m.Paper.attrs, m.Document.id, m.Document.paper_code, m.Document.title,
            m.Subject.slug,
        )
        .join(m.Paper, m.Paper.id == m.Question.paper_id)
        .join(m.Document, m.Document.id == m.Paper.document_id)
        .join(m.Subject, m.Subject.id == m.Document.subject_id)
        .where(m.Question.id.in_(target))
        .order_by(m.Question.id)
    ).all()

    # tag rows for those questions
    qids = [r[0] for r in rows]
    tag_rows = s.execute(
        select(m.QuestionTaxonomy.question_id, m.TaxonomyNode.code, m.QuestionTaxonomy.source,
               m.QuestionTaxonomy.assigned_by, m.QuestionTaxonomy.reviewed, m.QuestionTaxonomy.confidence)
        .where(m.QuestionTaxonomy.question_id.in_(qids))
    ).all()
    tags_by_q: dict[int, list] = defaultdict(list)
    for qid, code, source, by, rev, conf in tag_rows:
        tags_by_q[qid].append((code, source, by, rev, conf))

    by_slug: dict[str, list] = defaultdict(list)
    for qid, num, pid, pattrs, did, pcode, title, slug in rows:
        if slug not in IAL_SLUGS:
            print(f'  !! out-of-scope slug {slug} qid={qid}')
            continue
        fresh = unit_code_from_paper(pattrs, pcode)
        by_slug[slug].append((qid, num, pid, did, pcode, title, fresh))

    total = 0
    for slug in sorted(by_slug):
        items = by_slug[slug]
        total += len(items)
        print(f'== {slug}: {len(items)} unreviewed')
        per_paper = defaultdict(list)
        for it in items:
            per_paper[(it[3], it[2])].append(it)  # (doc, paper)
        for (did, pid), its in sorted(per_paper.items(), key=lambda kv: kv[0]):
            sample = its[0]
            _, _, _, _, pcode, title, fresh = sample
            units = Counter()
            ntag = Counter()
            for qid, *_ in its:
                for code, source, by, rev, conf in tags_by_q.get(qid, []):
                    u = (code or '').split('-', 1)[0]
                    units[u] += 1
                ntag[len(tags_by_q.get(qid, []))] += 1
            print(f'  doc {did} paper {pid} | pcode={pcode} | fresh={fresh!r} | {len(its)} q | '
                  f'tags={dict(units)} | rows_per_q={dict(ntag)}')
            print(f'    title: {title[:90]}')

    print(f'TOTAL unreviewed in IAL scope: {total}')


if __name__ == '__main__':
    main()
