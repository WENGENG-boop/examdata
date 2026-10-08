import re, sys, os
D = 'C:/Users/weo/Desktop/api/examdata/tmp_selfjudge/r2/ial18-physics'
dumps = ['_dump13.txt', '_dump14p01.txt', '_dump14p02.txt', '_dump14p03.txt']
maps = {}
for d in dumps:
    txt = open(os.path.join(D, d), encoding='utf-8').read()
    maps[d] = set(re.findall(r'^##### (\d+)', txt, flags=re.M))
qids = sys.argv[1:]
out = []
for q in qids:
    where = [d for d in dumps if q in maps[d]]
    out.append(f"{q}: {' '.join(where) if where else 'NONE'}")
open(os.path.join(D, '_loc.txt'), 'w', encoding='utf-8').write('\n'.join(out) + '\n')
print('ok', len(qids))
