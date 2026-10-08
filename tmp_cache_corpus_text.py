"""把全库 PDF 前两页文本缓存到 jsonl，供分类规则离线迭代。"""
import json
import sys

sys.path.insert(0, '.')
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from examdata.core.config import get_settings
from examdata.core.models import Artifact, Document, DocumentRevision, Subject
from examdata.parsing.pdfdoc import load_pdf

eng = create_engine('sqlite:///.data/examdata.db')
settings = get_settings()
with Session(eng) as s:
    rows = s.execute(
        select(Document.id, Document.title, Document.doc_type, Artifact.storage_key, Artifact.mime, Subject.code)
        .select_from(Document)
        .join(DocumentRevision, DocumentRevision.document_id == Document.id)
        .join(Artifact, Artifact.id == DocumentRevision.artifact_id)
        .join(Subject, Subject.id == Document.subject_id)
    ).all()

out = open('tmp_corpus_text.jsonl', 'w', encoding='utf-8')
n = 0
for did, title, dtype, key, mime, scode in rows:
    if not (str(mime or '').startswith('application/pdf') or key.lower().endswith('.pdf')):
        continue
    try:
        doc = load_pdf(settings.artifacts_dir / key, max_pages=2)
        text = '\n'.join(pg.text for pg in doc.pages[:2])[:6000]
        pages = len(doc.pages)
    except Exception as exc:
        text = ''
        pages = -1
        title = title + f' [LOAD_ERR {type(exc).__name__}]'
    rec = {'doc_id': did, 'subject': scode, 'title': title, 'db_type': dtype, 'text': text, 'pages': pages}
    out.write(json.dumps(rec, ensure_ascii=False) + '\n')
    n += 1
    if n % 200 == 0:
        print(f'  ... {n} cached', flush=True)
out.close()
print(f'DONE cached={n}')
