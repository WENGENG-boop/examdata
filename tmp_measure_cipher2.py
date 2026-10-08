"""密码字体 ground truth: 字体 CMap + get_texttrace glyph + 字符码频率。

目的: 确定精确解码规则 (特别是 0x20 是空格还是 '=', 以及范围边界)。
"""
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

DOC_ID = 3254  # wfm03-01


def main() -> None:
    init_db()
    session = get_session_factory()()
    settings = get_settings()
    try:
        doc = session.get(Document, DOC_ID)
        revision = session.get(DocumentRevision, doc.current_revision_id)
        path = _artifact_path(session, settings, revision.artifact_id)
        pdf = pymupdf.open(path)

        print('--- fonts page 2 ---')
        for f in pdf.get_page_fonts(1):
            print(' ', f)

        print('--- ToUnicode CMap of each font ---')
        seen = set()
        for f in pdf.get_page_fonts(1):
            xref = f[0]
            if xref in seen:
                continue
            seen.add(xref)
            keys = pdf.xref_get_keys(xref)
            print(f'font xref={xref} keys={keys}')
            try:
                tu = pdf.xref_get_key(xref, 'ToUnicode')
                print('  ToUnicode:', tu)
            except Exception as exc:
                print('  ToUnicode err:', exc)

        print('--- texttrace sample (page 2, first 3 spans) ---')
        tt = pdf[1].get_texttrace()
        shown = 0
        for span in tt:
            if not span.get('chars'):
                continue
            chars = span['chars']
            print(' span font=', span.get('font'), 'size=', round(span.get('size', 0), 1))
            for ch in chars[:40]:
                uni, gid = ch[0], ch[1]
                print(f'   gid={gid:5d} uni=U+{uni:04X} {chr(uni)!r}')
            shown += 1
            if shown >= 3:
                break

        print('--- char code frequency (whole doc) ---')
        cnt = Counter()
        for i in range(len(pdf)):
            t = pdf[i].get_text()
            cnt.update(t)
        interesting = [c for c in cnt if ord(c) < 0x80]
        for c in sorted(interesting, key=lambda c: -cnt[c])[:40]:
            print(f'  U+{ord(c):04X} {c!r}: {cnt[c]}')

        print('--- does 0x3D "=" appear? 0x20 space? ---')
        print('  0x3D count:', cnt.get('=', 0))
        print('  0x20 count:', cnt.get(' ', 0))
        print('  0x03 count:', cnt.get(chr(3), 0))

        print('--- texttrace chars for clip with "cosh" (page 2) ---')
        # find the cosh line: search decoded text
        for i in range(1, 4):
            t = pdf[i].get_text()
            if 'FRVK' in t:
                # dump trace chars where uni in cipher range around F R V K
                tt = pdf[i].get_texttrace()
                flat = []
                for span in tt:
                    for ch in span.get('chars', []):
                        flat.append((ch[0], ch[1]))
                idxs = [j for j, (u, g) in enumerate(flat) if u == ord('F')]
                for j in idxs[:3]:
                    seq = flat[max(0, j - 6):j + 26]
                    print(f'  page {i+1} around j={j}:')
                    for u, g in seq:
                        print(f'    gid={g:5d} uni=U+{u:04X} {chr(u)!r}')
                break
        pdf.close()
    finally:
        session.close()


if __name__ == '__main__':
    main()
