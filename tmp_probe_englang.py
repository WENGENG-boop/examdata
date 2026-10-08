"""验证：englang 1911 修复后 anchors + index_questions。"""
import sys
sys.path.insert(0, 'src')
import pymupdf
from examdata.core.config import get_settings
from examdata.core.db import get_session_factory, init_db
from examdata.core.models import Document, DocumentRevision
from examdata.edexcel_papers.pipeline import _artifact_path
from examdata.paperqa.locator import _anchors, locate, index_questions, LocationError

init_db()
session = get_session_factory()()
settings = get_settings()
doc = session.get(Document, 1911)
rev = session.get(DocumentRevision, doc.current_revision_id)
path = _artifact_path(session, settings, rev.artifact_id)
data = open(path, 'rb').read()
pdf = pymupdf.open(stream=data, filetype='pdf')
anchors, end = _anchors(pdf, 'qp')
print('anchors:', [(a.path, a.page, round(a.y, 1)) for a in anchors])
print('end:', end)
for a in anchors:
    try:
        clips = locate(pdf, a.path, 'qp')
        print(f'  locate({a.path!r}) -> pages {[p + 1 for p, _ in clips]}')
    except LocationError as exc:
        print(f'  locate({a.path!r}) FAIL {exc}')
try:
    idx = index_questions(data, 'qp')
    print(f'INDEX_OK q={len(idx)} paths={[e["question"] for e in idx]}')
except LocationError as exc:
    print('INDEX_FAIL', exc)
pdf.close()
session.close()
