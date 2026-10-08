"""Show which stems matched for candidate duplicate papers (read-only)."""
from __future__ import annotations

from collections import defaultdict

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

DB = 'sqlite:///.data/examdata.db'

CANDIDATES = {
    2022: [8, 1201, 2040, 2044, 1145],
    2026: [1057, 2059, 2086],
    2027: [4, 1133, 1174, 1964, 2065],
    2039: [2003, 2077, 1126],
    2042: [1974, 1055, 1075, 1198],
    2060: [2006, 1048, 1059],
    2083: [2264],
}


def main() -> None:
    eng = create_engine(DB)
    s = Session(eng)
    for pid, cands in CANDIDATES.items():
        own = {r[0] for r in s.execute(text('SELECT id FROM question WHERE paper_id=:p'), {'p': pid})}
        own_stems = list(s.execute(text('SELECT id, lower(stem_text) FROM question WHERE paper_id=:p'), {'p': pid}))
        for c in cands:
            rows = list(s.execute(text('SELECT id, lower(stem_text) FROM question WHERE paper_id=:p'), {'p': c}))
            if not rows:
                continue
            print(f'=== paper {pid} vs {c} ({len(own)} vs {len(rows)} questions)')
            for oid, ostem in own_stems:
                for rid, rstem in rows:
                    # crude 40-char window overlap
                    best = 0
                    for i in range(0, max(1, len(ostem) - 40), 20):
                        chunk = ostem[i:i + 40]
                        if len(chunk) == 40 and chunk in rstem:
                            best = 1
                            break
                    if best:
                        print(f'   {oid} ~ {rid} :: {ostem[:60]!r}')
                        break


if __name__ == '__main__':
    main()
