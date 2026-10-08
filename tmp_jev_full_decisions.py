"""Generate full-pass Jev second-check decisions for all slugs.

Scope: every question exported to tmp_jev_full_batches (all tagged questions).
Rules (mirroring the first-pass decisions):
- single current label == Jev choice -> keep
- Jev choice in multi current labels -> change to choice (converge to single)
- otherwise -> change to choice
Validation before writing: every batch row must have a Jev record with a
choice, and the choice code must belong to the resolved unit's point list.
If any row is missing/invalid, nothing is written for that subject; the
problems are listed to <out-root>/{slug}.problems.jsonl.

Usage:
  python tmp_jev_full_decisions.py --subject all            # preview all
  python tmp_jev_full_decisions.py --subject all --write    # write decisions
  # round 2:
  python tmp_jev_full_decisions.py --subject all --write \
      --batch-root tmp_jev_full_batches_r2 \
      --out-root tmp_jev_full_decisions_r2 \
      --jev-template 'tmp_jev_full_r2_{slug}.jsonl'
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from examdata.core import models as m
from examdata.tagging.corpus import load_points

ROOT = Path(__file__).resolve().parent
DB_URL = f"sqlite:///{ROOT / '.data' / 'examdata.db'}"

SLUGS = [
    'ial-accounting', 'ial-englang', 'ial-englit', 'ial-french', 'ial-geography',
    'ial-german', 'ial-greek', 'ial-history', 'ial-law', 'ial-maths',
    'ial-psychology', 'ial-spanish', 'ial18-biology', 'ial18-business',
    'ial18-chemistry', 'ial18-economics', 'ial18-it', 'ial18-mathematics',
    'ial18-mathematics-extra', 'ial18-physics',
]

POINTS_SUBJECT = {'ial18-mathematics-extra': 'ial18-mathematics'}


def run_one(session: Session, slug: str, *, batch_root: Path, out_root: Path,
            jev_template: str, write: bool) -> dict:
    points_slug = POINTS_SUBJECT.get(slug, slug)
    sub_row = session.execute(select(m.Subject).where(m.Subject.slug == points_slug)).scalar()
    if sub_row is None:
        print(f'[{slug}] ERROR subject {points_slug} not found')
        return {'slug': slug, 'error': 'subject not found'}
    keys = {(sub_row.code or '').strip().lower(), (sub_row.slug or '').strip().lower()}
    keys.discard('')
    points = [p for p in load_points(session) if (p.subject or '').strip().lower() in keys]
    by_unit: dict[str, set[str]] = {}
    for p in points:
        by_unit.setdefault(p.unit_code, set()).add(p.code)

    jev_path = ROOT / jev_template.format(slug=slug)
    if not jev_path.exists():
        print(f'[{slug}] ERROR jev file missing: {jev_path.name}')
        return {'slug': slug, 'error': 'jev file missing'}
    jev: dict[int, dict] = {}
    for line in open(jev_path, encoding='utf-8'):
        if line.strip():
            r = json.loads(line)
            jev[r['question_id']] = r

    batch_dir = batch_root / slug / 'batches'
    batch_files = sorted(batch_dir.glob('batch-*.jsonl'))
    if not batch_files:
        print(f'[{slug}] ERROR no batch files in {batch_dir}')
        return {'slug': slug, 'error': 'no batches'}

    problems: list[dict] = []
    per_batch: dict[str, list[dict]] = {}
    total = n_keep = n_change = 0
    for bf in batch_files:
        batch = bf.stem
        out: list[dict] = []
        for line in open(bf, encoding='utf-8'):
            if not line.strip():
                continue
            item = json.loads(line)
            qid = item['question_id']
            cur = [c['code'] for c in item.get('current') or []]
            r = jev.get(qid)
            if r is None or not r.get('choice'):
                problems.append({
                    'question_id': qid, 'batch': batch, 'problem': 'no jev choice',
                    'unit': item.get('unit_code'), 'paper_code': item.get('paper_code'),
                })
                continue
            choice, conf = r['choice'], r.get('confidence')
            unit = r.get('unit') or item.get('unit_code')
            if choice not in by_unit.get(unit, set()):
                problems.append({
                    'question_id': qid, 'batch': batch,
                    'problem': f'choice {choice} not in unit {unit}',
                    'unit': unit, 'paper_code': item.get('paper_code'),
                })
                continue
            sd = str(r.get('model') or '').startswith('self-judgment')
            if len(cur) == 1 and cur[0] == choice:
                if r.get('model') == 'auto-single-candidate':
                    reason = f'单候选单元（{unit} 仅 1 个内容点）自动确认 {choice}'
                elif sd:
                    reason = f'自判复核确认原标签 {choice}（置信度 {conf}）'
                else:
                    reason = f'Jev 二次核查确认原标签 {choice}（置信度 {conf}）'
                row = {'question_id': qid, 'decision': 'keep', 'reason': reason}
            elif choice in cur:
                who = '自判复核' if sd else 'Jev 二次核查'
                row = {'question_id': qid, 'decision': 'change', 'code': choice,
                       'reason': (f"{who}判定 {choice}（置信度 {conf}）；"
                                  f"原标签多选（{'、'.join(cur)}）收敛为单选")}
            elif not cur:
                who = '自判首标' if sd else 'Jev 直判'
                row = {'question_id': qid, 'decision': 'change', 'code': choice,
                       'reason': (f"{who}（原无标签）判定 {choice}（置信度 {conf}）")}
            else:
                who = '自判复核' if sd else 'Jev 二次核查'
                row = {'question_id': qid, 'decision': 'change', 'code': choice,
                       'reason': (f"{who}判定 {choice}（置信度 {conf}）"
                                  f"与原标签（{'、'.join(cur)}）不符")}
            out.append(row)
            if row['decision'] == 'keep':
                n_keep += 1
            else:
                n_change += 1
        per_batch[batch] = out
        total += len(out)

    print(f'[{slug}] questions={total + len(problems)} keep={n_keep} '
          f'change={n_change} problems={len(problems)}')
    for p in problems[:8]:
        print('   PROBLEM', p)

    if problems:
        outp = out_root / f'{slug}.problems.jsonl'
        outp.parent.mkdir(parents=True, exist_ok=True)
        with open(outp, 'w', encoding='utf-8') as fh:
            for p in problems:
                fh.write(json.dumps(p, ensure_ascii=False) + '\n')
        print(f'   problems -> {outp.name}; NOT writing decisions for {slug}')
        return {'slug': slug, 'total': total + len(problems), 'keep': n_keep,
                'change': n_change, 'problems': len(problems)}

    if not write:
        print('   preview only (use --write to write decisions files)')
        return {'slug': slug, 'total': total, 'keep': n_keep,
                'change': n_change, 'problems': 0}

    for batch, out in per_batch.items():
        dst = out_root / slug / f'{batch}.jsonl'
        dst.parent.mkdir(parents=True, exist_ok=True)
        with open(dst, 'w', encoding='utf-8') as fh:
            for row in out:
                fh.write(json.dumps(row, ensure_ascii=False) + '\n')
    print(f'   wrote {len(per_batch)} decision files -> {out_root / slug}')
    return {'slug': slug, 'total': total, 'keep': n_keep,
            'change': n_change, 'problems': 0}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--subject', required=True, help="slug or 'all'")
    ap.add_argument('--write', action='store_true')
    ap.add_argument('--batch-root', default='tmp_jev_full_batches')
    ap.add_argument('--out-root', default='tmp_jev_full_decisions')
    ap.add_argument('--jev-template', default='tmp_jev_full_{slug}.jsonl')
    args = ap.parse_args()

    slugs = SLUGS if args.subject == 'all' else [args.subject]
    batch_root = ROOT / args.batch_root
    out_root = ROOT / args.out_root

    eng = create_engine(DB_URL)
    session = Session(eng)
    summary = []
    for slug in slugs:
        try:
            summary.append(run_one(
                session, slug, batch_root=batch_root, out_root=out_root,
                jev_template=args.jev_template, write=args.write,
            ))
        except Exception as exc:  # keep going across subjects
            print(f'[{slug}] EXCEPTION {type(exc).__name__}: {exc}')
            summary.append({'slug': slug, 'error': f'{type(exc).__name__}: {exc}'})

    tot = sum(x.get('total', 0) for x in summary)
    keep = sum(x.get('keep', 0) for x in summary)
    change = sum(x.get('change', 0) for x in summary)
    prob = sum(x.get('problems', 0) for x in summary)
    errs = [x for x in summary if x.get('error')]
    print(f'TOTAL questions={tot} keep={keep} change={change} problems={prob} '
          f'subject_errors={len(errs)}')
    for x in errs:
        print('  ERROR', x)


if __name__ == '__main__':
    main()
