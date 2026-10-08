"""For each qid: current labels + family (root/children) labels.

usage: python tmp_fam.py qid1 qid2 ...
"""
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
con = sqlite3.connect(f"file:{ROOT / '.data' / 'examdata.db'}?mode=ro", uri=True)
c = con.cursor()

want = [int(x) for x in sys.argv[1:]]
wantset = set(want)


def labels(qid):
    return ", ".join(r[0] for r in c.execute(
        "select tn.code from question_taxonomy qt join taxonomy_node tn on tn.id=qt.node_id "
        "where qt.question_id=? order by tn.code", (qid,))) or "-"


seen = set()
for qid in want:
    row = c.execute("select id, paper_id, parent_id, number_label, coalesce(marks,-1) from question where id=?", (qid,)).fetchone()
    if not row:
        print(f"{qid} NOT FOUND")
        continue
    q, pid, par, num, mk = row
    root = par if par else q
    if root in seen:
        print(f"{q} #{num} {mk}mk :: {labels(q)}")
        continue
    seen.add(root)
    print(f"--- family root {root} (paper {pid}) ---")
    fam = c.execute(
        "select id, number_label, parent_id, coalesce(marks,-1) from question "
        "where id=? or parent_id=? order by id", (root, root)).fetchall()
    for fid, fnum, fpar, fmk in fam:
        mark = " <== PACK" if fid in wantset else ""
        print(f"  {fid} #{fnum} par={fpar} {fmk}mk :: {labels(fid)}{mark}")
    print()
