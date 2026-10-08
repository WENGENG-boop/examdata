#!/usr/bin/env python3
"""Per-question comparison of a question paper against its mark scheme.

Prints nothing when every question agrees; otherwise one line per question:
`<n> qp <qp marks> ms <ms marks>`. Exit code is 0 when consistent, 1 when not.

Usage:
  python tools/cmp.py <qp.pdf> <ms.pdf> [--bin path/to/cieparse]
"""
import json, os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_BIN = os.path.join(ROOT, 'cieparse', 'cieparse.exe' if os.name == 'nt' else 'cieparse')


def binary(argv):
    if '--bin' in argv:
        i = argv.index('--bin')
        p = argv[i + 1]
        del argv[i:i + 2]
        return p
    if os.path.exists(DEFAULT_BIN):
        return DEFAULT_BIN
    subprocess.run(['go', 'build', '-o', DEFAULT_BIN, '.'], cwd=os.path.join(ROOT, 'cieparse'), check=True)
    return DEFAULT_BIN


def parse(bin_path, pdf):
    out = subprocess.run([bin_path, pdf], capture_output=True, check=True)
    return json.loads(out.stdout.decode('utf-8', 'replace'))['data']


def row_marks(s):
    parts = [p for p in str(s or '').split(',') if p]
    nums = [int(p) for p in parts if p.isdigit()]
    if nums:
        return sum(nums)
    return sum(int(p[-1]) for p in parts if p and p[-1].isdigit())


def main():
    argv = sys.argv[1:]
    bin_path = binary(argv)
    if len(argv) != 2:
        sys.exit(__doc__)
    qp, ms = parse(bin_path, argv[0]), parse(bin_path, argv[1])
    qm = {str(q['number']): (q.get('marks') or 0) for q in qp.get('questions', [])}
    mm = {}
    for r in ms.get('rows', []):
        if r.get('alternative'):
            continue
        n = re.match(r'\d+', str(r.get('question') or ''))
        if n:
            mm.setdefault(n.group(), []).append((r.get('question'), r.get('marks')))
    bad = False
    for n in sorted(set(qm) | set(mm), key=int):
        s = sum(row_marks(m) for _, m in mm.get(n, []))
        if s != qm.get(n):
            print(n, 'qp', qm.get(n), 'ms', s, mm.get(n))
            bad = True
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
