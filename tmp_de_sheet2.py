"""Compact decision worksheet for the german self-judge batch.

One line per root series:
  [AUTO CODE] root=... "#n" "topic excerpt" pack=[qids] labels={code:count}
  [MANUAL   ] ...
"""
from __future__ import annotations

import sqlite3
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / '.data' / 'examdata.db'


def main() -> None:
    unit_filter = sys.argv[1] if len(sys.argv) > 1 else None
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    cur = db.cursor()

    packs: dict[str, list[int]] = {}
    for p in sorted((ROOT / 'tmp_selfjudge' / 'unt' / 'ial-german').glob('*.txt')):
        unit = p.name.split('-')[0]
        ids = []
        for line in p.read_text(encoding='utf-8').splitlines():
            if line.startswith('['):
                ids.append(int(line.split(']')[1].split()[0]))
        packs.setdefault(unit, []).extend(ids)

    pack_set = {q for ids in packs.values() for q in ids}
    unit_of_q: dict[int, str] = {}
    for u, ids in packs.items():
        for q in ids:
            unit_of_q[q] = u

    papers: dict[int, list[int]] = {}
    for qid in pack_set:
        r = cur.execute('SELECT paper_id FROM question WHERE id=?', (qid,)).fetchone()
        papers.setdefault(r['paper_id'], []).append(qid)

    for pid in sorted(papers):
        units = sorted({unit_of_q[q] for q in papers[pid]})
        if unit_filter and unit_filter not in units:
            continue
        allq = cur.execute('''SELECT q.id, q.parent_id, q.number_label, q.marks, q.display_order,
                                     q.stem_text, tn.code
                              FROM question q
                              LEFT JOIN question_taxonomy qt ON qt.question_id=q.id
                              LEFT JOIN taxonomy_node tn ON tn.id=qt.node_id
                              WHERE q.paper_id=? ORDER BY q.display_order''', (pid,)).fetchall()
        by_id = {r['id']: r for r in allq}

        def root_of(qid):
            r = by_id[qid]
            guard = 0
            while r['parent_id'] is not None and r['parent_id'] in by_id and guard < 20:
                r = by_id[r['parent_id']]
                guard += 1
            return r

        groups: dict[int, list[int]] = {}
        for qid in papers[pid]:
            groups.setdefault(root_of(qid)['id'], []).append(qid)

        print(f'\n##### PAPER {pid} ({",".join(units)}) — {len(papers[pid])} pack of {len(allq)}')
        for root_id, ids in sorted(groups.items(), key=lambda kv: by_id[kv[0]]['display_order']):
            r = by_id[root_id]
            subtree = [x for x in allq if x['id'] == root_id or _under(by_id, x, root_id)]
            codes = Counter(x['code'] for x in subtree if x['code'])
            own = r['code'] or '-'
            auto = ''
            if r['code']:
                auto = f'AUTO {r["code"]}'
            elif len(codes) == 1:
                auto = f'AUTO {next(iter(codes))}'
            else:
                auto = 'MANUAL'
            if codes:
                dist = '{' + ','.join(f'{k}:{v}' for k, v in codes.most_common()) + '}'
            else:
                dist = '{}'
            stem = ' '.join((r['stem_text'] or '').split())
            print(f'\n  [{auto}] root={root_id} #{r["number_label"]} {r["marks"]}mk own={own} sib={dist}')
            print(f'      topic: {stem[:240]}')
            print(f'      pack: {ids}')


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
