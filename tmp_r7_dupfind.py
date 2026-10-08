"""Find duplicate copies of the r7 maths-pure papers inside the DB (read-only).

For each target paper, we take a few distinctive stem tokens and look for
questions in *other* papers whose stem contains the same token.  Papers that
share several tokens are candidate duplicates.
"""
from __future__ import annotations

import re
import sys
from collections import defaultdict

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

DB = 'sqlite:///.data/examdata.db'
TARGET_PAPERS = [2022, 2026, 2027, 2039, 2042, 2043, 2059, 2060, 2083]

# distinctive tokens per target paper (lowercase, as they appear in the mangled text)
PROBES = {
    2022: ['3xy', 'y3', 'spherical balloon', 'trapezium rule, with 5 strips', 'x = 4 and x = 9'],
    2026: ['4i and z2', 'geometrical transformation u', 'xy = 16', 'divisible by 18',
           '2sinh', 'op is perpendicular'],
    2027: ['27 21 6 3', 'fishing boats', 'kx2 + 4x + k', 'log2b', 'harbour'],
    2039: ['2x – 5 cos x', 'interval bisection twice', 'ap3 + 2ap', 'rectangular hyperbola has parametric',
           'standard results for'],
    2042: ['series solution', '2asin2', 'x = et transforms', 'centre and the radius of the circle'],
    2043: ['shelim', 'f(x + 4)', 'salary of £14 000'],
    2059: ['cosh2 x – sinh2 x', 'sinh x + 7 cosh x', '2sinh', 'arc length', 'reflecting the line'],
    2060: ['geometric series is 5', 'height of water', 'smallest possible value of n'],
    2083: ['lizards', '2x4 + x2 – 3x + 8'],
}


def main() -> None:
    eng = create_engine(DB)
    s = Session(eng)
    q_all = {}
    for r in s.execute(text('SELECT id, paper_id, lower(stem_text) FROM question')):
        q_all[r[0]] = (r[1], r[2] or '')

    hits = defaultdict(lambda: defaultdict(int))
    for pid, probes in PROBES.items():
        own = {qid for qid, (p, _) in q_all.items() if p == pid}
        for probe in probes:
            for qid, (p, stem) in q_all.items():
                if probe in stem and qid not in own:
                    hits[pid][p] += 1
        print(f'--- paper {pid}: {len(own)} questions')
        for p, n in sorted(hits[pid].items(), key=lambda kv: -kv[1])[:6]:
            print(f'      paper {p}: {n} probe hits')


if __name__ == '__main__':
    main()
