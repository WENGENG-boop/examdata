"""r2 targeted probe: taxonomy dump or per-qid evidence (stem/MS/family).

usage: python tmp_r2probe.py tax
       python tmp_r2probe.py <qid> [<qid> ...]
"""
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
con = sqlite3.connect(f"file:{ROOT / '.data' / 'examdata.db'}?mode=ro", uri=True)
c = con.cursor()

WS = re.compile(r"\s+")


def sq(t, n):
    return WS.sub(" ", (t or "").strip())[:n]


def codes(qid):
    return [r[0] for r in c.execute(
        """select tn.code from question_taxonomy qt
           join taxonomy_node tn on tn.id = qt.node_id
           where qt.question_id = ? order by tn.code""", (qid,))]


mode = sys.argv[1]
if mode == 'tax':
    cols = [r[1] for r in c.execute("PRAGMA table_info(taxonomy_node)")]
    print("COLS:", cols)
    for r in c.execute("select * from taxonomy_node where code like 'WCH12%' order by code"):
        print(" | ".join(f"{col}={str(v)[:170]}" for col, v in zip(cols, r)))
    sys.exit()

for a in sys.argv[1:]:
    qid = int(a)
    info = c.execute("select id, parent_id, number_path, marks, kind, stem_text from question where id=?", (qid,)).fetchone()
    if not info:
        print(f"\n[{qid}] NOT FOUND")
        continue
    qid, parent, npath, marks, kind, stem = info
    print(f"\n===== [{qid}] p={npath} m={marks} kind={kind} cur={','.join(codes(qid)) or '-'} par={parent}")
    print("STEM:", sq(stem, 1100))
    for r in c.execute("select number_path, answer_text from mark_scheme_entry where question_id=? order by number_path", (qid,)):
        print(f"MS[{r[0]}]:", sq(r[1], 700))
    if parent:
        print(f"PARENT {parent} codes={codes(parent) or '-'}")
        fam = c.execute("select id, number_path, marks, stem_text from question where parent_id=? order by id", (parent,)).fetchall()
    else:
        fam = c.execute("select id, number_path, marks, stem_text from question where parent_id=? order by id", (qid,)).fetchall()
    for sid, sp, sm, ss in fam:
        mark = " <<" if sid == qid else ""
        print(f"  FAM {sid} {sp} m={sm} codes={','.join(codes(sid)) or '-'}{mark} :: {sq(ss, 160)}")
