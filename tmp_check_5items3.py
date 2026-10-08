"""Third-pass checks: [2] scope + [39]/[32] context + Edexcel parent-label stat."""
from __future__ import annotations

import json
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


def clean(text, n=200):
    return ' '.join((text or '').split())[:n]


def chunked(seq, n=500):
    seq = list(seq)
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


with Session(eng) as s:
    # ---- 1. WAC02-2.3.1.2 node + siblings ----
    p('=' * 90)
    p('1. WAC02-2.3.* nodes (label of q47721)')
    nodes = s.scalars(select(m.TaxonomyNode).where(m.TaxonomyNode.code.like('WAC02-2.3%'))
                      .order_by(m.TaxonomyNode.code)).all()
    for n in nodes:
        p(f'  {n.code} | {clean(n.name, 150)} | attrs={clean(json.dumps(n.attrs or {}), 180)}')

    # ---- 2. WBI15 nodes 8.6/8.14/8.15/8.16 full + calibration questions ----
    p('=' * 90)
    p('2. WBI15 brain nodes full attrs')
    for code in ('WBI15-8.6', 'WBI15-8.14', 'WBI15-8.15', 'WBI15-8.16'):
        n = s.scalar(select(m.TaxonomyNode).where(m.TaxonomyNode.code == code))
        if n:
            p(f'  {code}: attrs.text = {clean((n.attrs or {}).get("text"), 400)}')
    p('2b. calibration: questions labeled with these codes (stem excerpts)')
    for code in ('WBI15-8.6', 'WBI15-8.14', 'WBI15-8.16'):
        rows = s.execute(
            select(m.Question.id, m.Question.number_path, m.Question.stem_text, m.Document.paper_code, m.Document.year)
            .join(m.QuestionTaxonomy, m.QuestionTaxonomy.question_id == m.Question.id)
            .join(m.TaxonomyNode, m.TaxonomyNode.id == m.QuestionTaxonomy.node_id)
            .join(m.Paper, m.Paper.id == m.Question.paper_id)
            .join(m.Document, m.Document.id == m.Paper.document_id)
            .where(m.TaxonomyNode.code == code)
            .order_by(m.Question.id.desc()).limit(6)
        ).all()
        p(f'  --- {code}: {len(rows)} sample ---')
        for qid, np, st, pc, yr in rows:
            p(f'    q{qid} {pc} {yr} {np!r}: {clean(st, 160)}')

    # ---- 3. psych spec context for "List A" ----
    p('=' * 90)
    p('3. psych documents')
    subj_ids = [r[0] for r in s.execute(select(m.Subject.id).where(m.Subject.code.like('%psych%'))).all()]
    docs = s.execute(
        select(m.Document.id, m.Document.title, m.Document.doc_type, m.Document.year)
        .where(m.Document.subject_id.in_(subj_ids)).order_by(m.Document.id)).all()
    for did, title, dt, yr in docs:
        p(f'  doc {did}: [{dt}] {title!r} year={yr}')
    # find spec doc and search List A
    import pymupdf
    for did, title, dt, yr in docs:
        if not title or 'specification' not in (title or '').lower():
            continue
        doc = s.get(m.Document, did)
        try:
            data = service._current_revision_pdf(s, doc)
        except Exception as exc:
            p(f'  spec doc {did} pdf error: {exc}')
            continue
        with pymupdf.open(stream=data, filetype='pdf') as pdf:
            pages_hit = [i + 1 for i in range(len(pdf)) if 'List A' in pdf[i].get_text()]
            p(f'  spec doc {did} pages={len(pdf)}; pages with "List A": {pages_hit}')
            for pg in pages_hit[:3]:
                txt = pdf[pg - 1].get_text()
                p(f'  --- spec page {pg} (first 1600) ---')
                p('  ' + clean(txt, 1600))

    # ---- 4. Edexcel-only parent-tag stat ----
    p('=' * 90)
    p('4. Edexcel parents: tag subset of children?')
    kids_rows = s.execute(select(m.Question.parent_id, m.Question.id).where(
        m.Question.parent_id.isnot(None))).all()
    kids_of = defaultdict(set)
    for pid, qid in kids_rows:
        kids_of[pid].add(qid)
    tags_of = defaultdict(set)
    for qid, code in s.execute(
        select(m.QuestionTaxonomy.question_id, m.TaxonomyNode.code)
        .join(m.TaxonomyNode, m.TaxonomyNode.id == m.QuestionTaxonomy.node_id)):
        tags_of[qid].add(code)
    # edexcel question ids = questions whose paper->doc->subject.code like 'ial%'
    ed_q = {r[0] for r in s.execute(
        select(m.Question.id)
        .join(m.Paper, m.Paper.id == m.Question.paper_id)
        .join(m.Document, m.Document.id == m.Paper.document_id)
        .join(m.Subject, m.Subject.id == m.Document.subject_id)
        .where(m.Subject.code.like('ial%'))).all()}
    total_parents = with_tags = subset = not_subset = 0
    examples = []
    for pid in kids_of:
        if pid not in ed_q:
            continue
        total_parents += 1
        pt = tags_of.get(pid)
        if not pt:
            continue
        with_tags += 1
        ct = set()
        for k in kids_of[pid]:
            ct |= tags_of.get(k, set())
        if pt <= ct:
            subset += 1
        else:
            not_subset += 1
            if len(examples) < 12:
                q2 = s.get(m.Question, pid)
                examples.append((pid, q2.number_path, sorted(pt), sorted(ct)[:8]))
    p(f'  edexcel parents: {total_parents}; with tags: {with_tags}; subset: {subset}; not-subset: {not_subset}')
    for pid, np, pt, ct in examples:
        p(f'    q{pid} {np!r}: parent={pt} children={ct}')

    # ---- 5. Edexcel per-paper answer resolution ----
    p('=' * 90)
    p('5. Edexcel per-paper answer resolution')
    ed_subj = {r[0]: r[1] for r in s.execute(
        select(m.Subject.id, m.Subject.code).where(m.Subject.code.like('ial%'))).all()}
    p(f'  edexcel subjects: {len(ed_subj)}')
    papers = s.execute(
        select(m.Paper.id, m.Paper.document_id, m.Document.subject_id, m.Document.paper_code, m.Document.year)
        .join(m.Document, m.Document.id == m.Paper.document_id)
        .where(m.Document.subject_id.in_(ed_subj.keys()))).all()
    p(f'  edexcel papers: {len(papers)}')
    paper_ids = [r[0] for r in papers]
    qrows = []
    for part in chunked(paper_ids):
        qrows += s.execute(select(m.Question.id, m.Question.paper_id, m.Question.number_path)
                           .where(m.Question.paper_id.in_(part))).all()
    p(f'  edexcel questions: {len(qrows)}')
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
    some = [pid for pid, v in stats.items() if v[0] > 0 and v[1] > 0]
    p(f'  papers with questions: {len(stats)}; resolvable>0: {len(some)}; zero-resolve: {len(zero)}')
    p('  --- zero-resolve papers ---')
    for pid, n, ok, docid, subjid, pc, yr in sorted(zero, key=lambda x: x[4]):
        p(f'    {ed_subj.get(subjid)} {pc} {yr} paper={pid} doc={docid} n={n}')
    tot_q = sum(v[0] for v in stats.values())
    tot_ok = sum(v[1] for v in stats.values())
    p(f'  TOTAL: {tot_ok}/{tot_q} questions resolvable ({100.0*tot_ok/tot_q:.1f}%)')

    # parse_run for doc 1656
    p('  parse_run for doc 1656:')
    rows = s.execute(
        select(m.ParseRun.id, m.ParseRun.parser_version, m.ParseRun.status,
               m.ParseRun.stats, m.ParseRun.error)
        .join(m.DocumentRevision, m.DocumentRevision.id == m.ParseRun.document_revision_id)
        .where(m.DocumentRevision.document_id == 1656)).all()
    for rid, pv, st, stt, err in rows:
        p(f'    run {rid} {pv} status={st} stats={clean(json.dumps(stt or {}), 300)} err={clean(err, 150)}')
    p('  parse_run count total:', s.execute(select(m.ParseRun.id)).all().__len__())

    # ---- 6. MS 1656 pages 12-14 ----
    p('=' * 90)
    p('6. MS 1656 pages 12-14 text (where entries 26617-26619 point)')
    import pymupdf
    doc1656 = s.get(m.Document, 1656)
    data = service._current_revision_pdf(s, doc1656)
    with pymupdf.open(stream=data, filetype='pdf') as pdf:
        for pg in (12, 13, 14):
            txt = pdf[pg - 1].get_text()
            p(f'  --- page {pg} (first 800) ---')
            p('  ' + clean(txt, 800))

txt_path = ROOT / 'tmp_check_5items3.txt'
txt_path.write_text('\n'.join(out) + '\n', encoding='utf-8')
print(f'\nwrote {txt_path}')
