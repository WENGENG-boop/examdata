"""Queue audit: per subject, compare r3 batch content vs applied.jsonl.

Status meanings:
  CONVERGED        last applied round had 0 changes (batch is consumed/stale, harmless)
  PENDING-REJUDGE  batch == the set of changes from the last applied round -> the batch is the
                   pending input for the next round, not yet judged
  NEEDS-EXPORT     changes exist but batch != changes -> must re-export before next round
"""
import json
import pathlib

B = pathlib.Path('tmp_jev_full_batches_r3')
D = pathlib.Path('tmp_jev_full_decisions_r3')

print(f'{"slug":28s} {"batch":>5s} {"applied":>7s} {"changes":>7s}  status')
print('-' * 90)
needs_export, pending = [], []
for d in sorted(D.iterdir()):
    if not d.is_dir():
        continue
    slug = d.name
    ap = d / 'applied.jsonl'
    if not ap.exists():
        print(f'{slug:28s}   (no applied.jsonl)')
        continue
    applied = [json.loads(l) for l in open(ap, encoding='utf-8') if l.strip()]
    changes = sorted({int(e['question_id']) for e in applied
                      if e.get('decision') == 'change' and e.get('status') == 'applied'})
    batch_qids = set()
    for bf in sorted((B / slug / 'batches').glob('batch-*.jsonl')):
        for l in open(bf, encoding='utf-8'):
            if l.strip():
                batch_qids.add(json.loads(l)['question_id'])
    applied_qids = {int(e['question_id']) for e in applied}
    if not changes:
        if batch_qids and not batch_qids <= applied_qids:
            status = f'ODD batch={len(batch_qids)} not-subset-of-applied'
        else:
            status = 'CONVERGED'
    elif set(changes) == batch_qids:
        status = 'PENDING-REJUDGE'
        pending.append(slug)
    else:
        status = 'NEEDS-EXPORT'
        needs_export.append(slug)
    print(f'{slug:28s} {len(batch_qids):5d} {len(applied):7d} {len(changes):7d}  {status}')

print()
print('NEEDS-EXPORT:', needs_export)
print('PENDING-REJUDGE:', pending)
