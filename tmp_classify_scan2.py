"""全库 PDF 分类扫描 v2：dump 每行完整判定结果（before/after 对比用）。

用法: python tmp_classify_scan2.py <label>   -> tmp_classify_<label>.jsonl
"""
import json
import sys
import time

sys.path.insert(0, '.')
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from examdata.core.config import get_settings
from examdata.core.models import Artifact, Document, DocumentRevision, Subject
from examdata.parsing.content_classify import classify_content

label = sys.argv[1] if len(sys.argv) > 1 else 'scan'
eng = create_engine('sqlite:///.data/examdata.db')
settings = get_settings()
with Session(eng) as s:
    rows = s.execute(
        select(Document.id, Document.title, Document.doc_type, Artifact.storage_key, Artifact.mime, Subject.code)
        .join(DocumentRevision, DocumentRevision.document_id == Document.id)
        .join(Artifact, Artifact.id == DocumentRevision.artifact_id)
        .join(Subject, Subject.id == Document.subject_id)
    ).all()

t0 = time.time()
checked = 0
failures = []
out = open(f'tmp_classify_{label}.jsonl', 'w', encoding='utf-8')
for did, title, dtype, key, mime, scode in rows:
    if not (str(mime or '').startswith('application/pdf') or key.lower().endswith('.pdf')):
        continue
    checked += 1
    if checked % 500 == 0:
        print(f'  ... {checked} checked, {len(failures)} failures, {time.time()-t0:.0f}s', flush=True)
    ev = classify_content(settings.artifacts_dir / key)
    rec = {
        'doc_id': did, 'key': key, 'subject': scode, 'title': title,
        'db_type': dtype, 'doc_type': ev.doc_type, 'confidence': ev.confidence,
        'error': ev.error, 'pages_scanned': ev.pages_scanned,
        'scores': ev.scores,
    }
    out.write(json.dumps(rec, ensure_ascii=False) + '\n')
    if ev.doc_type is None:
        failures.append((did, key, scode, title[:50], ev.error))
        print(f'FAIL doc={did} {scode} {title[:50]!r} err={ev.error}', flush=True)
out.close()
print(f'DONE {label} checked={checked} failures={len(failures)} elapsed={time.time()-t0:.0f}s')
