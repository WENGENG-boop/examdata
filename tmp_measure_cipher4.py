"""密码卷补充测量: 格式对比 + search_for 变体 + MS 文档是否同样加密 + words 行为。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'src'))

import pymupdf  # noqa: E402

from examdata.core.config import get_settings  # noqa: E402
from examdata.core.db import get_session_factory, init_db  # noqa: E402
from examdata.core.models import Document, DocumentRevision  # noqa: E402
from examdata.edexcel_papers.pipeline import _artifact_path, _paper_code_of  # noqa: E402

CIPHER = {3254: 'wfm03-01', 3258: 'wfm02-01', 3265: '6665a-01', 3299: 'WME01'}
NORMAL = {3190: 'normal-maths'}


def ctl_count(s):
    return sum(1 for c in s if ord(c) < 0x20 and c not in '\n\r\t')


def cipher(s):
    out = []
    for c in s:
        o = ord(c)
        if o == 0x20 or o < 0x21 or o > 0x7E:
            out.append(c)
        else:
            out.append(chr(o - 0x1D))
    return ''.join(out)


def main() -> None:
    init_db()
    session = get_session_factory()()
    settings = get_settings()

    def load(doc_id):
        doc = session.get(Document, doc_id)
        revision = session.get(DocumentRevision, doc.current_revision_id)
        path = _artifact_path(session, settings, revision.artifact_id)
        return doc, revision, path

    try:
        doc, revision, path = load(3254)
        pdf = pymupdf.open(path)
        print('=== search_for variants on doc 3254 ===')
        needle_plain = 'TOTAL FOR PAPER'
        needle_c20 = cipher(needle_plain)          # 0x20 spaces
        needle_c03 = ''.join('\x03' if c == ' ' else cipher(c) for c in needle_plain)
        for label, needle in (('plain', needle_plain), ('cipher-20', needle_c20), ('cipher-03', needle_c03)):
            hits = sum(len(pdf[i].search_for(needle)) for i in range(len(pdf)))
            print(f'  {label}: {hits}  needle={needle!r}')
        print()
        print('=== "for Question" cipher seq occurrences ===')
        seq = cipher('for Question')
        total = 0
        for i in range(len(pdf)):
            t = pdf[i].get_text()
            c = t.count(seq)
            if c:
                print(f'  page {i+1}: {c}')
            total += c
        print('  total:', total)
        print()
        print('=== "(Total" context (page 3, 300 chars before) ===')
        t3 = pdf[2].get_text()
        j = t3.find('\x0b7RWDO')
        if j >= 0:
            print(repr(t3[max(0, j-300):j+60]))
        print()
        print('=== words vs rawdict on page 2 left column ===')
        words = pdf[1].get_text('words')
        left = [w for w in words if w[0] < 90]
        print('  words count left:', len(left))
        for w in left[:20]:
            print('   ', round(w[0], 1), round(w[1], 1), repr(w[4]))
        print()
        print('=== words containing control chars? ===')
        bad = [w for w in words if any(ord(c) < 0x20 and c not in '\n\r\t' for c in w[4])]
        print('  words with ctl:', len(bad), bad[:5])
        pdf.close()

        print()
        print('=== normal doc 3190 "(Total" lines ===')
        doc, revision, path = load(3190)
        pdf = pymupdf.open(path)
        found = 0
        for i in range(len(pdf)):
            t = pdf[i].get_text()
            for line in t.split('\n'):
                if 'Total' in line:
                    print(f'  page {i+1}: {line!r}')
                    found += 1
                    if found >= 5:
                        break
            if found >= 5:
                break
        # underscore count in region text
        import re as _re
        us = sum(len(_re.findall(r'_{2,}', pdf[i].get_text())) for i in range(len(pdf)))
        print('  underscore runs:', us)
        pdf.close()

        print()
        print('=== MS docs for cipher papers ===')
        for qp_id, code in CIPHER.items():
            qp = session.get(Document, qp_id)
            ms_docs = [
                d for d in session.query(Document).filter(
                    Document.subject_id == qp.subject_id,
                    Document.series_id == qp.series_id,
                ).all()
                if d.id != qp_id and d.title and code.upper()[:5] in d.title.upper()
                and 'Mark scheme' in (d.title or '')
            ]
            print(f'  QP {qp_id} {code}: {len(ms_docs)} candidate MS')
            for ms in ms_docs[:4]:
                rev = session.get(DocumentRevision, ms.current_revision_id)
                p = _artifact_path(session, settings, rev.artifact_id) if rev else None
                if p is None:
                    print(f'    ms {ms.id} no artifact; title={ms.title[:70]}')
                    continue
                mpdf = pymupdf.open(p)
                ctl = sum(ctl_count(mpdf[i].get_text()) for i in range(min(3, len(mpdf))))
                print(f'    ms {ms.id} ctl(first3)={ctl} pages={len(mpdf)} title={ms.title[:70]}')
                mpdf.close()
    finally:
        session.close()


if __name__ == '__main__':
    main()
