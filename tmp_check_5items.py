"""Verify the 5 pending audit items against the DB + original PDFs.

[2]  qid=47721  ial-accounting  wac02-01 1(b)   suspected answer mismatch
[40] qid=28395  ial18-business  wbs11-01 1     label vs sub-question stems
[39] qid=25188  ial18-biology   wbi15-01 8(e)  WBI15-8.6 vs WBI15-8.16
[51] qid=45837  ial18-it        wit13-01 4     WIT13-15.2.1 context
[32] qid=61531  ial-psychology  wps02-01 9(b)  WPS02-4.2.5 context
"""
from __future__ import annotations

import json
import sys
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


def clean(text, n=260):
    return ' '.join((text or '').split())[:n]


def node_info(s, code_or_id):
    n = None
    if isinstance(code_or_id, int):
        n = s.get(m.TaxonomyNode, code_or_id)
    else:
        n = s.scalar(select(m.TaxonomyNode).where(m.TaxonomyNode.code == code_or_id))
    if n is None:
        p(f'  node {code_or_id!r}: NOT FOUND')
        return None
    chain = []
    cur = n
    while cur is not None:
        chain.append(f'{cur.code} = {clean(cur.name, 90)}')
        cur = s.get(m.TaxonomyNode, cur.parent_id) if cur.parent_id else None
    p(f'  node {n.id} {n.code} type={n.node_type} src={n.source}')
    p(f'    name: {clean(n.name, 300)}')
    p(f'    chain: {" << ".join(reversed(chain))}')
    if n.attrs:
        p(f'    attrs: {json.dumps(n.attrs, ensure_ascii=False)[:800]}')
    return n


