"""Dump PDF text at question region bboxes. Read-only probe."""
import json
import sqlite3
import sys
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parent
db = sqlite3.connect(ROOT / '.data' / 'examdata.db')

qids = [int(x) for x in sys.argv[1:]]
for qid in qids:
    r = db.execute('''SELECT q.attrs, q.number_label, q.marks, d.current_revision_id, d.title
        FROM question q JOIN paper p ON p.id=q.paper_id JOIN document d ON d.id=p.document_id
        WHERE q.id=?''', (qid,)).fetchone()
    attrs = json.loads(r[0] or '{}')
    rev_id = r[3]
    art = db.execute('SELECT a.storage_key FROM document_revision dr JOIN artifact a ON a.id=dr.artifact_id WHERE dr.id=?', (rev_id,)).fetchone()
    path = ROOT / '.data' / 'artifacts' / art[0]
    doc = fitz.open(path)
    print(f'==== qid {qid} | label {r[1]!r} | {r[2]}mk | {r[4]}')
    for reg in attrs.get('regions', [])[:3]:
        page = doc[reg['page'] - 1]
        text = page.get_text('text', clip=fitz.Rect(reg['bbox']))
        print(f'  -- page {reg["page"]} bbox {[round(x,1) for x in reg["bbox"]]}:')
        for line in text.splitlines():
            if line.strip():
                print('     |', line)
    doc.close()
