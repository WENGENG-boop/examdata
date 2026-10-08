"""Read-only probe: document revisions, artifacts on disk, mark scheme entries, PDF text.

Usage:
  python tmp_rev_probe.py --tables
  python tmp_rev_probe.py --paper WPS01-01 WPS03-01
  python tmp_rev_probe.py --ms-for WPS01-01 --max 40
  python tmp_rev_probe.py --qms 62285 62286
  python tmp_rev_probe.py --pdf WPS01-01 --pdf-pages 1-6
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from examdata.core import models as m

ROOT = Path(__file__).resolve().parent
eng = create_engine(f"sqlite:///{ROOT / '.data' / 'examdata.db'}")
s = Session(eng)

ap = argparse.ArgumentParser()
ap.add_argument('--paper', nargs='*', default=[])
ap.add_argument('--ms-for', nargs='*', default=[])
ap.add_argument('--qms', nargs='*', type=int, default=[])
ap.add_argument('--pdf', nargs='*', default=[])
ap.add_argument('--pdf-pages', default='1-6')
ap.add_argument('--year', type=int, default=None)
ap.add_argument('--max', type=int, default=30)
ap.add_argument('--tables', action='store_true')
args = ap.parse_args()


def find_docs(code, doc_type=None):
    stmt = select(m.Document).where(m.Document.paper_code.ilike(code))
    if doc_type:
        stmt = stmt.where(m.Document.doc_type == doc_type)
    if args.year:
        stmt = stmt.where(m.Document.year == args.year)
    return s.execute(stmt).scalars().all()


def artifact_path(rev_id):
    rev = s.get(m.DocumentRevision, rev_id) if rev_id else None
    if rev is None:
        return None, None
    art = s.get(m.Artifact, rev.artifact_id)
    if art is None:
        return rev, None
    p = ROOT / '.data' / 'artifacts' / art.storage_key
    return rev, p


if args.tables:
    rows = s.execute(text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")).all()
    print('TABLES:', ' '.join(r[0] for r in rows))
    for t in ('raw_pages', 'page_text', 'document_text'):
        cols = s.execute(text(f'PRAGMA table_info({t})')).all()
        if cols:
            print(f'{t} cols:', [c[1] for c in cols])

for code in args.paper:
    docs = find_docs(code)
    print(f'== {code}: {len(docs)} docs')
    for d in docs:
        rev, p = artifact_path(d.current_revision_id)
        exists = p.is_file() if p else False
        print(f'  doc {d.id} type={d.doc_type} year={d.year} comp={d.component} var={d.variant} status={d.status}')
        print(f'      title={d.title!r}')
        print(f'      rev={d.current_revision_id} artifact={p} exists={exists}')

for code in args.ms_for:
    qps = find_docs(code, 'question_paper')
    if not qps:
        print(f'MS {code}: no QP doc')
        continue
    for qp in qps:
        mss = s.execute(select(m.MarkScheme).where(
            m.MarkScheme.matched_paper_document_id == qp.id)).scalars().all()
        print(f'== MS for {code} (qp doc {qp.id} year={qp.year}): {len(mss)} schemes')
        for ms in mss:
            msdoc = s.get(m.Document, ms.document_id)
            rev, p = artifact_path(msdoc.current_revision_id if msdoc else None)
            entries = s.execute(select(m.MarkSchemeEntry).where(
                m.MarkSchemeEntry.mark_scheme_id == ms.id).order_by(
                m.MarkSchemeEntry.number_path, m.MarkSchemeEntry.id)).scalars().all()
            exists = p.is_file() if p else False
            print(f'  ms {ms.id} doc={ms.document_id} ({msdoc.paper_code if msdoc else "?"}) '
                  f'conf={ms.match_confidence} entries={len(entries)} artifact_exists={exists}')
            print(f'      artifact={p}')
            for e in entries[:args.max]:
                ans = (e.answer_text or '').replace('\n', ' | ')[:220]
                g = (e.guidance or '').replace('\n', ' | ')[:120]
                print(f'   entry q={e.question_id} #{e.number_path or e.number_label} '
                      f'mk={e.marks} ans={ans!r} g={g!r}')

for qid in args.qms:
    entries = s.execute(select(m.MarkSchemeEntry).where(
        m.MarkSchemeEntry.question_id == qid)).scalars().all()
    print(f'== Q {qid}: {len(entries)} ms entries')
    for e in entries:
        ans = (e.answer_text or '').replace('\n', ' | ')
        g = (e.guidance or '').replace('\n', ' | ')
        print(f'   #{e.number_path or e.number_label} mk={e.marks}')
        print(f'     ans={ans[:600]!r}')
        if g:
            print(f'     g={g[:300]!r}')

if args.pdf:
    try:
        import fitz
    except ImportError:
        print('fitz NOT AVAILABLE')
        fitz = None
    if fitz:
        try:
            lo, hi = (int(x) for x in args.pdf_pages.split('-'))
        except ValueError:
            lo, hi = 1, 6
        for code in args.pdf:
            for dtype in ('question_paper', 'mark_scheme'):
                docs = find_docs(code, dtype)
                if not docs:
                    print(f'PDF {code} {dtype}: no doc')
                    continue
                for d in docs:
                    rev, p = artifact_path(d.current_revision_id)
                    if not p or not p.is_file():
                        print(f'PDF {code} {dtype} doc={d.id} year={d.year}: artifact missing {p}')
                        continue
                    doc = fitz.open(str(p))
                    print(f'===== PDF {code} {dtype} doc={d.id} year={d.year} pages={doc.page_count} =====')
                    for i in range(lo - 1, min(hi, doc.page_count)):
                        print(f'--- page {i + 1} ---')
                        print(doc[i].get_text())
                    doc.close()
