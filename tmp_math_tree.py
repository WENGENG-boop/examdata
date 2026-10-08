"""Compact parent/sibling context for maths questions."""
import sys
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
c = sqlite3.connect(str(ROOT / '.data' / 'examdata.db'))
c.row_factory = sqlite3.Row


def clean(s, n=300):
    s = ' '.join((s or '').split())
    return s[:n]


def code_of(qid):
    r = c.execute("""SELECT tn.code FROM question_taxonomy qt
      JOIN taxonomy_node tn ON tn.id=qt.node_id WHERE qt.question_id=?""", (qid,)).fetchone()
    return r['code'] if r else '-'


for qid in sys.argv[1:]:
    q = c.execute("""SELECT q.*, p.paper_no, d.year FROM question q
      JOIN paper p ON p.id=q.paper_id JOIN document d ON d.id=p.document_id
      WHERE q.id=?""", (int(qid),)).fetchone()
    if not q:
        print(f'{qid} NOT FOUND')
        continue
    print(f"== {qid} #{q['number_label']} {q['marks']}mk {q['paper_no']} {q['year']} cur={code_of(qid)}")
    pid = q['parent_id']
    if pid:
        p = c.execute("SELECT * FROM question WHERE id=?", (pid,)).fetchone()
        print(f"   parent {pid} #{p['number_label']} {p['marks']}mk cur={code_of(pid)}")
        print(f"     PSTEM: {clean(p['stem_text'], 500)}")
        gp = p['parent_id']
        if gp:
            g = c.execute("SELECT * FROM question WHERE id=?", (gp,)).fetchone()
            print(f"   grand {gp} #{g['number_label']} {g['marks']}mk cur={code_of(gp)}")
            print(f"     GSTEM: {clean(g['stem_text'], 400)}")
            kids = c.execute("""SELECT id, number_label, marks, stem_text FROM question
                WHERE parent_id=? ORDER BY display_order""", (gp,)).fetchall()
        else:
            kids = c.execute("""SELECT id, number_label, marks, stem_text FROM question
                WHERE parent_id=? ORDER BY display_order""", (pid,)).fetchall()
    else:
        kids = []
        print(f"   (no parent) STEM: {clean(q['stem_text'], 500)}")
    for k in kids:
        mark = '*' if k['id'] == qid else ' '
        print(f"   {mark}kid {k['id']} #{k['number_label']} {k['marks']}mk [{code_of(k['id'])}] {clean(k['stem_text'], 120)}")
    print()