with Session(eng) as s:
    # ================= [2] qid=47721 =================
    p('=' * 90)
    p('ITEM [2] qid=47721 ial-accounting wac02-01 1(b) - suspected answer mismatch')
    q = s.get(m.Question, 47721)
    paper = s.get(m.Paper, q.paper_id)
    doc = s.get(m.Document, paper.document_id)
    p('question:', q.id, repr(q.number_path), q.kind, 'marks', q.marks)
    p('paper:', paper.id, 'doc:', doc.id, doc.paper_code, doc.year, 'rev', doc.current_revision_id, doc.title)
    for pid in (47719, 47720, 47721):
        r = s.get(m.Question, pid)
        if r:
            p('  tree:', r.id, repr(r.number_path), r.kind, 'marks', r.marks, '|', clean(r.stem_text, 160))
    for code, name, conf, by, rev in s.execute(
        select(m.TaxonomyNode.code, m.TaxonomyNode.name, m.QuestionTaxonomy.confidence,
               m.QuestionTaxonomy.assigned_by, m.QuestionTaxonomy.reviewed)
        .join(m.QuestionTaxonomy, m.QuestionTaxonomy.node_id == m.TaxonomyNode.id)
        .where(m.QuestionTaxonomy.question_id == 47721)
    ):
        p('  tag:', code, '|', clean(name, 80), '| conf', conf, '| by', by, '| reviewed', rev)

    rows = s.execute(
        select(m.MarkSchemeEntry.id, m.MarkSchemeEntry.mark_scheme_id, m.MarkSchemeEntry.number_path,
               m.MarkSchemeEntry.marks, m.MarkSchemeEntry.answer_text)
        .where(m.MarkSchemeEntry.question_id == 47721)
    ).all()
    p(f'  direct MS entries for qid=47721: {len(rows)}')
    for eid, msid, np, mk, txt in rows:
        p(f'    entry {eid} ms={msid} path={np!r} marks={mk} | {clean(txt, 300)}')

    ms_rows = s.execute(
        select(m.MarkScheme.id, m.MarkScheme.document_id, m.MarkScheme.match_confidence,
               m.MarkScheme.match_method, m.MarkScheme.match_evidence)
        .where(m.MarkScheme.matched_paper_document_id == doc.id)
    ).all()
    ms_ids = []
    for mid, mdid, mc, mm, me in ms_rows:
        ms_ids.append(mid)
        md = s.get(m.Document, mdid)
        p(f'  matched-MS {mid}: doc={mdid} {md.title if md else None!r} conf={mc} method={mm} evidence={json.dumps(me, ensure_ascii=False)[:220]}')

    for mid in ms_ids:
        rs = s.execute(
            select(m.MarkSchemeEntry.id, m.MarkSchemeEntry.number_path, m.MarkSchemeEntry.marks,
                   m.MarkSchemeEntry.answer_text)
            .where(m.MarkSchemeEntry.mark_scheme_id == mid).order_by(m.MarkSchemeEntry.id)
        ).all()
        p(f'  MS {mid}: total {len(rs)} entries; first 40 paths: {[r[1] for r in rs[:40]]}')
        for eid, np, mk, txt in rs:
            if np and (np == '1' or np.startswith('1(')):
                p(f'    MS{mid}-entry {eid} {np!r} marks={mk} | {clean(txt, 160)}')
        # where does the Labour text live?
        for eid, np, mk, txt in rs:
            t = (txt or '').lower()
            if 'labour efficiency' in t or 'gearing' in t:
                p(f'    MS{mid}-search entry {eid} {np!r} marks={mk} | {clean(txt, 140)}')

    # resolve simulation (same logic as CLI _page_answers)
    entries_by_path: dict[str, list[AnswerEntry]] = {}
    for mid in ms_ids:
        for eid, np, txt in s.execute(
            select(m.MarkSchemeEntry.id, m.MarkSchemeEntry.number_path, m.MarkSchemeEntry.answer_text)
            .where(m.MarkSchemeEntry.mark_scheme_id == mid)
        ):
            if np:
                entries_by_path.setdefault(np, []).append(AnswerEntry(eid, np, txt))
    exact = [AnswerEntry(eid, np or '', txt) for eid, msid, np, mk, txt in rows]
    res = service.resolve_answer('1(b)', exact_entries=exact, entries_by_path=entries_by_path,
                                 official_entries=[])
    if res:
        p('  RESOLVE source:', res['source'], 'path:', res['number_path'], 'entry_ids:', res['entry_ids'])
        p('  RESOLVE text:', clean(res['text'], 900))
    else:
        p('  RESOLVE: None')

    regions = (q.attrs or {}).get('ms_regions') or []
    p('  ms_regions:', json.dumps(regions, ensure_ascii=False)[:500])
    try:
        crops = service.question_crops(s, 47721, role='ms')
        cdir = ROOT / 'tmp_check_crops'
        cdir.mkdir(exist_ok=True)
        for i, c in enumerate(crops, 1):
            fp = cdir / f'47721_ms_{i}_p{c["page"]}.png'
            fp.write_bytes(c['png'])
            p('  ms crop:', fp.name, 'bbox', c['bbox'])
    except Exception as exc:
        p('  ms crop ERROR:', type(exc).__name__, str(exc)[:200])

    # extract the underlying MS PDF text for the ms_regions pages
    import pymupdf
    if regions:
        sha = regions[0].get('sha256')
        art = s.scalar(select(m.Artifact).where(m.Artifact.sha256 == sha))
        if art:
            data = (service.get_settings().artifacts_dir / art.storage_key).read_bytes()
            with pymupdf.open(stream=data, filetype='pdf') as pdf:
                p('  MS PDF pages:', len(pdf))
                for pg in sorted({int(r['page']) for r in regions}):
                    txt = pdf[pg - 1].get_text()
                    p(f'  --- MS PDF page {pg} text (first 1500 chars) ---')
                    p('  ' + clean(txt, 1500))
                for needle in ('gearing', 'labour efficiency', 'labour rate', 'maltese'):
                    hits = []
                    for i in range(len(pdf)):
                        if needle in pdf[i].get_text().lower():
                            hits.append(i + 1)
                    p(f'  MS PDF search {needle!r}: pages {hits}')
        else:
            p('  ms_regions sha artifact not found')

    # ================= [40] qid=28395 =================
    p('=' * 90)
    p('ITEM [40] qid=28395 ial18-business wbs11-01 Q1 - label vs sub-questions')
    q = s.get(m.Question, 28395)
    paper = s.get(m.Paper, q.paper_id)
    doc = s.get(m.Document, paper.document_id)
    p('question:', q.id, repr(q.number_path), q.kind, 'marks', q.marks, '|', clean(q.stem_text, 200))
    # whole subtree
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
            .where(m.QuestionTaxonomy.question_id == cur.id)
        ).all()
        tag_txt = ','.join(t[0] for t in tags)
        p(f'  {cur.id} {cur.number_path!r} kind={cur.kind} marks={cur.marks} tags=[{tag_txt}]')
        p(f'      stem: {clean(cur.stem_text, 200)}')
        stack.extend(kids)
    # any elasticity anywhere in this paper?
    hits = s.execute(
        select(m.Question.id, m.Question.number_path, m.Question.stem_text)
        .where(m.Question.paper_id == paper.id)
    ).all()
    for qid2, np2, st2 in hits:
        if st2 and 'elasticity' in st2.lower():
            p(f'  elasticity hit: {qid2} {np2!r} | {clean(st2, 200)}')

    # ================= [39] qid=25188 =================
    p('=' * 90)
    p('ITEM [39] qid=25188 ial18-biology wbi15-01 8(e) - WBI15-8.6 vs WBI15-8.16')
    for code in ('WBI15-8.6', 'WBI15-8.16'):
        node_info(s, code)

    # ================= [51] qid=45837 =================
    p('=' * 90)
    p('ITEM [51] qid=45837 ial18-it wit13-01 Q4 - WIT13-15.2 context')
    nodes = s.execute(select(m.TaxonomyNode).where(m.TaxonomyNode.code.like('WIT13-15%'))
                      .order_by(m.TaxonomyNode.code)).scalars().all()
    for n in nodes:
        p(f'  {n.id} {n.code} | {clean(n.name, 140)} | parent={n.parent_id}')
    p('  --- detail for 15.2 subtree ---')
    for code in ('WIT13-15.2', 'WIT13-15.2.1', 'WIT13-15.2.2', 'WIT13-15.2.3'):
        node_info(s, code)

    # ================= [32] qid=61531 =================
    p('=' * 90)
    p('ITEM [32] qid=61531 ial-psychology wps02-01 9(b) - WPS02-4.2.5 context')
    nodes = s.execute(select(m.TaxonomyNode).where(m.TaxonomyNode.code.like('WPS02-4.2%'))
                      .order_by(m.TaxonomyNode.code)).scalars().all()
    for n in nodes:
        p(f'  {n.id} {n.code} | {clean(n.name, 160)} | parent={n.parent_id}')
    p('  --- detail ---')
    for code in ('WPS02-4.2', 'WPS02-4.2.5'):
        node_info(s, code)

txt_path = ROOT / 'tmp_check_5items.txt'
txt_path.write_text('\n'.join(out) + '\n', encoding='utf-8')
print(f'\nwrote {txt_path}')
