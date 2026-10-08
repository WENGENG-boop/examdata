"""Fill the six german .ans.txt files from their .draft files.

WGN01-p01.ans.txt is already final; it is only read for the union check.
Validation is all-or-nothing: on any error nothing is written.
"""
from __future__ import annotations

import glob
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ANS_DIR = ROOT / 'tmp_selfjudge' / 'unt' / 'ial-german'
BATCH_GLOB = str(ROOT / 'tmp_jev_untagged_batches' / 'ial-german' / 'batches' / 'batch-*.jsonl')

WGN01_FINAL = 'WGN01-p01.ans.txt'
PACKS = ['WGN02-p01', 'WGN02-p02', 'WGN02-p03', 'WGN02-p04', 'WGN04-p01', 'WGN04-p02']

# root qid -> point number (1..4) for WGN02 (children inherit the root code)
WGN02_ROOTS = {
    53201: 4, 53221: 4, 53230: 4, 53241: 3, 53328: 3, 53338: 2, 53341: 1, 53354: 1, 53359: 3, 53368: 3,
    53379: 3, 53380: 3, 53385: 1, 53390: 1, 53393: 2, 53400: 3, 53406: 2, 53411: 4, 53420: 4, 53431: 1,
    53614: 1, 53619: 3, 53622: 4, 53629: 2, 53635: 1, 53649: 3, 53660: 1, 53666: 2, 53671: 3, 53681: 1,
    53687: 3, 53712: 4, 53801: 3, 53806: 2, 53811: 1, 53813: 4, 53826: 1, 53831: 2, 53838: 2, 53849: 1,
    53940: 3, 53950: 4, 53951: 2, 53958: 3, 53969: 2, 53977: 2, 53989: 3, 53990: 1, 53995: 4, 54000: 2,
    54001: 3, 54008: 3, 54014: 4, 54019: 2, 54027: 2, 54213: 2, 54218: 1, 54223: 4, 54226: 3, 54239: 2,
    54251: 3, 54264: 2, 54269: 1, 54274: 3, 54277: 4, 54284: 1, 54290: 4, 54314: 2, 54498: 1, 54501: 4,
    54508: 2, 54514: 1, 54519: 3, 54528: 3, 54539: 4, 54545: 2, 54550: 3, 54552: 4, 54569: 1, 54588: 4,
    54589: 3, 54594: 2, 54599: 2, 54600: 2, 54607: 1, 54613: 3, 54619: 4, 54628: 4, 54812: 4, 54817: 3,
    54822: 4, 54824: 2, 54830: 1, 54836: 3, 54850: 1, 54861: 2,
}

# Q8 series: root -> (root point, children (a)..(j) points); child qids = root+1..root+10
WGN04_SERIES = {
    53471: (6, [3, 3, 3, 6, 6, 6, 6, 6, 1, 4]),
    53562: (4, [2, 2, 6, 6, 6, 4, 4, 4, 4, 4]),
    53754: (7, [3, 3, 3, 4, 4, 7, 7, 7, 7, 7]),
    53893: (6, [4, 4, 5, 5, 5, 6, 6, 6, 6, 6]),
    54080: (6, [3, 3, 7, 7, 7, 6, 6, 6, 6, 6]),
    54354: (5, [6, 7, 7, 7, 5, 5, 5, 5, 5, 5]),
    54678: (6, [2, 2, 2, 3, 3, 6, 6, 6, 6, 6]),
    54765: (1, [4, 4, 6, 6, 6, 1, 1, 1, 1, 1]),
}

OVERRIDES = {53284: 'WGN04-S2'}

VALID = {
    'WGN01': {f'WGN01-{i}' for i in range(1, 5)},
    'WGN02': {f'WGN02-{i}' for i in range(1, 5)},
    'WGN04': {f'WGN04-{i}' for i in range(1, 8)} | {f'WGN04-S{i}' for i in range(1, 5)},
}


def wgn04_by_qid() -> dict[int, str]:
    out: dict[int, str] = {}
    for root, (rcode, children) in WGN04_SERIES.items():
        out[root] = f'WGN04-{rcode}'
        for i, c in enumerate(children):
            out[root + 1 + i] = f'WGN04-{c}'
    return out


