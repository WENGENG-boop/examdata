"""Generate .ans.txt for ial-french unt self-judgment from tmp_fr_map.txt + decisions.

Rules:
- every batch qid gets exactly one line: `qid CODE` (no OK / ? - current is empty)
- in_batch=True group -> my decision for the root, applied to root + children
- in_batch=False group -> children inherit root's existing tag (tags[0])
- star (uncertain) items get an explicit alternative in comments
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ANS_DIR = ROOT / 'tmp_selfjudge' / 'unt' / 'ial-french'
PACKS = ['WFR02-p01', 'WFR02-p02', 'WFR02-p03', 'WFR02-p04', 'WFR04-p01', 'WFR04-p02']

# root qid -> WFR02 point number (decided in the analysis pass)
WFR02_DEC = {
    50157: 1, 50162: 2, 50167: 3, 50170: 4, 50177: 1, 50183: 3, 50188: 4, 50195: 4,
    50293: 1, 50298: 3, 50303: 2, 50308: 4, 50315: 1, 50321: 4, 50326: 3, 50344: 2,
    50517: 4, 50522: 2, 50529: 1, 50536: 4, 50542: 1, 50566: 3,
    50567: 2, 50572: 4, 50580: 1, 50587: 1, 50593: 3, 50598: 2, 50605: 2, 50617: 4,
    50618: 2, 50623: 3, 50628: 1, 50632: 4, 50638: 2, 50644: 1, 50649: 4, 50656: 4,
    50755: 3, 50767: 1, 50773: 3, 50792: 1,
    50892: 4, 50897: 2, 50902: 1, 50906: 3, 50924: 4, 50931: 4, 50942: 3,
    51029: 1, 51039: 4, 51042: 3, 51048: 4, 51054: 3, 51059: 2, 51066: 2, 51077: 1,
    51078: 4, 51083: 3, 51090: 1, 51096: 4, 51107: 3, 51125: 2,
    51297: 4, 51302: 4, 51309: 3, 51316: 1, 51322: 3, 51345: 4,
    51436: 4, 51441: 1, 51445: 3, 51451: 4, 51457: 3, 51462: 3, 51469: 3, 51480: 1,
    51481: 1, 51486: 4, 51494: 2, 51500: 4, 51506: 3, 51511: 2, 51518: 2, 51529: 4,
    51702: 3, 51707: 1, 51712: 2, 51714: 4, 51728: 4, 51733: 1, 51740: 1, 51752: 3,
    51837: 1, 51847: 4, 51850: 2, 51868: 4, 51875: 4, 51886: 1,
}
# root qid -> WFR04 point number (only 51790 needed a fresh decision)
WFR04_DEC = {
    51790: 4,
}

STAR = {
    50303: '★不确定（城乡生活，先例分歧：51034→3 vs 51722→2）；备选 WFR02-3',
    50566: '★不确定（回收轮胎作文）；备选 WFR02-4',
    50598: '★不确定（巴黎/外省生活）；备选 WFR02-3',
    50605: '★不确定（Savoyard 不搬家）；备选 WFR02-3',
    50767: '★不确定（Mbappé 榜样）；备选 WFR02-2',
    50792: '★不确定（游戏成瘾）；备选 WFR02-2',
    50892: '★不确定（lycée Camus）；备选 WFR02-2',
    51029: '★不确定（网络主题）；备选 WFR02-4',
    51125: '★不确定（乡村作文）；备选 WFR02-3',
    51441: '★不确定（偶像/榜样）；备选 WFR02-2',
    51457: '★不确定（达喀尔新生活）；备选 WFR02-2',
    51469: '★不确定（塑料建校）；备选 WFR02-4',
    51494: '★不确定（列日/公园）；备选 WFR02-3',
    51500: '★不确定（创业/时尚）；备选 WFR02-1',
    51728: '★不确定（慈善日，先例分歧，备选未定）',
    51733: '★不确定（儿童歌手）；备选 WFR02-4',
    51790: '★不确定（Q8 reformulation 混合文本，出处 Q5/Q6/Q7）；备选 WFR04-6',
}

RE_ROOT = re.compile(
    r"root=(\d+) label='([^']*)' marks=(\S+) n=(\d+) in_batch=(True|False) tags=\[([^\]]*)\]")


def parse_map() -> tuple[dict, dict, dict]:
    groups: dict[int, dict] = {}
    qid2root: dict[int, int] = {}
    root = None
    for line in (ROOT / 'tmp_fr_map.txt').read_text(encoding='utf-8').splitlines():
        if line.startswith('root='):
            m = RE_ROOT.match(line)
            root = int(m.group(1))
            tags = [t.strip().strip("'") for t in m.group(6).split(',') if t.strip()]
            groups[root] = {'label': m.group(2), 'n': int(m.group(4)),
                            'in_batch': m.group(5) == 'True', 'tags': tags, 'qids': []}
        elif line.startswith('    ') and root is not None:
            for q in line.split():
                qid2root[int(q)] = root
                groups[root]['qids'].append(int(q))
    return groups, qid2root, {r: g['qids'] for r, g in groups.items()}


def main() -> None:
    groups, qid2root, _ = parse_map()

    # sanity: decision coverage
    in_batch_roots = {r for r, g in groups.items() if g['in_batch']}
    decided = set(WFR02_DEC) | set(WFR04_DEC)
    assert in_batch_roots == decided, (
        f'missing={sorted(in_batch_roots - decided)} orphan={sorted(decided - in_batch_roots)}')
    for r, g in groups.items():
        if not g['in_batch']:
            assert g['tags'], f'untagged-batch root {r} has no tags to inherit'
        else:
            assert not g['tags'], f'in-batch root {r} unexpectedly has tags {g["tags"]}'

    code_of: dict[int, str] = {}
    for r, g in groups.items():
        if g['tags']:
            code = g['tags'][0]
        elif r in WFR02_DEC:
            code = f'WFR02-{WFR02_DEC[r]}'
        else:
            code = f'WFR04-{WFR04_DEC[r]}'
        for q in g['qids']:
            code_of[q] = code
    # root itself only when in batch
    for r, g in groups.items():
        if g['in_batch']:
            code_of[r] = code_of[g['qids'][0]]

    seen: set[int] = set()
    expected = {'WFR02-p01': 200, 'WFR02-p02': 200, 'WFR02-p03': 200, 'WFR02-p04': 52,
                'WFR04-p01': 150, 'WFR04-p02': 9}
    for pk in PACKS:
        unit = pk.split('-')[0]
        txt = (ANS_DIR / f'{pk}.txt').read_text(encoding='utf-8')
        qids = [int(m.group(2)) for m in re.finditer(r'^\[(\d+)\] (\d+) ', txt, re.M)]
        assert len(qids) == expected[pk], f'{pk}: {len(qids)} qids != {expected[pk]}'
        for q in qids:
            assert q not in seen, f'duplicate qid {q}'
            seen.add(q)
            assert q in code_of, f'{pk}: qid {q} not in map'
            code = code_of[q]
            assert code.startswith(unit + '-'), f'{pk}: qid {q} code {code} wrong unit'

        # decision-mapping comment block (groups with members in this pack)
        pack_roots: list[int] = []
        for q in qids:
            r = qid2root[q]
            if r not in pack_roots:
                pack_roots.append(r)
        lines: list[str] = []
        lines.append(f'# {pk}.ans.txt | ial-french unt 自判 | unit={unit} | {len(qids)} qids')
        lines.append('# 格式: qid CODE（逐题首标；本批 current 为空，无 OK/？）。'
                     '组内根题与子题同码。')
        lines.append(f'# 本文件覆盖的题组（root qid -> 码, 题号, n）：')
        for r in pack_roots:
            g = groups[r]
            note = ''
            if r in STAR:
                note = '  ' + STAR[r]
            tag = '' if g['in_batch'] else '  [继承根题已有标签]'
            lines.append(f'#   {r} -> {code_of[g["qids"][0]]} (Q{g["label"]}, n={g["n"]}){tag}{note}')
        lines.append('# --- 逐题 ---')
        for q in qids:
            if q in STAR:
                lines.append(f'# {STAR[q]}')
            lines.append(f'{q} {code_of[q]}')
        out = ANS_DIR / f'{pk}.ans.txt'
        out.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        print(f'wrote {out.name}: {len(qids)} qid lines + {len(pack_roots)} group comments')

    # global coverage checks
    map_qids = set(qid2root)
    assert seen == map_qids, f'diff pack-map: {sorted(seen ^ map_qids)[:20]}'
    print(f'total qids written: {len(seen)} (map: {len(map_qids)})')


if __name__ == '__main__':
    main()
