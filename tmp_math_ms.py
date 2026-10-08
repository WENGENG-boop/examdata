"""Print the mark-scheme text of a paper (skipping guidance pages)."""
import sys
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
c = sqlite3.connect(str(ROOT / '.data' / 'examdata.db'))
c.row_factory = sqlite3.Row


def storage_path(key):
    return ROOT / '.data' / 'artifacts' / key


def collapse(txt):
    return '\n'.join(ln.strip() for ln in txt.split('\n') if ln.strip())


def pick_revision(document_id, paper_no):
    rows = c.execute("""SELECT dr.id, dr.source_url, a.storage_key, a.mime
      FROM document_revision dr JOIN artifact a ON a.id=dr.artifact_id
      WHERE dr.document_id=?""", (document_id,)).fetchall()
    for r in rows:
        if paper_no and paper_no.lower() in (r['source_url'] or '').lower():
            return r
    return rows[-1] if rows else None


def main():
    import fitz
    pid = int(sys.argv[1])
    start = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    p = c.execute("SELECT * FROM paper WHERE id=?", (pid,)).fetchone()
    ms = c.execute("SELECT ms.document_id FROM mark_scheme ms WHERE ms.matched_paper_document_id=?",
                   (p['document_id'],)).fetchone()
    if not ms:
        print('no MS'); return
    rev = pick_revision(ms['document_id'], p['paper_no'])
    print(f"### paper {pid} {p['paper_no']} MS {rev['source_url']}")
    doc = fitz.open(str(storage_path(rev['storage_key'])))
    for i in range(start, doc.page_count):
        t = collapse(doc[i].get_text('text'))
        if t:
            print(f'--- p{i + 1} ---')
            print(t)


main()
