import json
R = r'C:/Users/weo/Desktop/api/ielts-data/runs/20261003T140007Z-repair'

def load(p):
    d = json.load(open(p, encoding='utf-8'))
    out = {}
    for e in d.get('entries', []):
        n = e.get('number')
        v = e.get('value', e.get('values'))
        if isinstance(n, int) and v is not None:
            out[n] = v
    return out

def norm(s):
    return str(s).lower().strip().replace('\u2019', "'")

def matches(a, b):
    na, nb = norm(a), norm(b)
    if na == nb:
        return True
    for part in na.split('//'):
        if part.strip() == nb:
            return True
    for part in nb.split('//'):
        if part.strip() == na:
            return True
    return False

for skill, suf in [('listening', 'shared'), ('reading', 'academic')]:
    off = {t: load(f'{R}/official-keys/book_11/test_{t}_{skill}.json') for t in [1, 2, 3, 4]}
    idx = {t: load(f'{R}/scratch/s18/answers/book_11/test_{t}_{skill}_{suf}.json') for t in [1, 2, 3, 4]}
    print(f'== {skill} == (official tN vs index tM match counts)')
    for t in [1, 2, 3, 4]:
        row = []
        for m in [1, 2, 3, 4]:
            common = set(off[t]) & set(idx[m])
            cnt = sum(1 for n in common if matches(off[t][n], idx[m][n]))
            row.append(f't{m}:{cnt}/{len(common)}')
        best = max(range(1, 5), key=lambda m: sum(1 for n in set(off[t]) & set(idx[m]) if matches(off[t][n], idx[m][n])))
        print(f'official t{t} -> ' + '  '.join(row) + f'   best=idx t{best}')
