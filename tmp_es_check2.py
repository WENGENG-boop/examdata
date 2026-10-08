"""Cross-check the WSP04 per-qid decision dict against parent/sibling tags in DB."""
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PACKS = ['WSP04-p01']
QID_RE = re.compile(r'^\[(\d+)\]\s+(\d+)\b', re.M)

# Final WSP04 decisions (qid -> code)
DEC = {
    # 2124
    62369: 'S3', 62375: '4', 62378: '4', 62380: '6', 62385: '6', 62388: '6',
    62389: 'S3', 62390: 'S3', 62391: '4', 62392: '4', 62393: '4',
    62394: '6', 62395: '6', 62396: '6', 62397: '6', 62398: '6',
    # 2125
    62438: '6', 62463: '6', 62475: '4', 62477: '4', 62478: '4',
    62479: '6', 62480: '6', 62481: '4', 62482: '4', 62483: '4', 62484: '4',
    62485: '4', 62486: '4', 62487: '4', 62488: '4',  # (j) corrected: source 62468[7]=WSP04-4
    # 2126
    62541: '4', 62563: '6', 62565: '6', 62568: '6', 62571: '5',  # (b) corrected: source 62547[5]=WSP04-5
    62572: '6', 62575: '6', 62576: '6', 62577: '6', 62578: '6',
    # 2129
    62725: '6', 62728: '6', 62732: '6', 62747: '4', 62760: '4', 62761: '4', 62763: '4',
    # 2131
    62868: '6', 62869: '6', 62873: '1', 62879: '6', 62892: '6', 62895: '6', 62896: '5',
    # 2133
    62993: '2', 63030: '6', 63033: '6',
    # 2136
    63209: '6', 63210: '6', 63211: 'S2', 63212: 'S2', 63213: 'S2',
    63214: '4', 63215: '4', 63216: '4', 63217: '4', 63218: '4',
    # 2137
    63295: '6', 63296: '6', 63297: '6', 63298: '6', 63300: '6', 63301: '6',
    63302: '6', 63303: '6', 63304: '6',
    # 2139
    63393: '4', 63403: 'S2', 63418: 'S2', 63429: '3', 63431: 'S2', 63432: 'S2',
    63433: '7', 63434: '7', 63436: '7', 63437: '7', 63438: '7',
    # 2142
    63592: '6', 63594: '6', 63597: '6', 63605: '3', 63612: '2', 63619: '3',
    63620: '3', 63625: '2', 63626: '2', 63627: '2', 63628: '2',
    # 2145
    63765: '6', 63775: '4', 63779: '6', 63795: 'S2', 63805: '2', 63807: '2',
    63808: 'S2', 63810: 'S2', 63813: 'S2', 63814: 'S2',
    # 2147
    63903: '6', 63909: '6', 63937: '1', 63938: '1', 63940: '6', 63941: '4',
    63942: '4', 63944: '3', 63946: '3',
    # 2148
    63991: '5', 64002: '6', 64003: '6', 64004: '6', 64010: '6', 64016: '3',
    64031: '3', 64033: '3', 64037: '3',
}

con = sqlite3.connect(f'file:{ROOT / ".data" / "examdata.db"}?mode=ro', uri=True)
con.row_factory = sqlite3.Row

txt = (ROOT / 'tmp_selfjudge' / 'unt' / 'ial-spanish' / 'WSP04-p01.txt').read_text(encoding='utf-8')
pack_qids = [int(m.group(2)) for m in QID_RE.finditer(txt)]

print(f'pack qids: {len(pack_qids)}, decision dict: {len(DEC)}')
missing = [q for q in pack_qids if q not in DEC]
extra = [q for q in DEC if q not in pack_qids]
print('missing from dict:', missing)
print('extra in dict:', extra)

def tags_of(qid):
    return [(r['code'], r['source']) for r in con.execute(
        '''SELECT tn.code, qt.source FROM question_taxonomy qt
           JOIN taxonomy_node tn ON tn.id=qt.node_id WHERE qt.question_id=?''', (qid,))]

print()
print('=== parent/sibling tag cross-check ===')
for qid in pack_qids:
    r = con.execute('SELECT id, paper_id, parent_id, number_path FROM question WHERE id=?', (qid,)).fetchone()
    pid, parent = r['paper_id'], r['parent_id']
    if parent:
        ptags = tags_of(parent)
        sibs = con.execute('SELECT id FROM question WHERE parent_id=? AND id!=?', (parent, qid)).fetchall()
        stags = {}
        for s in sibs:
            t = tags_of(s['id'])
            if t:
                stags[s['id']] = t
        note = ''
        assigned = DEC[qid]
        norm = lambda c: c.replace('WSP04-', '')
        pt_codes = [norm(c) for c, _ in ptags]
        sib_codes = [norm(c) for ts in stags.values() for c, _ in ts]
        pool = pt_codes + sib_codes
        if pool:
            from collections import Counter
            cnt = Counter(pool)
            top = cnt.most_common(2)
            if assigned not in cnt:
                note = f'  <-- NOT in parent/sib pool {top}'
            elif cnt[assigned] == top[0][1]:
                note = '  (matches top)'
        print(f"{qid} p{pid} {r['number_path']:8s} -> {assigned:3s} parent_tags={ptags} sib_tags={ {k: v for k, v in list(stags.items())[:4]} }{note}")
