"""Verify r6 apply state (read-only).

For every question in the r6 batch scope (per slug or all):
- must have >= 1 taxonomy row
- must have >= 1 reviewed row
- report any remaining unreviewed algo rows
- report distribution of reviewed-row counts (single-label goal)

Usage:
  ./.venv/Scripts/python.exe -X utf8 tmp_r6_verify.py            # all slugs
  ./.venv/Scripts/python.exe -X utf8 tmp_r6_verify.py --slugs a,b
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from examdata.core import models as m

ROOT = Path(__file__).resolve().parent
DB_URL = f"sqlite:///{ROOT / '.data' / 'examdata.db'}"
BATCH_ROOT = ROOT / 'tmp_jev_full_batches_r6'


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--slugs', default='all')
    args = ap.parse_args()

    eng = create_engine(DB_URL)
    s = Session(eng)
    if args.slugs == 'all':
        slugs = sorted(p.name for p in BATCH_ROOT.iterdir() if p.is_dir())
    else:
        slugs = args.slugs.split(',')

    total_q = 0
    total_ok = 0
    total_bad = 0
    for slug in slugs:
        qids = []
        for f in sorted((BATCH_ROOT / slug / 'batches').glob('batch-*.jsonl')):
            for line in open(f, encoding='utf-8'):
                if line.strip():
                    qids.append(json.loads(line)['question_id'])
        no_rows: list[int] = []
        no_reviewed: list[int] = []
        unreviewed_rows: list[tuple[int, str]] = []
        dist: Counter = Counter()
        for qid in qids:
            rows = list(s.scalars(select(m.QuestionTaxonomy).where(
                m.QuestionTaxonomy.question_id == qid)))
            rev = [r for r in rows if r.reviewed]
            if not rows:
                no_rows.append(qid)
            elif not rev:
                no_reviewed.append(qid)
            dist[len(rev)] += 1
            for r in rows:
                if not r.reviewed:
                    unreviewed_rows.append((qid, r.assigned_by or '?'))
        ok = len(qids) - len(no_rows) - len(no_reviewed)
        total_q += len(qids)
        total_ok += ok
        total_bad += len(no_rows) + len(no_reviewed)
        print(f'[{slug}] scope={len(qids)} reviewed_ok={ok} '
              f'no_rows={len(no_rows)} no_reviewed={len(no_reviewed)} '
              f'unreviewed_rows_left={len(unreviewed_rows)} '
              f'reviewed_count_dist={dict(sorted(dist.items()))}')
        for q in no_rows[:10]:
            print('   NO_ROWS', q)
        for q in no_reviewed[:10]:
            print('   NO_REVIEWED', q)
        for q, who in unreviewed_rows[:10]:
            print('   UNREVIEWED_ROW', q, who)

    print(f'TOTAL scope={total_q} reviewed_ok={total_ok} bad={total_bad}')
    if total_bad:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
