"""Validate r6 self-judgment answer files for one (slug, unit) pack. Read-only.

Checks:
  - every qid of the unit's batch rows has exactly one answer line
  - answer codes belong to the unit's point list (or OK/?)
  - OK only when the row's current label count == 1
  - no qid answered that is not part of this unit's rows

Usage:
  ./.venv/Scripts/python.exe -X utf8 tmp_r6_check_ans.py --slug ial-maths --unit WMA02
"""
from __future__ import annotations

import argparse
import glob
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from examdata.core import models as m
from examdata.tagging.corpus import load_points

ROOT = Path(__file__).resolve().parent
DB_URL = f"sqlite:///{ROOT / '.data' / 'examdata.db'}"
BATCH_ROOT = ROOT / 'tmp_jev_full_batches_r6'
ANS_ROOT = ROOT / 'tmp_selfjudge' / 'r6'


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--slug', required=True)
    ap.add_argument('--unit', required=True)
    ap.add_argument('--pack', default=None,
                    help='pack index like 01; restricts to that pack + its ans file')
    args = ap.parse_args()

    eng = create_engine(DB_URL)
    s = Session(eng)
    points_slug = 'ial18-mathematics' if args.slug == 'ial18-mathematics-extra' else args.slug
    sub_row = s.execute(select(m.Subject).where(m.Subject.slug == points_slug)).scalar()
    if sub_row is None:
        raise SystemExit(f'subject {points_slug} not found')
    keys = {(sub_row.code or '').strip().lower(), (sub_row.slug or '').strip().lower()}
    keys.discard('')
    points = [p for p in load_points(s) if (p.subject or '').strip().lower() in keys]
    codes = {p.code for p in points if p.unit_code == args.unit}
    if not codes:
        raise SystemExit(f'unit {args.unit} has no points for {points_slug}')

    rows = []
    for f in sorted(glob.glob(str(BATCH_ROOT / args.slug / 'batches' / 'batch-*.jsonl'))):
        for line in open(f, encoding='utf-8'):
            rec = json.loads(line)
            if rec.get('unit_code') == args.unit:
                rows.append(rec)
    by_qid = {r['question_id']: r for r in rows}
    if not rows:
        raise SystemExit(f'no batch rows for {args.slug}/{args.unit}')

    ans_dir = ANS_ROOT / args.slug
    if args.pack:
        pack_path = ans_dir / f'{args.unit}-p{args.pack}.txt'
        if not pack_path.exists():
            raise SystemExit(f'pack file not found: {pack_path}')
        pack_qids = set()
        for raw in pack_path.read_text(encoding='utf-8').splitlines():
            mm = re.match(r'^\[\d+\]\s+(\d+)\s', raw)
            if mm:
                pack_qids.add(int(mm.group(1)))
        by_qid = {q: r for q, r in by_qid.items() if q in pack_qids}
        ans_files = sorted(ans_dir.glob(f'{args.unit}-p{args.pack}.ans.txt'))
    else:
        ans_files = sorted(ans_dir.glob(f'{args.unit}-p*.ans.txt'))

    answers: dict[int, tuple[str, str]] = {}
    problems: list[str] = []
    for f in ans_files:
        for ln, raw in enumerate(f.read_text(encoding='utf-8').splitlines(), 1):
            line = raw.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split()
            if len(parts) != 2 or not parts[0].isdigit():
                problems.append(f'{f.name}:{ln}: bad line {raw!r}')
                continue
            qid, code = int(parts[0]), parts[1]
            if qid in answers:
                problems.append(f'{f.name}:{ln}: duplicate qid {qid} '
                                f'(first in {answers[qid][1]})')
                continue
            answers[qid] = (code, f.name)

    hist: Counter = Counter()
    for qid, (code, src) in sorted(answers.items()):
        rec = by_qid.get(qid)
        if rec is None:
            problems.append(f'{qid}: answered but not a {args.unit} batch row ({src})')
            continue
        if code == 'OK':
            if len(rec.get('current') or []) != 1:
                problems.append(f'{qid}: OK but current has '
                                f'{len(rec.get("current") or [])} rows')
            else:
                hist['OK'] += 1
        elif code == '?':
            problems.append(f'{qid}: unresolved ?')
        elif code not in codes:
            problems.append(f'{qid}: code {code} not in {args.unit} point list')
        else:
            hist[code] += 1

    missing = [q for q in by_qid if q not in answers]
    for q in sorted(missing):
        problems.append(f'{q}: missing answer')

    print(f'[{args.slug}/{args.unit}] rows={len(by_qid)} answered={len(answers)} '
          f'missing={len(missing)} problems={len(problems)}')
    for p in problems[:80]:
        print('   ', p)
    if len(problems) > 80:
        print(f'    ... and {len(problems) - 80} more')
    print('answer histogram:')
    for code, n in sorted(hist.items()):
        print(f'   {code}: {n}')
    if problems:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
