import re, sys, os
D = 'C:/Users/weo/Desktop/api/examdata/tmp_selfjudge/r2/ial18-physics'
dump = sys.argv[1]
out = sys.argv[2]
qids = sys.argv[3:]
txt = open(os.path.join(D, dump), encoding='utf-8').read()
entries = re.split(r'(?=^##### )', txt, flags=re.M)
by = {}
for e in entries:
    m = re.match(r'##### (\d+)', e)
    if m:
        by[m.group(1)] = e
buf = []
for q in qids:
    e = by.get(q)
    if e is None:
        buf.append(f"##### {q} MISSING")
        buf.append('---')
        continue
    e = re.sub(r'\.{4,}', ' ..', e)
    e = re.sub(r'[\u2026]+', ' ..', e)
    lines = e.split('\n')
    head = lines[0].strip()
    body = '\n'.join(lines[1:])
    ms = ''
    mm = re.search(r'(MS\[[^\]]*\]:.*?)(?=^PARENT=|^SIBS=|\Z)', body, flags=re.M | re.S)
    if mm:
        ms = re.sub(r'\s+', ' ', mm.group(1)).strip()
    st = ''
    sm = re.search(r'^STEM: (.*?)(?=^MS\[|^PARENT=|^SIBS=|\Z)', body, flags=re.M | re.S)
    if sm:
        st = re.sub(r'\s+', ' ', sm.group(1)).strip()
    ps = ''
    pm = re.search(r'^(PARENT=.*)$', body, flags=re.M)
    if pm:
        ps = pm.group(1).strip()
    sm2 = re.search(r'^(SIBS:.*)$', body, flags=re.M)
    if sm2:
        ps += ' ' + sm2.group(1).strip()
    buf.append(head)
    buf.append('STEM: ' + st[:260])
    if ms:
        buf.append('MS: ' + ms[:1500])
    buf.append(ps[:600])
    buf.append('---')
open(os.path.join(D, out), 'w', encoding='utf-8').write('\n'.join(buf) + '\n')
print(out, 'written', len(qids))
