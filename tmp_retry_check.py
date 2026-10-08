"""Check round2/round3 completion status for the retry watcher.

Round 2 (6 pending subjects): jev choices >= expected AND decisions written.
Round 3: for every subject dir in tmp_jev_full_batches_r3, decisions in
tmp_jev_full_decisions_r3/<slug>/ must cover the batch question count.

Exit 0 when round2 complete AND round3 done (or no round3 work).
Prints a status table either way.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

R2_EXPECT = {
    'ial18-chemistry': 2848,
    'ial18-economics': 443,
    'ial18-it': 494,
    'ial18-mathematics': 2186,
    'ial18-mathematics-extra': 879,
    'ial18-physics': 2202,
}


def count_choices(p: Path) -> int:
    if not p.exists():
        return 0
    n = 0
    for line in open(p, encoding='utf-8'):
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get('choice'):
            n += 1
    return n


def count_decisions(d: Path) -> int:
    if not d.is_dir():
        return 0
    n = 0
    for f in d.glob('batch-*.jsonl'):
        for line in open(f, encoding='utf-8'):
            if line.strip():
                n += 1
    return n


def main() -> int:
    ok = True
    print('== round2 pending subjects ==')
    for slug, exp in R2_EXPECT.items():
        jev = count_choices(ROOT / f'tmp_jev_full_r2_{slug}.jsonl')
        dec = count_decisions(ROOT / 'tmp_jev_full_decisions_r2' / slug)
        applied = (ROOT / 'tmp_jev_full_decisions_r2' / slug / 'applied.jsonl').exists()
        good = jev >= exp and dec >= exp
        ok = ok and good
        print(f'  {slug:28s} jev={jev:5d}/{exp} decisions={dec:5d} applied={applied} '
              f'{"OK" if good else "PENDING"}')

    print('== round3 ==')
    r3 = ROOT / 'tmp_jev_full_batches_r3'
    if not r3.is_dir():
        print('  (no round3 batches yet)')
    else:
        any_pending = False
        for sd in sorted(p for p in r3.iterdir() if p.is_dir()):
            slug = sd.name
            total = 0
            for f in (sd / 'batches').glob('batch-*.jsonl'):
                for line in open(f, encoding='utf-8'):
                    if line.strip():
                        total += 1
            dec = count_decisions(ROOT / 'tmp_jev_full_decisions_r3' / slug)
            good = dec >= total and total > 0
            any_pending = any_pending or not good
            print(f'  {slug:28s} batches={total:5d} decisions={dec:5d} '
                  f'{"OK" if good else "PENDING"}')
        ok = ok and not any_pending

    print('DONE' if ok else 'PENDING')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
