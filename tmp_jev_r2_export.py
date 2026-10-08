"""Round-2 export for Jev convergence re-check.

Re-exports only questions that were CHANGED in the previous apply round, with
their post-apply labels as `current`, so Jev can independently re-classify and
we can check whether the new labels converge (keep) or keep oscillating.

Unit/paper/number/stem are inherited from the previous round's batch entry
(that unit was validated by apply); `current` is refreshed from the DB.

Usage:
  python tmp_jev_r2_export.py                       # round2 from round1 outputs
  python tmp_jev_r2_export.py --decisions-root tmp_jev_full_decisions_r2 \
      --batch-root tmp_jev_full_batches_r2 --out-root tmp_jev_full_batches_r3
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

ROOT = Path(__file__).resolve().parent
DB_URL = f"sqlite:///{ROOT / '.data' / 'examdata.db'}"
BATCH_SIZE = 50


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--decisions-root', default='tmp_jev_full_decisions')
    ap.add_argument('--batch-root', default='tmp_jev_full_batches')
    ap.add_argument('--out-root', default='tmp_jev_full_batches_r2')
    args = ap.parse_args()

    decisions_root = ROOT / args.decisions_root
    batch_root = ROOT / args.batch_root
    out_root = ROOT / args.out_root

    eng = create_engine(DB_URL)
    s = Session(eng)

    total = 0
    for slug_dir in sorted(p for p in decisions_root.iterdir() if p.is_dir()):
        slug = slug_dir.name
        applied = slug_dir / 'applied.jsonl'
        if not applied.exists():
            continue
        changed: list[int] = []
        for line in open(applied, encoding='utf-8'):
            if not line.strip():
                continue
            e = json.loads(line)
            if e.get('decision') == 'change' and e.get('status') == 'applied':
                changed.append(int(e['question_id']))
        changed = sorted(set(changed))
        if not changed:
            continue

        r1: dict[int, dict] = {}
        for bf in sorted((batch_root / slug / 'batches').glob('batch-*.jsonl')):
            for line in open(bf, encoding='utf-8'):
                if line.strip():
                    item = json.loads(line)
                    r1[item['question_id']] = item

        missing = [q for q in changed if q not in r1]
        if missing:
            print(f'[{slug}] WARNING {len(missing)} changed qids not in previous batches: '
                  f'{missing[:10]}')

        items = []
        for qid in changed:
            base = r1.get(qid)
            if base is None:
                continue
            rows = s.execute(
                select(m.QuestionTaxonomy, m.TaxonomyNode)
                .join(m.TaxonomyNode, m.TaxonomyNode.id == m.QuestionTaxonomy.node_id)
                .where(m.QuestionTaxonomy.question_id == qid)
            ).all()
            current = [
                {
                    'code': node.code,
                    'name': node.name,
                    'confidence': round(row.confidence, 4) if row.confidence is not None else None,
                    'assigned_by': row.assigned_by,
                    'reviewed': bool(row.reviewed),
                }
                for row, node in rows
            ]
            items.append({
                'question_id': qid,
                'number_label': base.get('number_label') or '',
                'paper_code': base.get('paper_code'),
                'unit_code': base.get('unit_code'),
                'stem': base.get('stem') or '',
                'current': current,
            })

        out_dir = out_root / slug / 'batches'
        out_dir.mkdir(parents=True, exist_ok=True)
        for old in out_dir.glob('batch-*.jsonl'):
            old.unlink()
        for index in range(0, len(items), BATCH_SIZE):
            path = out_dir / f'batch-{index // BATCH_SIZE + 1:03d}.jsonl'
            with path.open('w', encoding='utf-8') as fh:
                for item in items[index:index + BATCH_SIZE]:
                    fh.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + '\n')
        print(f'[{slug}] changed={len(changed)} exported={len(items)} '
              f'batches={(len(items) + BATCH_SIZE - 1) // BATCH_SIZE} -> {out_dir}')
        total += len(items)

    print(f'TOTAL round-2 export: {total} questions -> {out_root}')


if __name__ == '__main__':
    main()
