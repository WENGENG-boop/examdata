"""Classify Edexcel zero-answer-resolution papers (why 0% resolvable)."""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from examdata.core import models as m
from examdata.query import service
from examdata.query.service import AnswerEntry

ROOT = Path(__file__).resolve().parent
DB = ROOT / '.data' / 'examdata.db'
eng = create_engine(f'sqlite:///{DB}')

out: list[str] = []


def p(*args) -> None:
    line = ' '.join(str(a) for a in args)
    out.append(line)
    print(line)


def chunked(seq, n=500):
    seq = list(seq)
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


with Session(eng) as s:
    ed_subj = {r[0]: r[1] for r in s.execute(
        select(m.Subject.id, m.Subject.code).where(m.Subject.code.like('ial%'))).all()}
    papers = s.execute(
        select(m.Paper.id, m.Paper.document_id, m.Document.subject_id,
               m.Document.paper_code, m.Document.year)
        .join(m.Document, m.Document.id == m.Paper.document_id)
        .where(m.Document.subject_id.in_(ed_subj.keys()))).all()
    paper_ids = [r[0] for r in papers]
    qrows = []
    for part in chunked(paper_ids):
        qrows += s.execute(select(m.Question.id, m.Question.paper_id, m.Question.number_path)
                           .where(m.Question.paper_id.in_(part))).all()
    doc_ids = sorted({r[1] for r in papers})
    ms_rows = []
    for part in chunked(doc_ids):
        ms_rows += s.execute(select(m.MarkScheme.id, m.MarkScheme.matched_paper_document_id)
                             .where(m.MarkScheme.matched_paper_document_id.in_(part))).all()
    ms_ids = [r[0] for r in ms_rows]
    entries_by_ms = defaultdict(list)
    for part in chunked(ms_ids):
        for mid, eid, np, txt in s.execute(
            select(m.MarkSchemeEntry.mark_scheme_id, m.MarkSchemeEntry.id,
                   m.MarkSchemeEntry.number_path, m.MarkSchemeEntry.answer_text)
            .where(m.MarkSchemeEntry.mark_scheme_id.in_(part))):
            entries_by_ms[mid].append(AnswerEntry(eid, np or '', txt))
    entries_by_doc = defaultdict(lambda: defaultdict(list))
    for mid, mdid in ms_rows:
        for e in entries_by_ms[mid]:
            if e.number_path:
                entries_by_doc[mdid][e.number_path].append(e)
    qids = [r[0] for r in qrows]
    exact_by_q = defaultdict(list)
    for part in chunked(qids):
        for eid, qid, np, txt in s.execute(
            select(m.MarkSchemeEntry.id, m.MarkSchemeEntry.question_id,
                   m.MarkSchemeEntry.number_path, m.MarkSchemeEntry.answer_text)
            .where(m.MarkSchemeEntry.question_id.in_(part))):
            exact_by_q[qid].append(AnswerEntry(eid, np or '', txt))
    official_by_q = defaultdict(list)
    for part in chunked(qids):
        for aid, qid, content in s.execute(
            select(m.OfficialAnswer.id, m.OfficialAnswer.question_id, m.OfficialAnswer.content)
            .where(m.OfficialAnswer.question_id.in_(part))):
            official_by_q[qid].append(AnswerEntry(aid, '', content))
    q_by_paper = defaultdict(list)
    for qid, pid, np in qrows:
        q_by_paper[pid].append((qid, np))
    ms_by_doc = defaultdict(list)
    for mid, mdid in ms_rows:
        ms_by_doc[mdid].append(mid)

    stats = {}
    for pid, docid, subjid, pc, yr in papers:
        n = ok = 0
        for qid, np in q_by_paper.get(pid, ()):
            n += 1
            res = service.resolve_answer(np, exact_entries=exact_by_q.get(qid, ()),
                                         entries_by_path=entries_by_doc.get(docid, {}),
                                         official_entries=official_by_q.get(qid, ()))
            if res:
                ok += 1
        stats[pid] = (n, ok, docid, subjid, pc, yr)

    zero = [(pid, *v) for pid, v in stats.items() if v[0] > 0 and v[1] == 0]
    p(f'zero-resolve papers: {len(zero)}')
    p('=' * 100)

    cls_count = defaultdict(int)
    for pid, n, ok, docid, subjid, pc, yr in sorted(zero, key=lambda x: (x[4] or '', x[5] or 0)):
        ms_for = ms_by_doc.get(docid, [])
        n_ms = len(ms_for)
        n_entries = sum(len(entries_by_ms[mid]) for mid in ms_for)
        q_paths = {np for qid, np in q_by_paper.get(pid, ()) if np}
        e_paths = set(entries_by_doc.get(docid, {}).keys())
        overlap = q_paths & e_paths
        n_exact = sum(len(exact_by_q.get(qid, ())) for qid, _ in q_by_paper.get(pid, ()))
        n_off = sum(len(official_by_q.get(qid, ())) for qid, _ in q_by_paper.get(pid, ()))
        if n_ms == 0:
            cls = 'A-no-ms-matched'
        elif n_entries == 0:
            cls = 'B-ms-no-entries'
        elif not overlap:
            cls = 'C-entries-no-path-overlap'
        else:
            cls = 'D-other'
        cls_count[cls] += 1
        p(f'[{cls}] {ed_subj.get(subjid)} {pc} {yr} paper={pid} doc={docid} '
          f'nq={n} ms={n_ms} entries={n_entries} overlap={len(overlap)} exact={n_exact} official={n_off}')
        if cls in ('C-entries-no-path-overlap',):
            p(f'    qpaths sample: {sorted(q_paths)[:12]}')
            p(f'    epaths sample: {sorted(e_paths)[:12]}')
            p(f'    ms entries per ms: {[len(entries_by_ms[mid]) for mid in ms_for][:8]}')

    p('=' * 100)
    p('summary by class:', dict(cls_count))

    # ---- suspicious MS: matched to paper with >=10 questions but few entries ----
    p('=' * 100)
    p('suspicious MS (entries < 20% of questions, questions >= 10):')
    susp = []
    for pid, docid, subjid, pc, yr in papers:
        n = len(q_by_paper.get(pid, ()))
        if n < 10:
            continue
        ms_for = ms_by_doc.get(docid, [])
        n_entries = sum(len(entries_by_ms[mid]) for mid in ms_for)
        if n_entries < 0.2 * n:
            susp.append((ed_subj.get(subjid), pc, yr, pid, docid, n, len(ms_for), n_entries))
    p(f'total suspicious: {len(susp)}')
    for row in sorted(susp, key=lambda x: (x[0] or '', x[1] or '', x[2] or 0)):
        p(f'  {row[0]} {row[1]} {row[2]} paper={row[3]} doc={row[4]} nq={row[5]} ms={row[6]} entries={row[7]}')

txt_path = ROOT / 'tmp_zero_papers.txt'
txt_path.write_text('\n'.join(out) + '\n', encoding='utf-8')
print(f'\nwrote {txt_path}')
