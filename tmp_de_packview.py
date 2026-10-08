"""Compact pack viewer: group a self-judge pack's questions by paper with context.

Usage:
  python tmp_de_packview.py <slug> [unit] [--full-qid QID ...] [--stem N]
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / '.data' / 'examdata.db'


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('slug')
    ap.add_argument('unit', nargs='?')
    ap.add_argument('--stem', type=int, default=110)
    ap.add_argument('--full', type=int, default=0, help='print full stems for first N marks>=X questions')
    ap.add_argument('--show-all-labels', action='store_true')
    args = ap.parse_args()

    db = sqlite3.connect(DB)
    db.row_factory = sqlite3.Row
    cur = db.cursor()

    packs = sorted((ROOT / 'tmp_selfjudge' / 'unt' / args.slug).glob('*.txt'))
    if args.unit:
        packs = [p for p in packs if p.name.startswith(args.unit)]

    qids: list[int] = []
    pack_of: dict[int, str] = {}
    for p in packs:
        for line in p.read_text(encoding='utf-8').splitlines():
            if line.startswith('['):
                qid = int(line.split(']')[1].split()[0])
                qids.append(qid)
                pack_of[qid] = p.stem

    print(f'# {args.slug}: {len(qids)} qids across {len(packs)} packs')

    info = {}
    for qid in qids:
        row = cur.execute('''SELECT q.id, q.paper_id, q.parent_id, q.number_label, q.marks,
                                    q.display_order, q.stem_text, p.attrs, d.paper_code
                             FROM question q JOIN paper p ON p.id=q.paper_id
                             LEFT JOIN document d ON d.id=p.document_id
                             WHERE q.id=?''', (qid,)).fetchone()
        info[qid] = row

    by_paper: dict[int, list[int]] = {}
    for qid in qids:
        by_paper.setdefault(info[qid]['paper_id'], []).append(qid)

    for pid, qs in sorted(by_paper.items(), key=lambda kv: -len(kv[1])):
        rows = [info[q] for q in qs]
        codes = {r['paper_code'] for r in rows}
        print(f'\n===== paper {pid} code={sorted(codes)} n_pack={len(qs)}')
        # paper-level label distribution (all questions of the paper)
        allq = cur.execute('''SELECT q.id, q.number_label, q.marks,
                                     substr(replace(q.stem_text,char(10),' '),1,80) s,
                                     tn.code
                              FROM question q
                              LEFT JOIN question_taxonomy qt ON qt.question_id=q.id
                              LEFT JOIN taxonomy_node tn ON tn.id=qt.node_id
                              WHERE q.paper_id=? ORDER BY q.display_order''', (pid,)).fetchall()
        print(f'  (paper has {len(allq)} questions total)')
        if args.show_all_labels:
            for r in allq:
                mark = 'PACK' if r['id'] in set(qs) else '    '
                print(f"  {mark} {r['id']} #{r['number_label']} {r['marks']}mk [{r['code'] or '-'}] {r['s']}")
        for r in rows:
            q = info[r['id']]
            stem = ' '.join((q['stem_text'] or '').split())
            if args.stem and len(stem) > args.stem:
                stem = stem[:args.stem] + '…'
            par = ''
            if q['parent_id']:
                prow = cur.execute('SELECT id, number_label, substr(replace(stem_text,char(10)," "),1,90) s FROM question WHERE id=?', (q['parent_id'],)).fetchone()
                if prow:
                    par = f" par={prow['id']}#{prow['number_label']} {prow['s']}"
            code = cur.execute('''SELECT tn.code FROM question_taxonomy qt JOIN taxonomy_node tn ON tn.id=qt.node_id WHERE qt.question_id=?''', (q['id'],)).fetchall()
            codes_s = ','.join(c[0] for c in code) or '-'
            print(f"  {q['id']} #{q['number_label']} {q['marks']}mk [{codes_s}] {stem}{par}")


if __name__ == '__main__':
    main()
