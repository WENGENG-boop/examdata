"""Dump context for maths pending questions using the actual PDF page text.

Picks the document_revision whose source_url matches the paper code, so that
mislabelled documents (title/paper_code drift) still resolve to the right PDF.
"""
import re
import sys
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / '.data' / 'examdata.db'
c = sqlite3.connect(str(DB))
c.row_factory = sqlite3.Row


def storage_path(key):
    return ROOT / '.data' / 'artifacts' / key


def pdf_text(path, page_from=None, page_to=None):
    import fitz
    doc = fitz.open(str(path))
    out = []
    lo = max(1, page_from or 1)
    hi = min(doc.page_count, page_to or doc.page_count)
    for p in range(lo, hi + 1):
        out.append(f'--- page {p} ---')
        out.append(doc[p - 1].get_text('text'))
    doc.close()
    return '\n'.join(out)


def pick_revision(document_id, paper_no):
    """Prefer the revision whose source_url contains the paper code."""
    rows = c.execute("""
      SELECT dr.id, dr.source_url, a.storage_key, a.mime
      FROM document_revision dr JOIN artifact a ON a.id=dr.artifact_id
      WHERE dr.document_id=?""", (document_id,)).fetchall()
    best = None
    for r in rows:
        url = (r['source_url'] or '').lower()
        if paper_no and paper_no.lower() in url:
            best = r
            break
    if best is None and rows:
        best = rows[-1]
    return best


def paper_info(pid):
    return c.execute("""
      SELECT p.id, p.document_id, p.paper_no, p.marks_total, d.title, d.year
      FROM paper p JOIN document d ON d.id=p.document_id WHERE p.id=?""", (pid,)).fetchone()


def ms_revision_for_paper(pid, paper_no):
    row = c.execute("""
      SELECT ms.id, ms.document_id FROM mark_scheme ms
      WHERE ms.matched_paper_document_id=(SELECT document_id FROM paper WHERE id=?)""", (pid,)).fetchone()
    if not row:
        # fall back: any mark_scheme whose document title mentions the paper code
        return None, None
    rev = pick_revision(row['document_id'], paper_no)
    return row['id'], rev


def ms_section(ms_path, number_label):
    """Print the MS text block for a given question number."""
    import fitz
    doc = fitz.open(str(ms_path))
    full = []
    for i in range(doc.page_count):
        full.append((i + 1, doc[i].get_text('text')))
    doc.close()
    num = re.sub(r'[^0-9a-zA-Z]', '', str(number_label or ''))
    # find pages mentioning "Question <num>"
    hits = []
    for pno, txt in full:
        for m in re.finditer(r'(?m)^\s*Question\s+(\d+)\b', txt):
            if m.group(1) == num:
                hits.append((pno, txt))
                break
    return hits, full


def show(qid, ms_pages=True):
    q = c.execute("SELECT * FROM question WHERE id=?", (qid,)).fetchone()
    if not q:
        print(f'Q {qid} NOT FOUND')
        return
    pinfo = paper_info(q['paper_id'])
    pno = pinfo['paper_no']
    print(f"===== Q {qid} paper={q['paper_id']} {pno} ({pinfo['year']}) "
          f"label={q['number_label']} marks={q['marks']} pages={q['page_from']}-{q['page_to']} parent={q['parent_id']}")
    qrev = pick_revision(pinfo['document_id'], pno)
    if qrev and qrev['mime'] and 'pdf' in qrev['mime']:
        p = storage_path(qrev['storage_key'])
        if p.exists():
            print(f'--- QP TEXT ({pno}) ---')
            print(pdf_text(p, q['page_from'], q['page_to']))
    msid, msrev = ms_revision_for_paper(q['paper_id'], pno)
    if msrev:
        p = storage_path(msrev['storage_key'])
        print(f'--- MS revision {msrev["id"]} url={msrev["source_url"]} ---')
        if ms_pages and p.exists():
            hits, full = ms_section(p, q['number_label'])
            if hits:
                for pno_, txt in hits[:1]:
                    i = txt.find(f'Question {re.sub(r"[^0-9a-zA-Z]", "", str(q["number_label"]))}')
                    print(f'[MS page {pno_}]')
                    print(txt[max(0, i - 200): i + 2500])
            else:
                print('(no "Question N" heading found in MS)')
    else:
        print('(no MS matched)')
    print('--- siblings ---')
    for sb in c.execute("""
      SELECT q.id, q.number_label, q.marks, substr(replace(q.stem_text,char(10),' '),1,90) st, tn.code
      FROM question q LEFT JOIN question_taxonomy qt ON qt.question_id=q.id
      LEFT JOIN taxonomy_node tn ON tn.id=qt.node_id
      WHERE q.paper_id=? ORDER BY q.display_order""", (q['paper_id'],)):
        print(f"  sib {sb['id']} #{sb['number_label']} {sb['marks']}mk [{sb['code'] or '-'}] {sb['st']}")
    print()


if __name__ == '__main__':
    args = sys.argv[1:]
    for a in args:
        show(int(a))
