"""希腊语试卷测量: Ερώτηση 词与数字 token 的精确几何关系 + NFC 检查。"""
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'src'))

import pymupdf  # noqa: E402

from examdata.core.config import get_settings  # noqa: E402
from examdata.core.db import get_session_factory, init_db  # noqa: E402
from examdata.core.models import Document, DocumentRevision  # noqa: E402
from examdata.edexcel_papers.pipeline import _artifact_path  # noqa: E402

DOC_IDS = [2441, 2442, 2446, 2450, 2458, 2461, 2463, 2467, 2470, 2473, 2481, 2483, 2487]
GREEK = unicodedata.normalize('NFC', 'Ερώτηση')


def main() -> None:
    init_db()
    session = get_session_factory()()
    settings = get_settings()
    nfc_forms = {}
    gap_stats = []
    x0_stats = []
    try:
        for doc_id in DOC_IDS[:3]:
            doc = session.get(Document, doc_id)
            revision = session.get(DocumentRevision, doc.current_revision_id)
            path = _artifact_path(session, settings, revision.artifact_id)
            pdf = pymupdf.open(path)
            print(f'===== doc {doc_id} pages={len(pdf)}')
            for i in range(len(pdf)):
                bounds = pdf[i].rect
                words = sorted(pdf[i].get_text('words'), key=lambda w: (round(w[1] / 3), w[0]))
                for j, w in enumerate(words):
                    x0, y0, x1, y1, text = w[0], w[1], w[2], w[3], w[4]
                    norm = unicodedata.normalize('NFC', text)
                    if 'Ερ' in norm or 'Ερ' in text:
                        nfc_forms[text] = nfc_forms.get(text, 0) + 1
                        if j + 1 < len(words):
                            nxt = words[j + 1]
                            gap = nxt[0] - x1
                            dy = abs(nxt[1] - y0)
                            if dy < 6:
                                gap_stats.append((doc_id, i + 1, round(gap, 2),
                                                  round(nxt[0], 1), nxt[4][:12]))
                                x0_stats.append(nxt[0])
            # sample: first few lines with Ερώτηση
            print('  NFC forms:', nfc_forms)
            pdf.close()
            break  # 第一张足够
    finally:
        session.close()
    print('gap samples (doc, page, gap, next_x0, next_text):')
    for row in gap_stats[:25]:
        print(' ', row)
    if x0_stats:
        print('next x0 min/max:', min(x0_stats), max(x0_stats))
    # 检查 NFC 与 NFD 差异
    print('NFC form == GREEK:', unicodedata.normalize('NFC', GREEK) == GREEK)


if __name__ == '__main__':
    main()
