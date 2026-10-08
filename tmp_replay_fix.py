"""重放验证：修复后 13 张 Invalid + 10 张 greek summary + englang 1911 的解析状态。"""
import sys
sys.path.insert(0, 'src')
import pymupdf
from examdata.core.config import get_settings
from examdata.core.db import get_session_factory, init_db
from examdata.core.models import Document, DocumentRevision
from examdata.edexcel_papers.pipeline import _artifact_path
from examdata.paperqa.locator import _anchors, locate, index_questions, LocationError

DOCS = [1754, 3190, 3214, 3239, 3265, 3298, 3305, 3310, 471, 774, 802, 951, 1120,
        2441, 2450, 2458, 2461, 2463, 2467, 2470, 2473, 2481, 2483, 1911]

init_db()
session = get_session_factory()()
settings = get_settings()
ok = 0
for doc_id in DOCS:
    doc = session.get(Document, doc_id)
    rev = session.get(DocumentRevision, doc.current_revision_id)
    path = _artifact_path(session, settings, rev.artifact_id)
    data = open(path, 'rb').read()
    try:
        idx = index_questions(data, 'qp')
        print(f'== doc {doc_id} {doc.paper_code}: INDEX_OK q={len(idx)}')
        ok += 1
        continue
    except LocationError as exc:
        first = str(exc)[:80]
    pdf = pymupdf.open(path)
    anchors, _ = _anchors(pdf, 'qp')
    paths = list(dict.fromkeys(a.path for a in anchors))
    fails = []
    maxspan = 0
    for p in paths:
        try:
            clips = locate(pdf, p, 'qp')
            maxspan = max(maxspan, len(clips))
        except LocationError as exc:
            fails.append((p, str(exc)[:70]))
    print(f'== doc {doc_id} {doc.paper_code}: INDEX_FAIL first="{first}" | locate fails={len(fails)} maxspan={maxspan}')
    for p, msg in fails[:6]:
        print(f'    {p}: {msg}')
    pdf.close()
print(f'=== TOTAL INDEX_OK {ok}/{len(DOCS)}')
session.close()
