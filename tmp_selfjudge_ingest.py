"""Ingest self-judgment answer files into Jev-format jsonl (for decisions/apply).

Answer files live next to the packs: tmp_selfjudge/{set}/{slug}/{unit}-pNN.ans.txt
with one directive per line:
    qid OK      -> keep the single current label (r2 review sets)
    qid CODE    -> set / change to CODE (validated against the unit's points)
    qid ?       -> unresolved (hard error unless --allow-unresolved)

Single-point units are auto-filled with model='auto-single-candidate' when not
answered explicitly. Validation is all-or-nothing: on any error nothing is
written. Output: tmp_jev_full_r2_{slug}.jsonl (set=r2) or
tmp_jev_untagged_{slug}.jsonl (set=unt); both are overridable for later rounds.

Usage:
  python tmp_selfjudge_ingest.py --set r2 --slug ial18-economics
  python tmp_selfjudge_ingest.py --set unt --slug ial-law
  python tmp_selfjudge_ingest.py --set unt --slug all
  # convergence rounds:
  python tmp_selfjudge_ingest.py --set r2 --slug all \
      --batch-root tmp_jev_full_batches_r3 --jev-out 'tmp_jev_full_r3_{slug}.jsonl'
"""
from __future__ import annotations

import argparse
import glob
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from examdata.core import models as m
from examdata.tagging.corpus import load_points, unit_code_from_paper

ROOT = Path(__file__).resolve().parent
DB_URL = f"sqlite:///{ROOT / '.data' / 'examdata.db'}"

SETS = {
    'r2': {'batch_root': 'tmp_jev_full_batches_r2', 'jev_out': 'tmp_jev_full_r2_{slug}.jsonl'},
    'unt': {'batch_root': 'tmp_jev_untagged_batches', 'jev_out': 'tmp_jev_untagged_{slug}.jsonl'},
    'r6': {'batch_root': 'tmp_jev_full_batches_r6', 'jev_out': 'tmp_jev_full_r6_{slug}.jsonl'},
}
SELFJUDGE_ROOT = ROOT / 'tmp_selfjudge'


def load_by_unit(session: Session, slug: str):
    points_slug = 'ial18-mathematics' if slug == 'ial18-mathematics-extra' else slug
    sub_row = session.execute(select(m.Subject).where(m.Subject.slug == points_slug)).scalar()
    if sub_row is None:
        raise SystemExit(f'subject {points_slug} not found')
    keys = {(sub_row.code or '').strip().lower(), (sub_row.slug or '').strip().lower()}
    keys.discard('')
    points = [p for p in load_points(session) if (p.subject or '').strip().lower() in keys]
    by_unit: dict[str, list] = {}
    for p in points:
        by_unit.setdefault(p.unit_code, []).append(p)
    return by_unit


def collect_rows(session: Session, batch_root: Path, slug: str, by_unit: dict):
    rows = []
    files = sorted(glob.glob(str(batch_root / slug / 'batches' / 'batch-*.jsonl')))
    if not files:
        raise SystemExit(f'no batch files under {batch_root / slug / "batches"}')
    for f in files:
        batch = re.search(r'(batch-\w+)\.jsonl$', f).group(1)
        for line in open(f, encoding='utf-8'):
            rec = json.loads(line)
            qid = rec['question_id']
            unit = rec.get('unit_code')
            q = session.get(m.Question, qid)
            if q is None:
                raise SystemExit(f'question {qid} not found in DB')
            q_paper = session.get(m.Paper, q.paper_id)
            q_doc = session.get(m.Document, q_paper.document_id) if q_paper else None
            fresh = unit_code_from_paper(
                q_paper.attrs if q_paper else None,
                q_doc.paper_code if q_doc else None,
            )
            if fresh and fresh in by_unit:
                unit = fresh
            rows.append({
                'batch': batch,
                'qid': qid,
                'unit': unit,
                'paper_code': rec.get('paper_code'),
                'number': rec.get('number_label') or '',
                'current': [c.get('code') for c in (rec.get('current') or [])],
                'marks': q.marks,
            })
    return rows


def parse_answers(ans_dir: Path):
    answers: dict[int, tuple[str, str]] = {}
    errors: list[str] = []
    files = sorted(ans_dir.glob('*.ans.txt'))
    for f in files:
        for ln, raw in enumerate(f.read_text(encoding='utf-8').splitlines(), 1):
            line = raw.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split()
            if len(parts) != 2 or not parts[0].isdigit():
                errors.append(f'{f.name}:{ln}: bad line {raw!r}')
                continue
            qid = int(parts[0])
            if qid in answers:
                errors.append(f'{f.name}:{ln}: duplicate qid {qid} (first in {answers[qid][1]})')
                continue
            answers[qid] = (parts[1], f.name)
    return answers, errors, len(files)


