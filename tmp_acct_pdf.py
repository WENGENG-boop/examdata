"""Read source PDF text for a question's paper.

usage:
  tmp_acct_pdf.py <qid> --info                 # print pdf path, page count
  tmp_acct_pdf.py <qid> --page N               # print page N (1-based)
  tmp_acct_pdf.py <qid> --pages A-B            # print pages A..B
  tmp_acct_pdf.py <qid> --find "phrase"        # print pages containing phrase (page numbers shown)
  tmp_acct_pdf.py <qid> --find "phrase" --context 400
"""
import sys
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
import pymupdf

ROOT = Path(__file__).resolve().parent
eng = create_engine(f"sqlite:///{ROOT / '.data' / 'examdata.db'}")
s = Session(eng)


def pdf_for_qid(qid):
    r = s.execute(text("""
      SELECT a.storage_key, p.id FROM question q
      JOIN paper p ON p.id=q.paper_id
      JOIN document d ON d.id=p.document_id
      JOIN document_revision dr ON dr.document_id=d.id
      JOIN artifact a ON a.id=dr.artifact_id
      WHERE q.id=:q ORDER BY dr.revision_no DESC LIMIT 1"""), {'q': qid}).fetchone()
    if not r:
        return None, None
    return ROOT / '.data' / 'artifacts' / r[0], r[1]


def main():
    qid = int(sys.argv[1])
    args = sys.argv[2:]
    path, pid = pdf_for_qid(qid)
    if path is None:
        print('no artifact for qid', qid)
        return
    print(f'# qid={qid} paper={pid} pdf={path}')
    doc = pymupdf.open(path)
    n = doc.page_count
    if '--info' in args or not args:
        print(f'# pages={n}')
        if not args:
            return
    if '--page' in args:
        pg = int(args[args.index('--page') + 1])
        print(f'===== page {pg}/{n} =====')
        print(doc[pg - 1].get_text())
    elif '--pages' in args:
        spec = args[args.index('--pages') + 1]
        a, b = spec.split('-')
        for pg in range(int(a), int(b) + 1):
            print(f'===== page {pg}/{n} =====')
            print(doc[pg - 1].get_text())
    elif '--find' in args:
        phrase = args[args.index('--find') + 1]
        ctx = 0
        if '--context' in args:
            ctx = int(args[args.index('--context') + 1])
        pl = phrase.lower()
        for i in range(n):
            t = doc[i].get_text()
            if pl in t.lower():
                print(f'===== page {i+1}/{n} =====')
                if ctx > 0:
                    pos = t.lower().find(pl)
                    print(t[max(0, pos - ctx):pos + len(phrase) + ctx])
                else:
                    print(t)


if __name__ == '__main__':
    main()
