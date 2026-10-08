"""doc 1633 (accounting MS) 影响核实：落库条目 vs 旧/新 locator 与 table 策略（只读）。"""
import sqlite3
import sys

sys.path.insert(0, 'src')

db = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
row = db.execute(
    "select id, title, doc_type, current_revision_id from document where id=1633"
).fetchone()
print('doc:', row)
ms = db.execute(
    "select id, matched_paper_document_id, match_confidence, match_method, parse_run_id"
    " from mark_scheme where document_id=1633"
).fetchall()
print('mark_scheme rows:', ms)
stored_paths = set()
for ms_id, matched, conf, method, run in ms:
    paths = [
        r[0]
        for r in db.execute(
            "select number_path from mark_scheme_entry where mark_scheme_id=?", (ms_id,)
        )
    ]
    stored_paths.update(p for p in paths if p)
    print(f'  ms_id={ms_id} matched_doc={matched} conf={conf} method={method} run={run} entries={len(paths)}')

matched = ms[0][1] if ms else None
qpaths = []
if matched:
    qp = db.execute("select id from paper where document_id=?", (matched,)).fetchone()
    print('QP paper:', qp)
    if qp:
        qpaths = [
            r[0]
            for r in db.execute(
                "select number_path from question where paper_id=? order by display_order",
                (qp[0],),
            )
        ]
print('QP paths n=', len(qpaths), qpaths[:40])
print('stored MS paths n=', len(stored_paths), sorted(stored_paths)[:40])

rev = db.execute(
    "select artifact_id from document_revision where id=?", (row[3],)
).fetchone()
key = db.execute("select storage_key from artifact where id=?", (rev[0],)).fetchone()[0]
data = open('.data/artifacts/' + key, 'rb').read()

import pymupdf  # noqa: E402

from examdata.edexcel_papers.pipeline import _ms_anchors, _ms_index_from_table  # noqa: E402
from examdata.paperqa import locator  # noqa: E402
from examdata.paperqa.locator import index_questions  # noqa: E402

wanted = set(qpaths)


def kept(items):
    return {
        it['question']
        for it in items
        if it.get('question') in wanted and it.get('regions')
    }


orig = locator._numeric_row
locator._numeric_row = lambda *a, **k: False
try:
    old_stock = index_questions(data, 'ms')
    print('old stock ok:', len(old_stock))
except Exception as exc:
    old_stock = []
    print('old stock err:', type(exc).__name__, exc)
finally:
    locator._numeric_row = orig

try:
    new_stock = index_questions(data, 'ms')
    print('new stock ok:', len(new_stock))
except Exception as exc:
    new_stock = []
    print('new stock err:', type(exc).__name__, exc)

with pymupdf.open(stream=data, filetype='pdf') as pdf:
    table = _ms_index_from_table(pdf, _ms_anchors(pdf, wanted), wanted)

old_f = [it for it in old_stock if it.get('question') in wanted and it.get('regions')]
new_f = [it for it in new_stock if it.get('question') in wanted and it.get('regions')]
old_keep, new_keep, table_keep = kept(old_stock), kept(new_stock), kept(table)
print('old stock kept:', len(old_keep), sorted(old_keep)[:50])
print('new stock kept:', len(new_keep), sorted(new_keep)[:50])
print('table kept:', len(table_keep), sorted(table_keep)[:50])
old_src = 'table' if len(table) >= len(old_f) else 'locator'
new_src = 'table' if len(table) >= len(new_f) else 'locator'
print('old chosen source:', old_src)
print('new chosen source:', new_src)
old_chosen = table_keep if old_src == 'table' else old_keep
new_chosen = table_keep if new_src == 'table' else new_keep
print('stored vs old_chosen equal:', stored_paths == old_chosen)
print('stored vs new_chosen equal:', stored_paths == new_chosen)
print('old_chosen - stored:', sorted(old_chosen - stored_paths)[:20])
print('stored - old_chosen:', sorted(stored_paths - old_chosen)[:20])
