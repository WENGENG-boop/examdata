"""只读测量: 密码字体文档的精确映射 + rawdict 重建可行性 + search_for 行为。

对 maths 4 张密码卷 (3254 wfm03-01, 3258 wfm02-01, 3265 6665a-01, 3299 WME01)
和 math18 1336 (wma02-01) 输出:
- get_text() 里控制字符计数 (前 3 页 / 全文档)
- rawdict 里前几个 span 的字符码 (确认映射)
- 用解码函数重建一段文本样本 (第 2 页前 300 字符)
- search_for("TOTAL FOR PAPER") 与密文变体的结果
- rawdict 带 clip 的行为
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'src'))

import pymupdf  # noqa: E402

from examdata.core.config import get_settings  # noqa: E402
from examdata.core.db import get_session_factory, init_db  # noqa: E402
from examdata.core.models import Document, DocumentRevision  # noqa: E402
from examdata.edexcel_papers.pipeline import _artifact_path  # noqa: E402

TARGETS = {
    3254: 'wfm03-01',
    3258: 'wfm02-01',
    3265: '6665a-01',
    3299: 'WME01',
    1336: 'wma02-01',
    2441: 'wgk01-01',
}


def decode(s: str) -> str:
    out = []
    for c in s:
        o = ord(c)
        if 0x03 <= o <= 0x61:
            out.append(chr(o + 0x1D))
        else:
            out.append(c)
    return ''.join(out)


def ctl_count(s: str) -> int:
    return sum(1 for c in s if ord(c) < 0x20 and c not in '\n\r\t')


def main() -> None:
    init_db()
    session = get_session_factory()()
    settings = get_settings()
    try:
        for doc_id, code in TARGETS.items():
            doc = session.get(Document, doc_id)
            print(f'===== doc {doc_id} {code} title={doc.title[:60] if doc else None}')
            if doc is None or doc.current_revision_id is None:
                print('  no revision')
                continue
            revision = session.get(DocumentRevision, doc.current_revision_id)
            path = _artifact_path(session, settings, revision.artifact_id) if revision else None
            if path is None:
                print('  no artifact')
                continue
            pdf = pymupdf.open(path)
            print(f'  pages={len(pdf)}')
            # control char counts
            full = ''.join(pdf[i].get_text() for i in range(len(pdf)))
            first3 = ''.join(pdf[i].get_text() for i in range(min(3, len(pdf))))
            print(f'  ctl full={ctl_count(full)}/{len(full)}  first3={ctl_count(first3)}/{len(first3)}')
            # rawdict sample on page 2 (index 1)
            if len(pdf) > 1:
                rd = pdf[1].get_text('rawdict')
                codes = []
                for block in rd['blocks']:
                    if block['type'] != 0:
                        continue
                    for line in block['lines']:
                        for span in line['spans']:
                            for ch in span['chars']:
                                codes.append(ch['c'])
                                if len(codes) >= 80:
                                    break
                            if len(codes) >= 80:
                                break
                        if len(codes) >= 80:
                            break
                    if len(codes) >= 80:
                        break
                print('  rawdict first chars (ord):', [hex(ord(c)) for c in codes[:40]])
                raw_text = ''.join(codes)
                print('  raw sample:', repr(raw_text[:60]))
                print('  decoded  :', repr(decode(raw_text)[:60]))
            # get_text() decoded sample
            t = pdf[1].get_text() if len(pdf) > 1 else ''
            print('  text() raw  :', repr(t[:80]))
            print('  text() dec  :', repr(decode(t)[:80]))
            # search_for
            found_plain = pdf[0].search_for('TOTAL FOR PAPER')
            cipher_head = ''.join(chr(ord(c) - 0x1D) for c in 'TOTAL FOR PAPER')
            print('  search_for plain:', len(found_plain), ' cipher:', repr(cipher_head))
            hits = 0
            for i in range(len(pdf)):
                hits += len(pdf[i].search_for(cipher_head))
            print('  search_for cipher hits (whole doc):', hits)
            # rawdict with clip
            clip = pymupdf.Rect(30, 60, 560, 300)
            try:
                rd2 = pdf[1].get_text('rawdict', clip=clip)
                n = sum(len(sp['chars']) for b in rd2['blocks'] if b['type'] == 0
                        for l in b['lines'] for sp in l['spans'])
                print('  rawdict clip chars:', n)
            except Exception as exc:
                print('  rawdict clip failed:', type(exc).__name__, exc)
            # get_text clip control count
            tc = pdf[1].get_text(clip=clip)
            print('  text(clip) ctl:', ctl_count(tc), 'sample:', repr(tc[:60]))
            pdf.close()
    finally:
        session.close()


if __name__ == '__main__':
    main()
