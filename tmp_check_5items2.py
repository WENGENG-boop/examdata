"""Second-pass checks for the 5 pending audit items (context + blast radius)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sqlalchemy import create_engine, select, func
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


with Session(eng) as s:
    # ============ A. MS 1554 blast radius ============
    p('=' * 90)
    p('A1. entries 26617-26619 raw + links')
    for eid in (26617, 26618, 26619):
        e = s.get(m.MarkSchemeEntry, eid)
        p(f'  {eid}: qid={e.question_id} path={e.number_path!r} marks={e.marks} raw={json.dumps(e.raw, ensure_ascii=False)[:300]}')

    p('A2. paper 1390 (wac02-01) questions + resolvability')
    qs = s.scalars(select(m.Question).where(m.Question.paper_id == 1390)
                   .order_by(m.Question.display_order)).all()
    # collect MS entries matched to this doc (same logic as _page_answers)
    doc_id = 1721
    entries_by_path: dict[str, list[AnswerEntry]] = {}
    ms_ids = s.scalars(select(m.MarkScheme.id).where(
        m.MarkScheme.matched_paper_document_id == doc_id)).all()
    for mid in ms_ids:
        for eid, np, txt in s.execute(
            select(m.MarkSchemeEntry.id, m.MarkSchemeEntry.number_path, m.MarkSchemeEntry.answer_text)
            .where(m.MarkSchemeEntry.mark_scheme_id == mid)
        ):
            if np:
                entries_by_path.setdefault(np, []).append(AnswerEntry(eid, np, txt))
    n_ok = n_none = 0
    for q in qs:
        exact = [AnswerEntry(e.id, e.number_path or '', e.answer_text) for e in s.scalars(
            select(m.MarkSchemeEntry).where(m.MarkSchemeEntry.question_id == q.id)).all()]
        res = service.resolve_answer(q.number_path, exact_entries=exact,
                                     entries_by_path=entries_by_path, official_entries=[])
        status = res['source'] if res else 'NONE'
        if res:
            n_ok += 1
        else:
            n_none += 1
        p(f'  q{q.id} {q.number_path!r} {q.kind} m={q.marks} -> {status}'
          + (f' ids={res["entry_ids"]}' if res else ''))
    p(f'  summary: resolvable={n_ok} none={n_none} of {len(qs)}')

    p('A3. MS entry count distribution + docs with <=5 entries')
    cnt = dict(s.execute(
        select(m.MarkSchemeEntry.mark_scheme_id, func.count())
        .group_by(m.MarkSchemeEntry.mark_scheme_id)).all())
    ms_all = s.scalars(select(m.MarkScheme)).all()
    dist = {}
    for ms in ms_all:
        c = cnt.get(ms.id, 0)
        dist[c] = dist.get(c, 0) + 1
    p('  entry-count distribution (count->#MS):', json.dumps({str(k): v for k, v in sorted(dist.items())})[:600])
    lows = sorted(((cnt.get(ms.id, 0), ms.id) for ms in ms_all))[:30]
    for c, mid in lows:
        ms = s.get(m.MarkScheme, mid)
        doc = s.get(m.Document, ms.document_id)
        p(f'  MS {mid}: {c} entries | {doc.title if doc else "?"!r} | year={doc.year if doc else None} | matched={ms.matched_paper_document_id}')

    p('A4. MS 1656 PDF pages 3-7 full text')
    import pymupdf
    ms1656 = s.scalar(select(m.MarkScheme).where(m.MarkScheme.document_id == 1656))
    doc1656 = s.get(m.Document, 1656)
    if doc1656 and doc1656.current_revision_id:
        data = service._current_revision_pdf(s, doc1656)
        with pymupdf.open(stream=data, filetype='pdf') as pdf:
            for pg in (3, 4, 5, 6, 7):
                txt = pdf[pg - 1].get_text()
                p(f'  --- page {pg} (first 900) ---')
                p('  ' + clean(txt, 900))

    # ============ B. WBI15-8.* list + better node search ============
    p('=' * 90)
    p('B1. WBI15-8.* nodes')
    nodes = s.scalars(select(m.TaxonomyNode).where(m.TaxonomyNode.code.like('WBI15-8%'))
                      .order_by(m.TaxonomyNode.code)).all()
    for n in nodes:
        p(f'  {n.code} | {clean(n.name, 130)}')
    p('B2. WBI15 nodes mentioning memory/alzheimer/brain')
    nodes = s.scalars(select(m.TaxonomyNode).where(m.TaxonomyNode.code.like('WBI15%'))).all()
    for n in nodes:
        t = ((n.name or '') + ' ' + json.dumps(n.attrs or {})).lower()
        if 'memory' in t or 'alzheim' in t or 'brain' in t:
            p(f'  HIT {n.code} | {clean(n.name, 150)}')

    # ============ C. WIT13 Q4 subtree ============
    p('=' * 90)
    p('C1. qid 45837 (wit13-01 Q4) subtree')
    q = s.get(m.Question, 45837)
    stack = [q]
    seen = set()
    while stack:
        cur = stack.pop(0)
        if cur.id in seen:
            continue
        seen.add(cur.id)
        kids = s.scalars(select(m.Question).where(m.Question.parent_id == cur.id)
                         .order_by(m.Question.display_order)).all()
        tags = s.execute(
            select(m.TaxonomyNode.code).join(m.QuestionTaxonomy, m.QuestionTaxonomy.node_id == m.TaxonomyNode.id)
            .where(m.QuestionTaxonomy.question_id == cur.id)).all()
        p(f'  {cur.id} {cur.number_path!r} kind={cur.kind} m={cur.marks} tags={[t[0] for t in tags]}')
        p(f'      stem: {clean(cur.stem_text, 220)}')
        stack.extend(kids)

    # ============ D. WPS02-D subtree ============
    p('=' * 90)
    p('D1. WPS02-D.* nodes')
    nodes = s.scalars(select(m.TaxonomyNode).where(m.TaxonomyNode.code.like('WPS02-D%'))
                      .order_by(m.TaxonomyNode.code)).all()
    for n in nodes:
        p(f'  {n.code} | {clean(n.name, 150)}')
    p('D2. WPS02 nodes mentioning list a / variable / experiment')
    nodes = s.scalars(select(m.TaxonomyNode).where(m.TaxonomyNode.code.like('WPS02%'))).all()
    for n in nodes:
        t = ((n.name or '') + ' ' + json.dumps(n.attrs or {})).lower()
        if 'list a' in t or 'variable' in t or 'experiment' in t:
            p(f'  HIT {n.code} | {clean(n.name, 150)} | attrs={clean(json.dumps(n.attrs or {}), 200)}')

    # ============ E. 28395 batch item + decision ============
    p('=' * 90)
    p('E1. batch item + decisions for 28395')
    for bdir in ('tmp_jev_full_batches_r2/ial18-business/batches', 'tmp_jev_full_batches/ial18-business/batches'):
        d = ROOT / bdir
        if not d.is_dir():
            continue
        for f in sorted(d.glob('batch-*.jsonl')):
            for line in open(f, encoding='utf-8'):
                if not line.strip():
                    continue
                r = json.loads(line)
                if r.get('question_id') == 28395:
                    p(f'  [{bdir}] item:')
                    p('  ' + json.dumps(r, ensure_ascii=False)[:1500])
                    break
    for ddir in ('tmp_jev_full_decisions_r2/ial18-business', 'tmp_jev_full_decisions/ial18-business'):
        d = ROOT / ddir
        if not d.is_dir():
            continue
        for f in sorted(d.glob('batch-*.jsonl')):
            for line in open(f, encoding='utf-8'):
                if not line.strip():
                    continue
                r = json.loads(line)
                if r.get('question_id') == 28395:
                    p(f'  [{ddir}] decision:')
                    p('  ' + json.dumps(r, ensure_ascii=False)[:800])
                    break

    # ============ F. parent-label pattern stat ============
    p('=' * 90)
    p('F1. parent questions: tag subset of children tags?')
    from collections import defaultdict
    # all questions with children
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
    total_parents = with_tags = subset = not_subset = 0
    examples = []
    for pid in kids_of:
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
            if len(examples) < 15:
                examples.append((pid, sorted(pt), sorted(ct)[:6]))
    p(f'  parents with children: {total_parents}; with own tags: {with_tags}; tag-subset-of-children: {subset}; not: {not_subset}')
    for pid, pt, ct in examples:
        q2 = s.get(m.Question, pid)
        p(f'  NOT-SUBSET q{pid} {q2.number_path!r}: parent={pt} children={ct}')

txt_path = ROOT / 'tmp_check_5items2.txt'
txt_path.write_text('\n'.join(out) + '\n', encoding='utf-8')
print(f'\nwrote {txt_path}')
