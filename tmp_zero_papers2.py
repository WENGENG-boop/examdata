"""Deep-dive causes for zero-resolve Edexcel papers (A: no MS matched; B: MS empty)."""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from examdata.core import models as m

ROOT = Path(__file__).resolve().parent
DB = ROOT / '.data' / 'examdata.db'
eng = create_engine(f'sqlite:///{DB}')

out: list[str] = []


def p(*args) -> None:
    line = ' '.join(str(a) for a in args)
    out.append(line)
    print(line)


def clean(text, n=140):
    return ' '.join((text or '').split())[:n]


with Session(eng) as s:
    ed_subj = {r[0]: r[1] for r in s.execute(
        select(m.Subject.id, m.Subject.code).where(m.Subject.code.like('ial%'))).all()}

    # --- A-class papers (from tmp_zero_papers.txt): paper doc ids with no matched MS
    a_docs = [1752, 1728, 1753, 1871, 1901, 1936, 1952, 2006, 2088, 2266, 2378, 2559,
              2557, 2586, 2491, 2640, 3115, 3116, 3107, 3319, 3250, 3255, 3256, 3257,
              3263, 3268, 3271, 3273, 3290, 3294, 3297, 3203, 3510, 3511, 344, 342, 707, 553]
    p('=' * 100)
    p('SECTION 1: A-class (no MS matched) — search for unmatched MS candidates')
    for docid in a_docs:
        doc = s.get(m.Document, docid)
        if doc is None:
            p(f'doc {docid}: NOT FOUND')
            continue
        subj_code = ed_subj.get(doc.subject_id, '?')
        # candidates: MS docs same subject, same year, title like mark, not already matched to this paper
        cands = s.execute(
            select(m.Document.id, m.Document.title, m.Document.doc_type,
                   m.Document.paper_code, m.Document.year)
            .where(m.Document.subject_id == doc.subject_id,
                   m.Document.year == doc.year,
                   m.Document.id != doc.id)
            .where((m.Document.title.like('%ark%')) | (m.Document.doc_type.like('%mark%')))
        ).all()
        ms_rows = s.execute(
            select(m.MarkScheme.id, m.MarkScheme.document_id, m.MarkScheme.matched_paper_document_id,
                   m.MarkScheme.match_method)
            .where(m.MarkScheme.document_id.in_([c[0] for c in cands]) if cands else False)
        ).all()
        ms_by_doc = {r[1]: r for r in ms_rows}
        p(f'[{subj_code}] doc={docid} paper_code={doc.paper_code} year={doc.year} '
          f'title={clean(doc.title, 90)!r} candidates={len(cands)}')
        for cid, ctitle, cdt, cpc, cyr in cands[:6]:
            row = ms_by_doc.get(cid)
            mt = f'matched_to={row[2]}' if row else 'no-ms-row'
            p(f'    cand doc={cid} [{cdt}] {clean(ctitle, 80)!r} pc={cpc} {mt}')

    p('=' * 100)
    p('SECTION 2: B-class (MS matched, 0 entries) — MS parse_run status')
    b_docs = [1736, 1684, 1635, 1641, 1685, 1696, 1700, 1705, 1714, 1740, 1745, 1748,
              1858, 1970, 1976, 1857, 1864, 1886, 1893, 1905, 1912, 1922, 1931, 1946,
              1954, 1971, 1974, 1892, 1943, 1953, 1972, 1977, 1994, 2079, 2000, 2080,
              2106, 2117, 2118, 2217, 2258, 2287, 2328, 2333, 2340, 2408, 3117, 3118]
    for docid in b_docs:
        doc = s.get(m.Document, docid)
        if doc is None:
            p(f'doc {docid}: NOT FOUND')
            continue
        ms_rows = s.execute(
            select(m.MarkScheme.id, m.MarkScheme.document_id, m.MarkScheme.parse_run_id)
            .where(m.MarkScheme.matched_paper_document_id == docid)).all()
        # actually B-class doc ids listed above are the *paper* docs; find MS matched to them
        # re-query: mark_scheme.matched_paper_document_id == docid → MS doc = document_id
        parts = []
        for mid, msdocid, prid in ms_rows:
            msdoc = s.get(m.Document, msdocid)
            pr = s.get(m.ParseRun, prid) if prid else None
            stats = (pr.stats or {}) if pr else {}
            parts.append(
                f'ms={mid} msdoc={msdocid} title={clean(msdoc.title if msdoc else "?", 70)!r} '
                f'run={prid} status={pr.status if pr else None} stats={clean(str(stats), 120)}')
        p(f'paperdoc={docid} ({ed_subj.get(doc.subject_id)} {doc.paper_code} {doc.year}):')
        for x in parts:
            p('    ' + x)

    p('=' * 100)
    p('SECTION 3: all Edexcel MS docs with 0 entries + parse status')
    ms_rows = s.execute(
        select(m.MarkScheme.id, m.MarkScheme.document_id, m.MarkScheme.matched_paper_document_id,
               m.MarkScheme.parse_run_id)
    ).all()
    msdoc_ids = sorted({r[1] for r in ms_rows})
    entry_count = defaultdict(int)
    if msdoc_ids:
        rows = s.execute(
            select(m.MarkScheme.document_id, m.MarkSchemeEntry.id)
            .join(m.MarkSchemeEntry, m.MarkSchemeEntry.mark_scheme_id == m.MarkScheme.id)
        ).all()
        for msdocid, eid in rows:
            entry_count[msdocid] += 1
    zero_ms = [(r[0], r[1], r[2], r[3]) for r in ms_rows if entry_count.get(r[1], 0) == 0]
    p(f'total MS rows: {len(ms_rows)}; MS docs: {len(msdoc_ids)}; MS docs with 0 entries: {len(zero_ms)}')
    # only edexcel subjects
    for mid, msdocid, mpid, prid in zero_ms:
        msdoc = s.get(m.Document, msdocid)
        if msdoc is None or msdoc.subject_id not in ed_subj:
            continue
        pr = s.get(m.ParseRun, prid) if prid else None
        stats = (pr.stats or {}) if pr else {}
        p(f'  ms={mid} msdoc={msdocid} [{ed_subj.get(msdoc.subject_id)}] {msdoc.paper_code} {msdoc.year} '
          f'title={clean(msdoc.title, 70)!r} run={prid} status={pr.status if pr else None} '
          f'stats={clean(str(stats), 110)}')

txt_path = ROOT / 'tmp_zero_papers2.txt'
txt_path.write_text('\n'.join(out) + '\n', encoding='utf-8')
print(f'\nwrote {txt_path}')
