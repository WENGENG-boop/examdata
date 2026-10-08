"""Draft the german ans files: series inheritance for AUTO cases, TODO for manual.

Writes tmp_selfjudge/unt/ial-german/{pack}.ans.txt.draft (not the real ans files).
"""
from __future__ import annotations

import sqlite3
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / '.data' / 'examdata.db'
ANS_DIR = ROOT / 'tmp_selfjudge' / 'unt' / 'ial-german'


def main() -> None:
    unit_filter = sys.argv[1] if len(sys.argv) > 1 else None
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    cur = db.cursor()

    pack_files = sorted(ANS_DIR.glob('*.txt'))
    for pf in pack_files:
        unit = pf.name.split('-')[0]
        if unit_filter and unit != unit_filter:
            continue
        lines = []
        qids = []
        for line in pf.read_text(encoding='utf-8').splitlines():
            if line.startswith('['):
                qids.append(int(line.split(']')[1].split()[0]))
        # load paper data
        meta = {}
        for qid in qids:
            q = cur.execute('SELECT paper_id, parent_id, number_label, marks FROM question WHERE id=?', (qid,)).fetchone()
            meta[qid] = dict(q)
        papers = {m['paper_id'] for m in meta.values()}
        by_paper = {}
        for pid in papers:
            rows = cur.execute('''SELECT q.id, q.parent_id, q.number_label, q.marks, q.display_order,
                                         q.stem_text, tn.code
                                  FROM question q
                                  LEFT JOIN question_taxonomy qt ON qt.question_id=q.id
                                  LEFT JOIN taxonomy_node tn ON tn.id=qt.node_id
                                  WHERE q.paper_id=? ORDER BY q.display_order''', (pid,)).fetchall()
            by_paper[pid] = {r['id']: r for r in rows}

        n_auto = n_todo = 0
        for qid in qids:
            m = meta[qid]
            qs = by_paper[m['paper_id']]
            r = qs[qid]
            root = r
            guard = 0
            while root['parent_id'] is not None and root['parent_id'] in qs and guard < 20:
                root = qs[root['parent_id']]
                guard += 1
            subtree = [x for x in qs.values() if x['id'] == root['id'] or _under(qs, x, root['id'])]
            codes = Counter(x['code'] for x in subtree if x['code'])
            if root['code']:
                choice, why = root['code'], f'root {root["id"]}'
            elif len(codes) == 1:
                choice, why = next(iter(codes)), f'series {root["id"]} ({codes[next(iter(codes))]}x)'
            elif codes:
                top = codes.most_common()
                if len(top) > 1 and top[0][1] == top[1][1]:
                    choice, why = None, f'TIE {dict(codes)} root={root["id"]}'
                else:
                    choice, why = top[0][0], f'series {root["id"]} majority {top[0][1]}/{sum(codes.values())}'
            else:
                choice, why = None, f'NOLABEL root={root["id"]} # {root["number_label"]} ' + ' '.join((root['stem_text'] or '').split())[:120]
            if choice:
                lines.append(f'{qid} {choice}  # {why}')
                n_auto += 1
            else:
                lines.append(f'# TODO {qid} {why}')
                n_todo += 1
        out = ANS_DIR / (pf.stem + '.ans.txt.draft')
        out.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        print(f'{pf.name}: auto={n_auto} todo={n_todo} -> {out.name}')


def _under(by_id, node, root_id: int) -> bool:
    p = node['parent_id']
    guard = 0
    while p is not None and guard < 20:
        if p == root_id:
            return True
        parent = by_id.get(p)
        if parent is None:
            return False
        p = parent['parent_id']
        guard += 1
    return False


if __name__ == '__main__':
    main()
