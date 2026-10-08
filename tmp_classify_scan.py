import sys, time
sys.path.insert(0, '.')
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from examdata.core.config import get_settings
from examdata.core.models import Artifact, Document, DocumentRevision, Subject
from examdata.parsing.content_classify import classify_content

eng = create_engine('sqlite:///.data/examdata.db')
settings = get_settings()
with Session(eng) as s:
    rows = s.execute(
        select(Document.id, Document.title, Artifact.storage_key, Artifact.mime, Subject.code)
        .join(DocumentRevision, DocumentRevision.document_id == Document.id)
        .join(Artifact, Artifact.id == DocumentRevision.artifact_id)
        .join(Subject, Subject.id == Document.subject_id)
    ).all()

t0 = time.time()
checked = 0
failures = []
for did, title, key, mime, scode in rows:
    if not (str(mime or '').startswith('application/pdf') or key.lower().endswith('.pdf')):
        continue
    checked += 1
    if checked % 200 == 0:
        print(f'  ... {checked} checked, {len(failures)} failures, {time.time()-t0:.0f}s', flush=True)
    ev = classify_content(settings.artifacts_dir / key)
    if ev.doc_type is None:
        failures.append((did, scode, title[:60], ev.error, ev.pages_scanned))
        print(f'FAIL doc={did} {scode} {title[:50]!r} err={ev.error} pages={ev.pages_scanned}', flush=True)
print(f'DONE checked={checked} failures={len(failures)} elapsed={time.time()-t0:.0f}s')
