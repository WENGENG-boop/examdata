"""englang 1911 spans 调试: 找出 clips>25 的路径及原因。"""
import sys
sys.path.insert(0, 'src')
import pymupdf
from examdata.core.config import get_settings
from examdata.core.db import get_session_factory, init_db
from examdata.core.models import Document, DocumentRevision
from examdata.edexcel_papers.pipeline import _artifact_path
from examdata.paperqa.locator import _anchors, locate, LocationError

init_db()
session = get_session_factory()()
settings = get_settings()
doc = session.get(Document, 1911)
rev = session.get(DocumentRevision, doc.current_revision_id)
path = _artifact_path(session, settings, rev.artifact_id)
pdf = pymupdf.open(path)
print('pages:', len(pdf))
anchors, end = _anchors(pdf, 'qp')
print('end:', end)
print('anchors:', [(a.path, a.page, round(a.y, 1)) for a in anchors])
paths = list(dict.fromkeys(a.path for a in anchors))
for p in paths:
    try:
        clips = locate(pdf, p, 'qp')
        tag = 'SPAN' if len(clips) > 25 else 'ok'
        print(f'{tag} {p}: {len(clips)} clips, pages {clips[0][0]}..{clips[-1][0]}')
    except LocationError as exc:
        print(f'FAIL {p}: {exc}')
pdf.close()
session.close()
