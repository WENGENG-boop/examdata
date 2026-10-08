"""决定性测量: Total 行的精确字符码 + 'B' 的来源 + 数字行上下文。"""
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'src'))

import pymupdf  # noqa: E402

from examdata.core.config import get_settings  # noqa: E402
from examdata.core.db import get_session_factory, init_db  # noqa: E402
from examdata.core.models import Document, DocumentRevision  # noqa: E402
from examdata.edexcel_papers.pipeline import _artifact_path  # noqa: E402

DOC_ID = 3254


def show_codes(label, s):
    print(f'  {label}: {s!r}')
    print('    codes:', ' '.join(f'{ord(c):02x}' for c in s))


def main() -> None:
    init_db()
    session = get_session_factory()()
    settings = get_settings()
    try:
        doc = session.get(Document, DOC_ID)
        revision = session.get(DocumentRevision, doc.current_revision_id)
        path = _artifact_path(session, settings, revision.artifact_id)
        pdf = pymupdf.open(path)

        print('=== find "(Total" (cipher \\x0b7RWDO) lines ===')
        found = 0
        for i in range(len(pdf)):
            t = pdf[i].get_text()
            start = 0
            while found < 6:
                j = t.find('\x0b7RWDO', start)
                if j < 0:
                    break
                line_start = t.rfind('\n', 0, j) + 1
                line_end = t.find('\n', j)
                if line_end < 0:
                    line_end = len(t)
                line = t[line_start:line_end]
                print(f' page {i+1}:')
                show_codes('line', line)
                found += 1
                start = j + 1
            if found >= 6:
                break

        print('=== find "TOTAL FOR PAPER" (cipher 727$/) ===')
        found = 0
        for i in range(len(pdf)):
            t = pdf[i].get_text()
            j = t.find('727$/')
            if j >= 0:
                line_start = t.rfind('\n', 0, j) + 1
                line_end = t.find('\n', j)
                if line_end < 0:
                    line_end = len(t)
                line = t[line_start:line_end]
                print(f' page {i+1}:')
                show_codes('line', line)
                found += 1
                if found >= 3:
                    break
        if not found:
            print('  no literal 727$/ found')

        print('=== "B" source: texttrace spans with many B ===')
        for i in (1, 5, 10):
            tt = pdf[i].get_texttrace()
            for span in tt:
                chars = span.get('chars', [])
                if not chars:
                    continue
                b = sum(1 for ch in chars if ch[0] == 0x42)
                if b > 20:
                    print(f' page {i+1} font={span.get("font")} size={round(span.get("size",0),1)} n={len(chars)} B={b}')
                    print('   sample gids:', [ch[1] for ch in chars[:12]])
                    print('   sample unis:', [hex(ch[0]) for ch in chars[:12]])
                    break

        print('=== question number line sample (cipher 1. = \\x14\\x11) ===')
        for i in range(1, 6):
            t = pdf[i].get_text()
            j = t.find('\x14\x11')
            if j >= 0:
                line_start = t.rfind('\n', 0, j) + 1
                line_end = t.find('\n', j)
                if line_end < 0:
                    line_end = len(t)
                print(f' page {i+1}:')
                show_codes('line', t[line_start:line_end])
                break

        print('=== decode test: apply +0x1D to [0x03..0x61] except 0x20 ===')
        def dec(s):
            out = []
            for c in s:
                o = ord(c)
                if o == 0x20:
                    out.append(' ')
                elif 0x03 <= o <= 0x61:
                    out.append(chr(o + 0x1D))
                else:
                    out.append(c)
            return ''.join(out)
        t2 = pdf[1].get_text()
        print(' ', repr(dec(t2[:400])))

        pdf.close()
    finally:
        session.close()


if __name__ == '__main__':
    main()
