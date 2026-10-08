"""Paper-level dump: all questions + full MS text (collapsed) for a paper."""
import re
import sys
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
c = sqlite3.connect(str(ROOT / '.data' / 'examdata.db'))
c.row_factory = sqlite3.Row


def storage_path(key):
    return ROOT / '.data' / 'artifacts' / key


def collapse(txt):
    lines = [ln.strip() for ln in txt.split('\n')]
    out = []
    for ln in lines:
        if not ln:
            continue
        out.append(ln)
    return '\n'.join(out)


def pdf_text(path, page_from=None, page_to=None):
    import fitz
    doc = fitz.open(str(path))
    lo = max(1, page_from or 1)
    hi = min(doc.page_count, page_to or doc.page_count)
    out = []
    for p in range(lo, hi + 1):
        out.append(f'--- page {p} ---')
        out.append(collapse(doc[p - 1].get_text('text')))
    doc.close()
    return '\n'.join(out)


def pick_revision(document_id, paper_no):
    rows = c.execute("""
      SELECT dr.id, dr.source_url, a.storage_key, a.mime
      FROM document_revision dr JOIN artifact a ON a.id=dr.artifact_id
      WHERE dr.document_id=?""", (document_id,)).fetchall()
    for r in rows:
        if paper_no and paper_no.lower() in (r['source_url'] or '').lower():
            return r
    return rows[-1] if rows else None


def paper_dump(pid, want_qp=True, want_ms=True):
    p = c.execute("""SELECT p.*, d.title, d.year, d.paper_code FROM paper p
                     JOIN document d ON d.id=p.document_id WHERE p.id=?""", (pid,)).fetchone()
    qrev = pick_revision(p['document_id'], p['paper_no'])
    print(f"##### PAPER {pid} {p['paper_no']} year={p['year']} title={p['title']}")
    if qrev:
        print(f"  QP url: {qrev['source_url']}")
    qs = c.execute("""
      SELECT q.id, q.number_label, q.marks, q.page_from, q.page_to, q.parent_id, q.display_order,
             tn.code, substr(replace(q.stem_text,char(10),' '),1,110) st
      FROM question q LEFT JOIN question_taxonomy qt ON qt.question_id=q.id
      LEFT JOIN taxonomy_node tn ON tn.id=qt.node_id
      WHERE q.paper_id=? ORDER BY q.display_order""", (pid,)).fetchall()
    for q in qs:
        par = f" parent={q['parent_id']}" if q['parent_id'] else ''
        print(f"  Q{q['id']} #{q['number_label']} {q['marks']}mk p{q['page_from']}-{q['page_to']} [{q['code'] or '-'}]{par} | {q['st']}")
    ms = c.execute("""SELECT ms.id, ms.document_id FROM mark_scheme ms
                      WHERE ms.matched_paper_document_id=?""", (p['document_id'],)).fetchone()
    if ms and want_ms:
        mrev = pick_revision(ms['document_id'], p['paper_no'])
        if mrev:
            print(f"  MS url: {mrev['source_url']}")
            path = storage_path(mrev['storage_key'])
            if path.exists():
                print('----- MS TEXT -----')
                print(pdf_text(path))
    if want_qp and qrev:
        path = storage_path(qrev['storage_key'])
        if path.exists():
            print('----- QP TEXT -----')
            print(pdf_text(path))
    print()


if __name__ == '__main__':
    args = sys.argv[1:]
    flags = {a for a in args if a.startswith('--')}
    for a in args:
        if a.startswith('--'):
            continue
        paper_dump(int(a), '--noqp' not in flags, '--noms' not in flags)
