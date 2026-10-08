"""用新代码验证全部 183 行历史失败记录：应全部变成 typed 或 None+error。"""
import re
import sys

sys.path.insert(0, '.')
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from examdata.core.config import get_settings
from examdata.core.models import Artifact, Document, DocumentRevision
from examdata.parsing.content_classify import classify_content

fails = []
for line in open('tmp_classify_scan.log', encoding='utf-8'):
    m = re.match(r"FAIL doc=(\d+) (\S+) (.*) err=(.*) pages=(\d+)", line.strip())
    if m:
        fails.append(int(m.group(1)))

eng = create_engine('sqlite:///.data/examdata.db')
settings = get_settings()
with Session(eng) as s:
    rows = s.execute(
        select(Document.id, Artifact.storage_key, Artifact.mime)
        .join(DocumentRevision, DocumentRevision.document_id == Document.id)
        .join(Artifact, Artifact.id == DocumentRevision.artifact_id)
        .where(Document.id.in_(sorted(set(fails))))
    ).all()

by_doc = {}
for did, key, mime in rows:
    if not (str(mime or '').startswith('application/pdf') or key.lower().endswith('.pdf')):
        continue
    by_doc.setdefault(did, []).append(key)

still_fail = []
typed = 0
unreadable = 0
checked = 0
for did in fails:
    for key in by_doc.get(did, []):
        checked += 1
        ev = classify_content(settings.artifacts_dir / key)
        if ev.doc_type is None:
            if ev.error:
                unreadable += 1
                print(f"UNREADABLE doc={did} {key.split('/')[-1][:60]} err={ev.error}")
            else:
                still_fail.append((did, key))
                print(f"STILL-FAIL doc={did} {key}")
        else:
            typed += 1

print(f"\nDONE checked={checked} typed={typed} unreadable={unreadable} still_fail={len(still_fail)}")
