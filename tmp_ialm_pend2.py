import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, '.')
from examdata.core import models as m
from examdata.tagging.corpus import load_points, unit_code_from_paper
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

con = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
cur = con.cursor()


def q(qid):
    return cur.execute(
        "select id, paper_id, parent_id, number_label, stem_text from question where id=?",
        (qid,)).fetchone()


def labels(qid):
    rows = cur.execute(
        """select t.code, qt.source, qt.confidence from question_taxonomy qt
           join taxonomy_node t on t.id=qt.node_id where qt.question_id=?""",
        (qid,)).fetchall()
    return [(r[0], r[1], round(r[2], 2) if r[2] is not None else None) for r in rows]


def ms(qid):
    rows = cur.execute(
        "select answer_text from mark_scheme_entry where question_id=?", (qid,)).fetchall()
    return [r[0] for r in rows]


print("===== A. taxonomy names =====")
for r in cur.execute(
        "select id, code, name from taxonomy_node where code like 'WMA02-%' "
        "or code like 'WMA01-%' or code like 'WDM01-%' order by id").fetchall():
    print(r)

print()
print("===== A2. unit nodes =====")
for r in cur.execute(
        "select id, code, name from taxonomy_node where id in (672) "
        "or name like '%Core Mathematics%' or name like '%Decision%'").fetchall():
    print(r)

print()
print("===== B. fresh unit check: batch rows vs unit_code_from_paper =====")
eng = create_engine(f"sqlite:///{Path('.data/examdata.db').resolve()}")
session = Session(eng)
rows = []
batch_files = sorted(Path('tmp_jev_untagged_batches/ial-maths/batches').glob('batch-*.jsonl'))
for f in batch_files:
    for line in open(f, encoding='utf-8'):
        rec = json.loads(line)
        qid = rec['question_id']
        unit = rec.get('unit_code')
        qq = session.get(m.Question, qid)
        p = session.get(m.Paper, qq.paper_id)
        d = session.get(m.Document, p.document_id) if p else None
        fresh = unit_code_from_paper(p.attrs if p else None, d.paper_code if d else None)
        rows.append((unit, qid, rec.get('number_label'), fresh,
                     [c.get('code') for c in (rec.get('current') or [])]))
import glob
from collections import Counter
print("batch unit counts:", Counter(r[0] for r in rows))
print("fresh unit counts:", Counter(r[3] for r in rows))
bad = [r for r in rows if r[3] != r[0]]
print("mismatches (batch unit != fresh):", len(bad))
for r in bad[:20]:
    print("  MISMATCH", r)
print()
print("--- all rows ---")
for r in rows:
    print(r)

print()
print("===== C. 57128/57129/57130 context =====")
for qid in [57128, 57129, 57130]:
    r = q(qid)
    if r is None:
        print(f"{qid} NOT FOUND")
        continue
    print(f"----- {qid} [{r[3]}] parent={r[2]} labs={labels(qid)}")
    print("STEM:", (r[4] or '').replace('\n', ' ')[:900])
    for mm in ms(qid):
        print("MS:", (mm or '').replace('\n', ' ')[:500])

print()
print("===== D. 60721-60727 full =====")
for qid in [60721, 60722, 60723, 60724, 60725, 60726, 60727]:
    r = q(qid)
    if r is None:
        print(f"{qid} NOT FOUND")
        continue
    print(f"----- {qid} [{r[3]}] parent={r[2]} labs={labels(qid)}")
    print("STEM:", (r[4] or '').replace('\n', ' ')[:900])
    for mm in ms(qid):
        print("MS:", (mm or '').replace('\n', ' ')[:700])

print()
print("===== E. 60915-60922 full =====")
for qid in [60915, 60916, 60917, 60918, 60919, 60920, 60921, 60922]:
    r = q(qid)
    if r is None:
        print(f"{qid} NOT FOUND")
        continue
    print(f"----- {qid} [{r[3]}] parent={r[2]} labs={labels(qid)}")
    print("STEM:", (r[4] or '').replace('\n', ' ')[:900])
    for mm in ms(qid):
        print("MS:", (mm or '').replace('\n', ' ')[:700])

print()
print("===== F. 58918-58922 =====")
for qid in [58918, 58919, 58920, 58921, 58922]:
    r = q(qid)
    if r is None:
        print(f"{qid} NOT FOUND")
        continue
    print(f"----- {qid} [{r[3]}] parent={r[2]} labs={labels(qid)}")
    print("STEM:", (r[4] or '').replace('\n', ' ')[:800])
    for mm in ms(qid):
        print("MS:", (mm or '').replace('\n', ' ')[:600])

print()
print("===== G. 59389-59394 =====")
for qid in [59389, 59390, 59391, 59392, 59393, 59394]:
    r = q(qid)
    if r is None:
        print(f"{qid} NOT FOUND")
        continue
    print(f"----- {qid} [{r[3]}] parent={r[2]} labs={labels(qid)}")
    print("STEM:", (r[4] or '').replace('\n', ' ')[:800])
    for mm in ms(qid):
        print("MS:", (mm or '').replace('\n', ' ')[:500])

print()
print("===== H. 57795-57797 =====")
for qid in [57795, 57796, 57797]:
    r = q(qid)
    if r is None:
        print(f"{qid} NOT FOUND")
        continue
    print(f"----- {qid} [{r[3]}] parent={r[2]} labs={labels(qid)}")
    print("STEM:", (r[4] or '').replace('\n', ' ')[:800])
    for mm in ms(qid):
        print("MS:", (mm or '').replace('\n', ' ')[:500])

print()
print("===== I. table-part siblings + 60980-60982 =====")
for qid in [57769, 58573, 59382, 59850, 60400, 60980, 60981, 60982]:
    r = q(qid)
    if r is None:
        print(f"{qid} NOT FOUND")
        continue
    print(f"----- {qid} [{r[3]}] parent={r[2]} labs={labels(qid)}")
    print("STEM:", (r[4] or '').replace('\n', ' ')[:400])

con.close()
