"""Find duplicate papers for each r7 maths-pure target paper (v2).

- 40-char shingles, but drop shingles that occur in more than COMMON_MAX questions
  (these are boilerplate: 'Leave blank', 'DO NOT WRITE IN THIS AREA', ...).
- For each (target paper, other paper) pair count how many *target questions* are matched.
"""
from __future__ import annotations

import re
from collections import defaultdict

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

DB = 'sqlite:///.data/examdata.db'
TARGET_PAPERS = [2022, 2026, 2027, 2039, 2042, 2043, 2059, 2060, 2083]
COMMON_MAX = 25


def shingles(txt: str, n: int = 40, step: int = 10):
    t = re.sub(r'\s+', ' ', (txt or '').lower()).strip()
    out = set()
    for i in range(0, max(1, len(t) - n + 1), step):
        s = t[i:i + n]
        if len(s) == n:
            out.add(s)
    return out


def main() -> None:
    eng = create_engine(DB)
    s = Session(eng)
    rows = list(s.execute(text('SELECT id, paper_id, stem_text FROM question')))
    qpaper = {r[0]: r[1] for r in rows}
    shing = {r[0]: shingles(r[2]) for r in rows}

    df = defaultdict(int)
    index = defaultdict(set)
    for qid, sh in shing.items():
        for x in sh:
            index[x].add(qid)
    for x, qs in index.items():
        df[x] = len(qs)
    rare = {x for x, n in df.items() if n <= COMMON_MAX}

    for tp in TARGET_PAPERS:
        own = [qid for qid, p in qpaper.items() if p == tp]
        pair = defaultdict(set)  # other paper -> set of matched target qids
        for qid in own:
            for x in shing[qid] & rare:
                for other in index[x]:
                    op = qpaper[other]
                    if op != tp:
                        pair[op].add(qid)
        ranked = sorted(pair.items(), key=lambda kv: -len(kv[1]))
        print(f'=== target paper {tp}: {len(own)} questions')
        for p, qs in ranked[:6]:
            if len(qs) >= 2:
                print(f'    paper {p}: matches {len(qs)} target questions')


if __name__ == '__main__':
    main()
