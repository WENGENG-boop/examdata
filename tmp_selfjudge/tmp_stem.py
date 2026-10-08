"""Print full stem + MS for qids (cap lengths).

usage: python tmp_stem.py [--stem N] [--ms N] qid1 qid2 ...
"""
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
con = sqlite3.connect(f"file:{ROOT / '.data' / 'examdata.db'}?mode=ro", uri=True)
c = con.cursor()

args = sys.argv[1:]
stem_cap = 900
ms_cap = 900
if "--stem" in args:
    i = args.index("--stem")
    stem_cap = int(args[i + 1])
    args = args[:i] + args[i + 2:]
if "--ms" in args:
    i = args.index("--ms")
    ms_cap = int(args[i + 1])
    args = args[:i] + args[i + 2:]

for qid in [int(x) for x in args]:
    row = c.execute(
        "select id, paper_id, parent_id, number_label, marks, "
        "replace(stem_text, char(10), ' ') from question where id=?",
        (qid,)).fetchone()
    if not row:
        print(f"Q {qid} NOT FOUND")
        continue
    print(f"===== Q {row[0]} paper={row[1]} par={row[2]} #{row[3]} {row[4]}mk")
    print(f"STEM: {row[5][:stem_cap]}")
    n = 0
    for ms in c.execute(
            "select number_path, marks, replace(answer_text, char(10), ' | ') "
            "from mark_scheme_entry where question_id=? order by id", (qid,)):
        n += 1
        print(f"MS [{ms[0]}] {ms[1]}mk: {ms[2][:ms_cap]}")
    if n == 0:
        print("MS: (none)")
    print()
