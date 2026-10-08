"""Per-series decision sheet: one row per (paper, root series) with the pack qids,
existing sibling labels and a topic excerpt."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / '.data' / 'examdata.db'

POINTS = {
    'WGN01': ['WGN01-1', 'WGN01-2', 'WGN01-3', 'WGN01-4'],
    'WGN02': ['WGN02-1', 'WGN02-2', 'WGN02-3', 'WGN02-4'],
    'WGN04': ['WGN04-1', 'WGN04-2', 'WGN04-3', 'WGN04-4', 'WGN04-5', 'WGN04-6', 'WGN04-7',
              'WGN04-S1', 'WGN04-S2', 'WGN04-S3', 'WGN04-S4'],
}


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
    qrows = {}
    for qid in pack_set:
        qrows[qid] = cur.execute('SELECT paper_id FROM question WHERE id=?', (qid,)).fetchone()

    papers = {}
    for qid in pack_set:
        papers.setdefault(qrows[qid]['paper_id'], []).append(qid)

    for pid in sorted(papers):
        allq = cur.execute('''SELECT q.id, q.parent_id, q.number_label, q.marks, q.display_order,
                                     q.stem_text, tn.code
                              FROM question q
                              LEFT JOIN question_taxonomy qt ON qt.question_id=q.id
                              LEFT JOIN taxonomy_node tn ON tn.id=qt.node_id
                              WHERE q.paper_id=? ORDER BY q.display_order''', (pid,)).fetchall()
        by_id = {r['id']: r for r in allq}
        unit = None
        for qid in papers[pid]:
            pass
        # unit of the pack questions
        units = set()
        for u, ids in packs.items():
            if set(ids) & set(papers[pid]):
                units.add(u)
        unit = ','.join(sorted(units))
        if unit_filter and unit_filter not in units:
            continue
        print(f'\n##### PAPER {pid} ({unit}) — {len(papers[pid])} pack of {len(allq)}')

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

        for root_id, ids in sorted(groups.items(), key=lambda kv: by_id[kv[0]]['display_order']):
            r = by_id[root_id]
            subtree = [x for x in allq if x['id'] == root_id or _under(by_id, x, root_id)]
            labels = sorted({x['code'] for x in subtree if x['code']})
            lab = ','.join(labels) or '-'
            stem = ' '.join((r['stem_text'] or '').split())
            print(f'\n  ROOT {root_id} #{r["number_label"]} {r["marks"]}mk [{lab}] {stem[:300]}')
            for qid in ids:
                q = by_id[qid]
                s = ' '.join((q['stem_text'] or '').split())
                print(f'     {qid} #{q["number_label"]} {q["marks"]}mk : {s[:110]}')


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
