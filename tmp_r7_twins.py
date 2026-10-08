"""For each target qid, find twin questions in other papers and show their taxonomy codes.

Usage:  ./.venv/Scripts/python.exe -X utf8 tmp_r7_twins.py 58939 58940 ...
        ./.venv/Scripts/python.exe -X utf8 tmp_r7_twins.py --paper 2022
"""
from __future__ import annotations

import argparse
import re
from collections import defaultdict

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

DB = 'sqlite:///.data/examdata.db'


def shingles(txt: str, n: int = 40, step: int = 10):
    t = re.sub(r'\s+', ' ', (txt or '').lower()).strip()
    out = set()
    for i in range(0, max(1, len(t) - n + 1), step):
        s = t[i:i + n]
        if len(s) == n:
            out.add(s)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('qids', nargs='*', type=int)
    ap.add_argument('--paper', type=int, default=None)
    ap.add_argument('--min-overlap', type=int, default=3)
    args = ap.parse_args()

    eng = create_engine(DB)
    s = Session(eng)
    rows = list(s.execute(text('SELECT id, paper_id, stem_text FROM question')))
    qpaper = {r[0]: r[1] for r in rows}
    qstem = {r[0]: r[2] for r in rows}
    shing = {r[0]: shingles(r[2]) for r in rows}
    labels = {}
    for r in s.execute(text('''SELECT qt.question_id, tn.code FROM question_taxonomy qt
                               JOIN taxonomy_node tn ON tn.id=qt.node_id''')):
        labels.setdefault(r[0], []).append(r[1])

    index = defaultdict(set)
    for qid, sh in shing.items():
        for x in sh:
            index[x].add(qid)

    if args.paper:
        targets = [qid for qid, p in qpaper.items() if p == args.paper]
        targets.sort()
    else:
        targets = args.qids

    for qid in targets:
        mine = shing[qid]
        score = defaultdict(int)
        for x in mine:
            for other in index[x]:
                if other != qid:
                    score[other] += 1
        best = sorted(score.items(), key=lambda kv: -kv[1])[:8]
        print(f'== qid {qid} (paper {qpaper[qid]}) label={labels.get(qid)}')
        print(f'   stem: {re.sub(chr(10), " ", (qstem[qid] or ""))[:110]!r}')
        for other, n in best:
            if n < args.min_overlap:
                continue
            if qpaper[other] == qpaper[qid]:
                continue
            print(f'   twin {other} paper {qpaper[other]} overlap={n} label={labels.get(other)}')


if __name__ == '__main__':
    main()
