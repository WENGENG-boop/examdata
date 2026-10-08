"""Dump Q5/Q6/Q7 source texts + Q8 sentences with known labels for Q8 roots.

Usage: python tmp_de_q8ctx.py ROOTID [ROOTID...]
"""
from __future__ import annotations

import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / '.data' / 'examdata.db'


def clean(s: str, n: int) -> str:
    return ' '.join((s or '').split())[:n]


def main() -> None:
    roots = [int(x) for x in sys.argv[1:]]
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    cur = db.cursor()

    for root in roots:
        r = cur.execute('SELECT paper_id, number_label FROM question WHERE id=?', (root,)).fetchone()
        pid = r['paper_id']
        print(f'\n############ Q8 root {root} paper {pid}')
        rows = cur.execute('''SELECT q.id, q.number_label, q.parent_id, q.marks, q.stem_text, tn.code
                              FROM question q
                              LEFT JOIN question_taxonomy qt ON qt.question_id=q.id
                              LEFT JOIN taxonomy_node tn ON tn.id=qt.node_id
                              WHERE q.paper_id=? ORDER BY q.display_order''', (pid,)).fetchall()
        byid = {x['id']: x for x in rows}
        roots_l = [x for x in rows if x['parent_id'] is None]
        for x in roots_l:
            lab = (x['number_label'] or '').strip()
            if lab in ('5', '6', '7'):
                print(f"\n--- Q{lab} root {x['id']} [{x['code'] or '-'}]")
                print(clean(x['stem_text'], 1400))
        print('\n--- Q8 sentences:')
        kids = [x for x in rows if x['parent_id'] == root]
        for k in kids:
            print(f"  {k['id']} {k['number_label']} [{k['code'] or '-'}]: {clean(k['stem_text'], 200)}")


if __name__ == '__main__':
    main()
