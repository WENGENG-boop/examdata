"""Precedent lookup: for given taxonomy codes, list questions already labeled with
them (whole DB), with short stem + MS snippets.

usage: python tmp_r2prec.py CODE [CODE ...] [--limit N] [--full]
"""
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
con = sqlite3.connect(f"file:{ROOT / '.data' / 'examdata.db'}?mode=ro", uri=True)
c = con.cursor()
WS = re.compile(r"\s+")

args = [a for a in sys.argv[1:]]
limit = 25
full = False
if "--limit" in args:
    i = args.index("--limit")
    limit = int(args[i + 1])
    args = args[:i] + args[i + 2:]
if "--full" in args:
    full = True
    args.remove("--full")

for code in args:
    node = c.execute("select id from taxonomy_node where code = ?", (code,)).fetchone()
    if not node:
        print(f"\n### {code}: NO NODE")
        continue
    rows = c.execute("""select q.id, d.title, q.number_path, q.stem_text, q.marks
                        from question_taxonomy qt
                        join question q on q.id = qt.question_id
                        join paper p on p.id = q.paper_id
                        join document d on d.id = p.document_id
                        where qt.node_id = ?
                        order by q.id""", (node[0],)).fetchall()
    print(f"\n### {code}: {len(rows)} questions labeled")
    for qid, title, npath, stem, marks in rows[:limit]:
        ms = c.execute("""select answer_text from mark_scheme_entry where question_id = ?
                          order by number_path limit 1""", (qid,)).fetchone()
        n = 400 if full else 160
        print(f"  [{qid}] {npath} {marks}mk | {WS.sub(' ', (stem or '').strip())[:n]}")
        if ms and ms[0]:
            print(f"        MS: {WS.sub(' ', ms[0].strip())[:160]}")
