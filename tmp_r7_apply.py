"""r7 apply: fix the 441 wrong-row questions (row unit != paper print unit).

Inputs (authoritative):
  - tmp_r7_scope.jsonl        qid -> truth_unit (paper print code), doc_id, ...
  - tmp_r7_batches/manifest.json + <batch>/answers.ans.txt   (qid CODE)

Rules:
  - answers must cover every scope qid of the batch exactly once;
  - code must be a known point (global lookup, cross-subject allowed) whose
    unit_code == truth_unit of the question;
  - write semantics (same as r6 apply): delete ALL taxonomy rows of the
    question, then insert one row source=ai-review / assigned_by=ai-review-v1 /
    confidence=1.0 / reviewed=True.

Default is dry-run; --write commits and writes tmp_r7_applied.jsonl.
Refuses to write if any validation error exists.

Usage:
  ./.venv/Scripts/python.exe -X utf8 tmp_r7_apply.py            # dry run
  ./.venv/Scripts/python.exe -X utf8 tmp_r7_apply.py --write    # apply
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
from examdata.tagging.assign import REVIEW_ASSIGNED_BY, REVIEW_SOURCE
from examdata.tagging.corpus import load_points

ROOT = Path(__file__).resolve().parent
DB_URL = f"sqlite:///{ROOT / '.data' / 'examdata.db'}"


def load_scope() -> dict[int, dict]:
    out: dict[int, dict] = {}
    for line in (ROOT / 'tmp_r7_scope.jsonl').read_text(encoding='utf-8').splitlines():
        if line.strip():
            x = json.loads(line)
            out[x['question_id']] = x
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true')
    args = ap.parse_args()

    manifest = json.loads((ROOT / 'tmp_r7_batches' / 'manifest.json').read_text(encoding='utf-8'))
    scope = load_scope()

    eng = create_engine(DB_URL)
    s = Session(eng)
    points = load_points(s)
    by_code = {p.code.upper(): p for p in points}

    errors: list[str] = []
    planned: list[tuple[int, str, str, int]] = []  # qid, code, truth_unit, doc_id
    seen: set[int] = set()
    per_batch = Counter()

    for bid in sorted(manifest):
        mg = manifest[bid]
        expected = {qid for qid, x in scope.items() if x['doc_id'] in set(mg['docs'])}
        ans_path = ROOT / mg['ans_file']
        if not ans_path.exists():
            errors.append(f'[{bid}] answer file missing: {mg["ans_file"]}')
            continue
        answered: dict[int, str] = {}
        for ln, line in enumerate(ans_path.read_text(encoding='utf-8').splitlines(), 1):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split()
            if len(parts) != 2:
                errors.append(f'[{bid}] line {ln}: bad format {line!r}')
                continue
            qid_s, code = parts
            try:
                qid = int(qid_s)
            except ValueError:
                errors.append(f'[{bid}] line {ln}: bad qid {qid_s!r}')
                continue
            if qid in answered:
                errors.append(f'[{bid}] line {ln}: duplicate qid {qid}')
                continue
            if qid not in expected:
                errors.append(f'[{bid}] line {ln}: qid {qid} not in batch scope')
                continue
            if code == '?':
                errors.append(f'[{bid}] line {ln}: ? not allowed (qid {qid})')
                continue
            pt = by_code.get(code.upper())
            if pt is None:
                errors.append(f'[{bid}] line {ln}: code {code!r} not a known point')
                continue
            tu = scope[qid]['truth_unit'].upper()
            if (pt.unit_code or '').upper() != tu:
                errors.append(f'[{bid}] line {ln}: code {code} unit {pt.unit_code or "?"} != truth {tu} (qid {qid})')
                continue
            answered[qid] = code
        missing = sorted(expected - set(answered))
        for qid in missing:
            errors.append(f'[{bid}] missing qid {qid} (unit {scope[qid]["truth_unit"]})')
        for qid, code in answered.items():
            if qid in seen:
                errors.append(f'[{bid}] qid {qid} planned twice')
                continue
            seen.add(qid)
            planned.append((qid, code, scope[qid]['truth_unit'], scope[qid]['doc_id']))
            per_batch[bid] += 1

    n_scope = len(scope)
    print(f'scope={n_scope} planned={len(planned)} errors={len(errors)}')
    for bid in sorted(manifest):
        exp = len({qid for qid, x in scope.items() if x['doc_id'] in set(manifest[bid]['docs'])})
        print(f'  [{bid}] expected={exp} planned={per_batch[bid]}')
    for e in errors[:60]:
        print('  ERROR', e)
    if len(errors) > 60:
        print(f'  ... {len(errors) - 60} more errors')
    if errors:
        print('REFUSING to write: validation errors present')
        sys.exit(1)

    mode = 'WRITE' if args.write else 'dry-run'
    n_deleted_total = 0
    log: list[dict] = []
    for qid, code, truth_unit, doc_id in planned:
        rows = list(s.scalars(select(m.QuestionTaxonomy).where(
            m.QuestionTaxonomy.question_id == qid,
        )))
        n_del = len(rows)
        n_deleted_total += n_del
        if args.write:
            for link in rows:
                s.delete(link)
            s.flush()
            s.add(m.QuestionTaxonomy(
                question_id=qid,
                node_id=by_code[code.upper()].node_id,
                source=REVIEW_SOURCE,
                confidence=1.0,
                assigned_by=REVIEW_ASSIGNED_BY,
                reviewed=True,
            ))
        log.append({
            'question_id': qid,
            'doc_id': doc_id,
            'truth_unit': truth_unit,
            'code': code,
            'n_deleted': n_del,
            'status': 'applied' if args.write else 'dry-run',
        })
    if args.write:
        s.commit()
        out = ROOT / 'tmp_r7_applied.jsonl'
        with open(out, 'w', encoding='utf-8') as fh:
            for entry in log:
                fh.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + '\n')
        print(f'committed; log -> {out.name}')
    print(f'TOTAL planned={len(planned)} rows_deleted={n_deleted_total} mode={mode}')
    # sanity: rows per question before deletion distribution
    dist = Counter(e['n_deleted'] for e in log)
    print('n_deleted distribution:', dict(sorted(dist.items())))


if __name__ == '__main__':
    main()
