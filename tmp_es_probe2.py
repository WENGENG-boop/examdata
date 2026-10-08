"""List all pack qids per WSP04 paper with number_path, sorted by qid."""
import re
import sqlite3
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PACKS = ['WSP02-p01', 'WSP02-p02', 'WSP02-p03', 'WSP02-p04', 'WSP04-p01']
QID_RE = re.compile(r'^\[(\d+)\]\s+(\d+)\b', re.M)

con = sqlite3.connect(f'file:{ROOT / ".data" / "examdata.db"}?mode=ro', uri=True)
con.row_factory = sqlite3.Row

all_qids = []
for pack in PACKS:
    txt = (ROOT / 'tmp_selfjudge' / 'unt' / 'ial-spanish' / f'{pack}.txt').read_text(encoding='utf-8')
    all_qids += [int(m.group(2)) for m in QID_RE.finditer(txt)]

by_paper = defaultdict(list)
for qid in all_qids:
    r = con.execute('SELECT paper_id, number_path FROM question WHERE id = ?', (qid,)).fetchone()
    by_paper[r['paper_id']].append((qid, r['number_path']))

wsp04 = [2124, 2125, 2126, 2129, 2131, 2133, 2136, 2137, 2139, 2142, 2145, 2147, 2148]
for pid in wsp04:
    items = sorted(by_paper[pid])
    print(f'== paper {pid} ({len(items)}) ==')
    print('  ' + '; '.join(f'{q}={p}' for q, p in items))

print()
print('== WSP02 per paper Q-order qid lists (for reference) ==')
wsp02 = [2123, 2127, 2128, 2130, 2132, 2134, 2135, 2138, 2140, 2141, 2143, 2144, 2146, 2149]
for pid in wsp02:
    items = sorted(by_paper[pid])
    print(f'== paper {pid} ({len(items)}) ==')
    print('  ' + '; '.join(f'{q}={p}' for q, p in items))
