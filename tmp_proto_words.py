"""原型: 从 rawdict 重建解码词表, 复刻 _anchors 主循环, 看 4 张密码卷能否出锚点。"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'src'))

import pymupdf  # noqa: E402

from examdata.core.config import get_settings  # noqa: E402
from examdata.core.db import get_session_factory, init_db  # noqa: E402
from examdata.core.models import Document, DocumentRevision  # noqa: E402
from examdata.edexcel_papers.pipeline import _artifact_path  # noqa: E402

TARGETS = {3254: 'wfm03-01', 3258: 'wfm02-01', 3265: '6665a-01', 3299: 'WME01'}


def decode_char(c):
    o = ord(c)
    if o in (0x09, 0x0A, 0x0D, 0x20) or o < 0x03 or o > 0x61:
        return c
    return chr(o + 0x1D)


def decoded_words(page):
    out = []
    rd = page.get_text('rawdict')
    for b in rd['blocks']:
        if b['type'] != 0:
            continue
        for line in b['lines']:
            cur = None
            for sp in line['spans']:
                for ch in sp['chars']:
                    c = decode_char(ch['c'])
                    if c.isspace():
                        if cur is not None:
                            out.append(cur)
                            cur = None
                        continue
                    bb = ch['bbox']
                    if cur is None:
                        cur = [bb[0], bb[1], bb[2], bb[3], c]
                    else:
                        cur[0] = min(cur[0], bb[0])
                        cur[1] = min(cur[1], bb[1])
                        cur[2] = max(cur[2], bb[2])
                        cur[3] = max(cur[3], bb[3])
                        cur[4] += c
            if cur is not None:
                out.append(cur)
    return [(w[0], w[1], w[2], w[3], w[4], 0, 0, 0) for w in out]


def main() -> None:
    init_db()
    session = get_session_factory()()
    settings = get_settings()
    try:
        for doc_id, code in TARGETS.items():
            doc = session.get(Document, doc_id)
            revision = session.get(DocumentRevision, doc.current_revision_id)
            path = _artifact_path(session, settings, revision.artifact_id)
            pdf = pymupdf.open(path)
            anchors = []
            main = 0
            sub = ''
            for index, page in enumerate(pdf):
                if index == 0:
                    continue
                bounds = page.rect
                words = sorted(decoded_words(page), key=lambda w: (round(w[1] / 3), w[0]))
                for word in words:
                    x, y, _, _, text = word[0], word[1], word[2], word[3], word[4]
                    if not bounds.height * .04 < y < bounds.height * .9:
                        continue
                    stripped = text.lstrip('*')
                    if x < bounds.width * .125 and re.fullmatch(r'[1-9]\d{0,2}\.?', stripped):
                        number = int(stripped.rstrip('.'))
                        if number == main + 1 or (main and number == main):
                            main = number
                            sub = ''
                            anchors.append((str(main), index, round(y, 1)))
                    elif main and x < bounds.width * .20:
                        m = re.fullmatch(r'\(([a-z]+)\)', text)
                        if not m:
                            continue
                        part = m.group(1)
                        if len(part) == 1 and (part not in {'i', 'v', 'x'} or not sub or ord(part) == ord(sub) + 1):
                            sub = part
                            anchors.append((f'{main}({part})', index, round(y, 1)))
                        elif sub and re.fullmatch(r'[ivx]+', part):
                            anchors.append((f'{main}({sub})({part})', index, round(y, 1)))
            paths = list(dict.fromkeys(a[0] for a in anchors))
            print(f'=== {doc_id} {code}: anchors={len(anchors)} paths={len(paths)}')
            print('   first:', anchors[:6])
            print('   last :', anchors[-4:])
            pdf.close()
    finally:
        session.close()


if __name__ == '__main__':
    main()