def run_one(session: Session, set_name: str, slug: str, batch_root: Path, jev_out: str,
            allow_unresolved: bool) -> dict:
    by_unit = load_by_unit(session, slug)
    rows = collect_rows(session, batch_root, slug, by_unit)
    ans_dir = SELFJUDGE_ROOT / set_name / slug
    if not ans_dir.is_dir():
        raise SystemExit(f'no answer dir {ans_dir}')
    answers, errors, n_files = parse_answers(ans_dir)
    if not n_files:
        print(f'[{slug}] no answer files in {ans_dir}; skipped')
        return {'slug': slug, 'skipped': 'no answer files'}

    used: set[int] = set()
    unresolved: list[int] = []
    out: list[dict] = []
    stats: dict[str, dict[str, int]] = {}
    for r in rows:
        qid, unit = r['qid'], r['unit']
        pts = by_unit.get(unit) or []
        if not pts:
            errors.append(f'{qid}: unit {unit!r} not resolvable in subject points')
            continue
        st = stats.setdefault(unit, {'keep': 0, 'change': 0, 'auto': 0})
        a = answers.get(qid)
        model = 'self-judgment-v1'
        if a is None:
            if len(pts) == 1:
                choice = pts[0].code
                model = 'auto-single-candidate'
                st['auto'] += 1
            else:
                errors.append(f'{qid}: no answer (unit {unit})')
                continue
        else:
            used.add(qid)
            verb = a[0]
            if verb == 'OK':
                if len(r['current']) != 1:
                    errors.append(f'{qid}: OK but current labels = {r["current"]!r}')
                    continue
                choice = r['current'][0]
            elif verb == '?':
                unresolved.append(qid)
                continue
            else:
                choice = verb
            code_set = {p.code for p in pts}
            if choice not in code_set:
                errors.append(f'{qid}: choice {choice!r} not in unit {unit}')
                continue
        cur = list(r['current'])
        if len(cur) == 1 and cur[0] == choice and model == 'self-judgment-v1':
            st['keep'] += 1
        else:
            st['change'] += 1
        out.append({
            'question_id': qid,
            'batch': r['batch'],
            'unit': unit,
            'paper_code': r['paper_code'],
            'number': r['number'],
            'marks': r['marks'],
            'current': cur,
            'choice': choice,
            'confidence': 1.0,
            'top_probs': [[choice, 1.0]],
            'model': model,
            'ts': time.strftime('%Y-%m-%dT%H:%M:%S'),
        })

    for qid in sorted(set(answers) - used):
        errors.append(f'{qid}: answered but not in batch rows')

    if unresolved:
        msg = f'{len(unresolved)} unresolved (?): {unresolved[:20]}'
        if allow_unresolved:
            print(f'[{slug}] WARNING: {msg}')
        else:
            errors.append(msg)

    if errors:
        print(f'[{slug}] ERRORS ({len(errors)}), nothing written:')
        for e in errors[:40]:
            print('   ', e)
        if len(errors) > 40:
            print(f'    ... and {len(errors) - 40} more')
        return {'slug': slug, 'error': f'{len(errors)} validation errors'}

    out_path = ROOT / jev_out.format(slug=slug)
    with open(out_path, 'w', encoding='utf-8') as fh:
        for rec in out:
            fh.write(json.dumps(rec, ensure_ascii=False) + '\n')

    n_keep = sum(s['keep'] for s in stats.values())
    n_change = sum(s['change'] for s in stats.values())
    n_auto = sum(s['auto'] for s in stats.values())
    print(f'[{slug}] rows={len(rows)} written={len(out)} keep={n_keep} '
          f'change={n_change} auto={n_auto} unresolved={len(unresolved)} -> {out_path.name}')
    for unit in sorted(stats):
        s = stats[unit]
        print(f'    {unit}: keep={s["keep"]} change={s["change"]} auto={s["auto"]}')
    return {'slug': slug, 'written': len(out), 'keep': n_keep, 'change': n_change,
            'auto': n_auto, 'unresolved': len(unresolved)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--set', required=True, choices=['r2', 'unt', 'r6'])
    ap.add_argument('--slug', required=True)
    ap.add_argument('--batch-root', default=None)
    ap.add_argument('--jev-out', default=None)
    ap.add_argument('--allow-unresolved', action='store_true')
    args = ap.parse_args()

    cfg = SETS[args.set]
    batch_root = ROOT / (args.batch_root or cfg['batch_root'])
    jev_out = args.jev_out or cfg['jev_out']

    eng = create_engine(DB_URL)
    session = Session(eng)
    if args.slug == 'all':
        base = SELFJUDGE_ROOT / args.set
        slugs = sorted(d.name for d in base.iterdir() if d.is_dir()) if base.is_dir() else []
    else:
        slugs = [args.slug]

    summary = []
    for slug in slugs:
        try:
            summary.append(run_one(session, args.set, slug, batch_root, jev_out,
                                   args.allow_unresolved))
        except SystemExit as exc:
            print(f'[{slug}] {exc}')
            summary.append({'slug': slug, 'error': str(exc)})
        except Exception as exc:  # keep going across subjects
            print(f'[{slug}] EXCEPTION {type(exc).__name__}: {exc}')
            summary.append({'slug': slug, 'error': f'{type(exc).__name__}: {exc}'})

    ok = [x for x in summary if x.get('written') is not None]
    skipped = [x for x in summary if x.get('skipped')]
    errs = [x for x in summary if x.get('error')]
    print(f'INGEST TOTAL slugs={len(summary)} written={len(ok)} '
          f'rows={sum(x.get("written", 0) for x in ok)} skipped={len(skipped)} errors={len(errs)}')
    for x in errs:
        print('  ERROR', x)


if __name__ == '__main__':
    main()
