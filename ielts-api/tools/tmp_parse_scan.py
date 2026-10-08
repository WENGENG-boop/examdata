import re, sys

path = 'ielts-data/runs/20261003T140007Z-repair/evidence/range-scan-all.txt'
cur = None
out = {}
for line in open(path, encoding='utf-8'):
    line = line.rstrip('\n')
    m = re.match(r'===== BOOK (\d+) pages=(\d+) =====', line)
    if m:
        cur = m.group(1)
        out[cur] = []
        continue
    if cur is None:
        continue
    # listening part headers
    m = re.match(r'p\s*(\d+):\s*(SECTION|SECTON|SECTIO N|SECTION2|SECTON2)\s*(\d+)\s+Questions?\s+(\d+)[-–—一~](\d+)', line, re.I)
    if m:
        out[cur].append(('L', int(m.group(3)), int(m.group(4)), int(m.group(5)), int(m.group(1))))
        continue
    # reading passage headers
    m = re.match(r'p\s*(\d+):\s*You (?:should|are advised to) spend about 20 minutes on Questions?\s+(\d+)[-–—一~](\d+)(.*)', line)
    if m:
        rest = m.group(4)
        pm = re.search(r'Passage\s*(\d)', rest)
        out[cur].append(('R', int(pm.group(1)) if pm else 0, int(m.group(2)), int(m.group(3)), int(m.group(1))))
        continue
    # GT section headers like "SECTION 1         Questions 1-13" already covered by first pattern

for bk in sorted(out, key=int):
    rows = out[bk]
    if not rows:
        print('BOOK %s: (none)' % bk)
        continue
    print('BOOK %s:' % bk)
    for kind, idx, a, b, pg in rows:
        print('  %s%s p%d: %d-%d' % (kind, idx, pg, a, b))