def main() -> None:
    batch_qids: set[int] = set()
    for f in sorted(glob.glob(BATCH_GLOB)):
        for line in open(f, encoding='utf-8'):
            line = line.strip()
            if line:
                batch_qids.add(json.loads(line)['question_id'])

    w4map = wgn04_by_qid()
    errors: list[str] = []
    out_files: dict[str, list[str]] = {}
    stats: dict[str, tuple[int, int, int]] = {}
    seen: dict[int, str] = {}
    overrides_used: set[int] = set()

    for pack in PACKS:
        draft = ANS_DIR / f'{pack}.ans.txt.draft'
        unit = pack.split('-')[0]
        lines_out: list[str] = []
        n_todo = n_auto = n_ovr = 0
        for ln, raw in enumerate(draft.read_text(encoding='utf-8').splitlines(), 1):
            s = raw.strip()
            if not s:
                continue
            if s.startswith('# TODO'):
                toks = s.split()
                qid = int(toks[2])
                root_tok = next((t for t in toks[3:] if t.startswith('root=')), None)
                if root_tok is None:
                    errors.append(f'{pack}.draft:{ln}: no root= token: {s[:90]!r}')
                    continue
                root = int(root_tok[5:])
                if unit == 'WGN02':
                    num = WGN02_ROOTS.get(root)
                    if num is None:
                        errors.append(f'{pack}.draft:{ln}: root {root} not in WGN02_ROOTS')
                        continue
                    code = f'WGN02-{num}'
                else:
                    code = w4map.get(qid)
                    if code is None:
                        errors.append(f'{pack}.draft:{ln}: qid {qid} not in WGN04 table')
                        continue
                n_todo += 1
            elif s[0].isdigit():
                toks = s.split()
                qid = int(toks[0])
                code = toks[1]
                if qid in OVERRIDES:
                    code = OVERRIDES[qid]
                    overrides_used.add(qid)
                    n_ovr += 1
                n_auto += 1
            else:
                errors.append(f'{pack}.draft:{ln}: unexpected line: {s[:90]!r}')
                continue
            if code not in VALID[unit]:
                errors.append(f'{pack}.draft:{ln}: code {code} not valid for {unit}')
                continue
            if qid in seen:
                errors.append(f'{pack}.draft:{ln}: duplicate qid {qid} (also in {seen[qid]})')
                continue
            seen[qid] = pack
            lines_out.append(f'{qid} {code}')
        out_files[pack] = lines_out
        stats[pack] = (n_todo, n_auto, n_ovr)

    for ln, raw in enumerate((ANS_DIR / WGN01_FINAL).read_text(encoding='utf-8').splitlines(), 1):
        s = raw.strip()
        if not s or s.startswith('#'):
            continue
        qid = int(s.split()[0])
        if qid in seen:
            errors.append(f'{WGN01_FINAL}:{ln}: duplicate qid {qid} (also in {seen[qid]})')
            continue
        seen[qid] = WGN01_FINAL

    unused_ovr = set(OVERRIDES) - overrides_used
    if unused_ovr:
        errors.append(f'overrides not applied: {sorted(unused_ovr)}')

    missing = sorted(batch_qids - set(seen))
    extra = sorted(set(seen) - batch_qids)
    if missing:
        errors.append(f'{len(missing)} batch qids without answer: {missing[:20]}')
    if extra:
        errors.append(f'{len(extra)} answered qids not in batch: {extra[:20]}')

    if errors:
        print(f'ERRORS ({len(errors)}), nothing written:')
        for e in errors[:80]:
            print(' ', e)
        raise SystemExit(1)

    for pack in PACKS:
        (ANS_DIR / f'{pack}.ans.txt').write_text(
            '\n'.join(out_files[pack]) + '\n', encoding='utf-8', newline='\n')
        nt, na, no = stats[pack]
        print(f'{pack}: wrote {len(out_files[pack])} lines (TODO {nt}, AUTO {na}, overrides {no})')
    dist = Counter(line.split()[1][:5] for f in out_files.values() for line in f)
    print(f'total answered qids = {len(seen)} (batch {len(batch_qids)}), units: {dict(dist)}')


if __name__ == '__main__':
    main()
