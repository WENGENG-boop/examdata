"""Map Q8 transformation sentences to their source text (longest contiguous token run).

Usage: python tmp_de_q8map.py ROOTID [ROOTID...]
"""
from __future__ import annotations

import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / '.data' / 'examdata.db'

WORD = re.compile(r"[a-zäöüßA-ZÄÖÜ]+")


def toks(s: str) -> list[str]:
    return [w.lower() for w in WORD.findall(s or '')]


def longest_run(frag: list[str], text: list[str]) -> int:
    """Longest contiguous run of frag tokens present in text (in order)."""
    best = 0
    for i in range(len(frag)):
        for j in range(len(text)):
            k = 0
            while i + k < len(frag) and j + k < len(text) and frag[i + k] == text[j + k]:
                k += 1
            if k > best:
                best = k
    return best


def main() -> None:
    roots = [int(x) for x in sys.argv[1:]]
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    cur = db.cursor()

    for root in roots:
        r = cur.execute('SELECT paper_id, stem_text FROM question WHERE id=?', (root,)).fetchone()
        pid = r['paper_id']
        print(f'\n===== Q8 root {root} paper {pid}')
        cands = cur.execute('''SELECT q.id, q.number_label, q.marks, q.stem_text, tn.code
                               FROM question q
                               LEFT JOIN question_taxonomy qt ON qt.question_id=q.id
                               LEFT JOIN taxonomy_node tn ON tn.id=qt.node_id
                               WHERE q.paper_id=? AND q.id != ? AND q.parent_id IS NULL
                               ORDER BY q.display_order''', (pid, root)).fetchall()
        cands = [dict(c) for c in cands if len(c['stem_text'] or '') > 400]
        for c in cands:
            c['tok'] = toks(c['stem_text'])
        print('  candidates: ' + '; '.join(f"{c['id']}#{c['number_label']}[{c['code'] or '-'}]" for c in cands))
        kids = cur.execute('SELECT id, number_label, stem_text FROM question WHERE parent_id=? ORDER BY display_order', (root,)).fetchall()
        for k in kids:
            s = ' '.join((k['stem_text'] or '').split())
            frag = re.sub(r'^\([a-z]\)\s*', '', re.split(r'\((?:1|2)\)', s)[0])
            cut = frag.find(' (')
            if cut > 0:
                frag = frag[:cut]
            ft = toks(frag)
            scored = sorted(((longest_run(ft, c['tok']), c) for c in cands), key=lambda x: -x[0])
            top = ', '.join(f"{c['id']}#{c['number_label']}[{c['code'] or '-'}]:{sc}" for sc, c in scored[:3])
            print(f"  {k['id']} {k['number_label']}: {top}   || {s[:95]}")


if __name__ == '__main__':
    main()
