"""Debug: distinct-question match counts for a single target paper, no df filter."""
from __future__ import annotations

import re
import sys
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
    tp = int(sys.argv[1])
    eng = create_engine(DB)
    s = Session(eng)
    rows = list(s.execute(text('SELECT id, paper_id, stem_text FROM question')))
    qpaper = {r[0]: r[1] for r in rows}
    shing = {r[0]: shingles(r[2]) for r in rows}
    index = defaultdict(set)
    for qid, sh in shing.items():
        for x in sh:
            index[x].add(qid)
    own = [qid for qid, p in qpaper.items() if p == tp]
    pair = defaultdict(set)
    for qid in own:
        for x in shing[qid]:
            for other in index[x]:
                if qpaper[other] != tp:
                    pair[qpaper[other]].add(qid)
    for p, qs in sorted(pair.items(), key=lambda kv: -len(kv[1]))[:12]:
        print(f'paper {p}: {len(qs)} target questions matched')


if __name__ == '__main__':
    main()
