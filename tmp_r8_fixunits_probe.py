"""probe: inspect the 24 cross-unit questions (doc 1752/1754/3106/3122/3123/3143)
and run unit-restricted BM25 for the 17 that will end up with 0 rows.

Read-only. Prints stems + candidates for manual judgement.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'src'))
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from examdata.core import models as m
from examdata.tagging.assign import rank_question
from examdata.tagging.corpus import CorpusSet, QuestionRef, load_points

ROOT = Path(__file__).resolve().parent
DB_URL = f"sqlite:///{ROOT / '.data' / 'examdata.db'}"

# question_id -> forced unit (doc truth)
FORCED = {
    68437: 'WAC11', 68438: 'WAC11', 68441: 'WAC11', 68443: 'WAC11', 68444: 'WAC11',
    68445: 'WAC11', 68446: 'WAC11', 68448: 'WAC11', 68449: 'WAC11', 68450: 'WAC11',
    68453: 'WAC01', 68456: 'WAC01', 68457: 'WAC01', 68458: 'WAC01',
    68517: 'YLA1-01', 68520: 'YLA1-01', 68525: 'YLA1-02',
}
KEEP_ONLY = [68429, 68430, 68440, 68442, 68454, 68455, 68531]


def main() -> None:
    eng = create_engine(DB_URL)
    s = Session(eng)
    points = load_points(s, board_key='edexcel')
    corpora = CorpusSet(points)

    all_qids = sorted(set(FORCED) | set(KEEP_ONLY))
    stmt = (
        select(
            m.Question.id, m.Question.number_label, m.Question.stem_text,
            m.Document.paper_code, m.Paper.attrs,
            m.Subject.code, m.Subject.slug, m.Document.id,
        )
        .join(m.Paper, m.Paper.id == m.Question.paper_id)
        .join(m.Document, m.Document.id == m.Paper.document_id)
        .join(m.Subject, m.Subject.id == m.Document.subject_id, isouter=True)
        .where(m.Question.id.in_(all_qids))
        .order_by(m.Document.id, m.Question.display_order, m.Question.id)
    )
    for qid, num, stem, pcode, attrs, scode, sslug, did in s.execute(stmt):
        stem = (stem or '').replace('\n', ' ')
        print(f'== q{qid} doc{did} [{num}] {sslug} pcode={pcode} unit={FORCED.get(qid, "KEEP")}')
        print(f'   stem: {stem[:360]}')
        if qid in FORCED:
            ref = QuestionRef(
                question_id=qid, number_label=num or '', stem_text=stem,
                paper_code=pcode, subject_code=scode, subject_slug=sslug,
                unit_code=FORCED[qid],
            )
            subject, cands = rank_question(corpora, ref)
            print(f'   subject={subject}')
            for c in cands[:6]:
                print(f'     {c.score:.3f} conf={c.confidence:.3f} {c.code}  {c.name[:70]}')
        print()
    s.close()


if __name__ == '__main__':
    main()
