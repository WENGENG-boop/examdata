import re, os, sys

D = 'C:/Users/weo/Desktop/api/examdata/tmp_selfjudge/r2/ial18-physics'

def triage(dump, out):
    txt = open(os.path.join(D, dump), encoding='utf-8').read()
    entries = re.split(r'(?=^##### )', txt, flags=re.M)
    lines = []
    for e in entries:
        m = re.match(r'##### (\d+) (#\S+(?: \S+)?) (\S+mk) parent=(\S+) old=(\S+) conf=(\S+) new=(\S+)', e)
        if not m:
            continue
        qid, label, mk, parent, old, conf, new = m.groups()
        sm = re.search(r'^STEM: (.*)$', e, flags=re.M)
        stem = sm.group(1) if sm else ''
        stem = re.sub(r'[.\s\u2026]+$', '', stem)
        stem = re.sub(r'\s+', ' ', stem)[:300]
        lines.append(f"{qid} {new} {mk} par={parent} | {stem}")
    open(os.path.join(D, out), 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
    print(out, len(lines))

for dump, out in [('_dump13.txt','_tri13.txt'), ('_dump14p01.txt','_tri14p01.txt'),
                  ('_dump14p02.txt','_tri14p02.txt'), ('_dump14p03.txt','_tri14p03.txt')]:
    triage(dump, out)
