"""r7 answer check: validate answers.ans.txt per batch against scope + points (read-only).

Usage:
  ./.venv/Scripts/python.exe -X utf8 tmp_r7_check_ans.py --batch accounting
  ./.venv/Scripts/python.exe -X utf8 tmp_r7_check_ans.py --all
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from examdata.tagging.corpus import load_points

ROOT = Path(__file__).resolve().parent
DB_URL = f"sqlite:///{ROOT / '.data' / 'examdata.db'}"


def load_scope() -> dict[int, dict]:
    out = {}
    for line in (ROOT / 'tmp_r7_scope.jsonl').read_text(encoding='utf-8').splitlines():
        if line.strip():
            x = json.loads(line)
            out[x['question_id']] = x
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--batch', default=None)
    ap.add_argument('--all', action='store_true')
    args = ap.parse_args()

    manifest = json.loads((ROOT / 'tmp_r7_batches' / 'manifest.json').read_text(encoding='utf-8'))
    batch_ids = sorted(manifest) if args.all or not args.batch else [args.batch]
    scope = load_scope()
    eng = create_engine(DB_URL)
    s = Session(eng)
    points = load_points(s)
    by_code = {p.code.upper(): p for p in points}

    grand_err = 0
    for bid in batch_ids:
        m = manifest[bid]
        expected = {qid for qid, x in scope.items() if x['doc_id'] in set(m['docs'])}
        unit_of = {qid: scope[qid]['truth_unit'] for qid in expected}
        ans_path = ROOT / m['ans_file']
        errors: list[str] = []
        if not ans_path.exists():
            errors.append(f'answer file missing: {m["ans_file"]}')
            answered: dict[int, str] = {}
        else:
            answered = {}
            for ln, line in enumerate(ans_path.read_text(encoding='utf-8').splitlines(), 1):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                parts = line.split()
                if len(parts) != 2:
                    errors.append(f'line {ln}: bad format {line!r}')
                    continue
                qid_s, code = parts
                try:
                    qid = int(qid_s)
                except ValueError:
                    errors.append(f'line {ln}: bad qid {qid_s!r}')
                    continue
                if qid in answered:
                    errors.append(f'line {ln}: duplicate qid {qid}')
                    continue
                if qid not in expected:
                    errors.append(f'line {ln}: qid {qid} not in batch scope')
                    continue
                if code == '?':
                    errors.append(f'line {ln}: ? not allowed (qid {qid})')
                    continue
                pt = by_code.get(code.upper())
                if pt is None:
                    errors.append(f'line {ln}: code {code!r} not a known point')
                    continue
                tu = unit_of[qid].upper()
                if (pt.unit_code or '').upper() != tu:
                    errors.append(f'line {ln}: code {code} unit {(pt.unit_code or "?")} != truth {tu} (qid {qid})')
                    continue
                answered[qid] = code
            missing = sorted(expected - set(answered))
            for qid in missing:
                errors.append(f'missing qid {qid} (unit {unit_of[qid]})')
        n_ok = len(answered)
        status = 'OK' if not errors else 'FAIL'
        print(f'[{bid}] expected={len(expected)} answered={n_ok} status={status} errors={len(errors)}')
        for e in errors[:40]:
            print('   ', e)
        if len(errors) > 40:
            print(f'    ... {len(errors) - 40} more')
        grand_err += len(errors)
    print(f'TOTAL errors={grand_err}')
    sys.exit(0 if grand_err == 0 else 1)


if __name__ == '__main__':
    main()
