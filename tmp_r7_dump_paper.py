"""Dump one paper's questions with structure + marks + current label (read-only).

Usage: ./.venv/Scripts/python.exe -X utf8 tmp_r7_dump_paper.py 2039 2042 ...
"""
from __future__ import annotations

import re
import sys

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

DB = 'sqlite:///.data/examdata.db'


def clean(x: str) -> str:
    x = re.sub(r'_{4,}', ' ', x or '')
    x = re.sub(r'Leave\s*blank', ' ', x)
    x = re.sub(r'\s+', ' ', x)
    return x.strip()


def main() -> None:
    eng = create_engine(DB)
    s = Session(eng)
    for pid in [int(a) for a in sys.argv[1:]]:
        rows = list(s.execute(text('''SELECT q.id, q.parent_id, q.number_label, q.marks, q.display_order,
                                              tn.code, q.stem_text
                                       FROM question q
                                       LEFT JOIN question_taxonomy qt ON qt.question_id = q.id
                                       LEFT JOIN taxonomy_node tn ON tn.id = qt.node_id
                                       WHERE q.paper_id = :p ORDER BY q.display_order'''), {'p': pid}))
        print(f'########## paper {pid} ({len(rows)} rows)')
        for r in rows:
            mark = f'{r[3]}mk' if r[3] is not None else '--mk'
            print(f'{r[0]} par={r[1]} #{r[2]} {mark} [{r[5] or "-"}] {clean(r[6])[:230]}')


if __name__ == '__main__':
    main()
