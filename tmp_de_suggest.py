"""Suggest a spec code for each german pack question by series inheritance.

Rules:
 1. root ancestor's own label (if exactly 1)
 2. majority/unique label among the root's subtree siblings
 3. otherwise: no suggestion (manual topic matching needed)
Outputs a per-paper report + a candidate .ans.txt body.
"""
from __future__ import annotations

import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / '.data' / 'examdata.db'
UNIT_POINTS = {
    'WGN01': ['WGN01-1', 'WGN01-2', 'WGN01-3', 'WGN01-4'],
    'WGN02': ['WGN02-1', 'WGN02-2', 'WGN02-3', 'WGN02-4'],
    'WGN04': ['WGN04-1', 'WGN04-2', 'WGN04-3', 'WGN04-4', 'WGN04-5', 'WGN04-6', 'WGN04-7',
              'WGN04-S1', 'WGN04-S2', 'WGN04-S3', 'WGN04-S4'],
}


def main() -> None:
    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    cur = db.cursor()

    rows = []
    for p in sorted((ROOT / 'tmp_selfjudge' / 'unt' / 'ial-german').glob('*.txt')):
        unit = p.name.split('-')[0]
        for line in p.read_text(encoding='utf-8').splitlines():
            if line.startswith('['):
                qid = int(line.split(']')[1].split()[0])
                rows.append((unit, qid, p.stem))

    # gather paper questions once
    paper_of: dict[int, int] = {}
    for unit, qid, _ in rows:
        r = cur.execute('SELECT paper_id, parent_id, number_label, marks, stem_text FROM question WHERE id=?', (qid,)).fetchone()
        paper_of[qid] = r['paper_id']

    cache: dict[int, dict] = {}
    for pid in set(paper_of.values()):
        qs = cur.execute('''SELECT q.id, q.parent_id, q.number_label, q.marks, q.display_order,
                                   q.stem_text, tn.code
                            FROM question q
                            LEFT JOIN question_taxonomy qt ON qt.question_id=q.id
                            LEFT JOIN taxonomy_node tn ON tn.id=qt.node_id
                            WHERE q.paper_id=? ORDER BY q.display_order''', (pid,)).fetchall()
        cache[pid] = {r['id']: r for r in qs}

    out_by_unit: dict[str, list[str]] = defaultdict(list)
    stats = Counter()
    manual: list[tuple[str, int, str]] = []

    cur_unit = None
    for unit, qid, pack in rows:
        if unit != cur_unit:
            cur_unit = unit
            out_by_unit[unit].append(f'\n# ---------- {unit} ----------')
        qs = cache[paper_of[qid]]
        q = qs[qid]
        # walk to root
        root = q
        seen = set()
        while root['parent_id'] is not None and root['parent_id'] in qs and root['id'] not in seen:
            seen.add(root['id'])
            root = qs[root['parent_id']]
        subtree = [r for r in qs.values() if r['id'] == root['id'] or _under(qs, r, root['id'])]
        codes = Counter(r['code'] for r in subtree if r['code'])
        choice = None
        why = ''
        if root['code']:
            choice, why = root['code'], 'root'
        elif len(codes) == 1:
            choice, why = next(iter(codes)), f'series({codes[next(iter(codes))]})'
        elif codes:
            top = codes.most_common(1)[0]
            choice, why = top[0], f'majority {top[1]}/{sum(codes.values())}'
        if choice:
            stats['auto'] += 1
            out_by_unit[unit].append(f'{qid} {choice}  # {why} root={root["id"]}')
        else:
            stats['manual'] += 1
            manual.append((unit, qid, pack))
            out_by_unit[unit].append(f'# TODO {qid} root={root["id"]} #{root["number_label"]} {" ".join((root["stem_text"] or "").split())[:150]}')

    for unit, lines in out_by_unit.items():
        print(f'\n===== {unit} =====')
        print('\n'.join(lines))
    print('\nSTATS', dict(stats))


def _under(qs: dict, node, root_id: int) -> bool:
    p = node['parent_id']
    guard = 0
    while p is not None and guard < 20:
        if p == root_id:
            return True
        parent = qs.get(p)
        if parent is None:
            return False
        p = parent['parent_id']
        guard += 1
    return False


if __name__ == '__main__':
    main()
