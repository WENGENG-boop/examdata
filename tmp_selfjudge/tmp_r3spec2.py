import json, sys

path, unit = sys.argv[1], sys.argv[2]
full = len(sys.argv) > 3 and sys.argv[3] == 'full'
d = json.load(open(path, encoding='utf-8'))
for u in d['units']:
    if u.get('unit_key') == unit or u.get('code') == unit:
        print('UNIT', u.get('unit_key'), '|', u['name'])
        for n in u['nodes']:
            print('===', n.get('label'), '|', n.get('title'))
            t = n.get('text') or ''
            print(t if full else t[:1500])
            print()
            for c in n.get('children', []):
                print('  --', c.get('label'), '|', c.get('title'))
                ct = (c.get('text') or '').replace('\n', ' | ')
                print('     ', ct if full else ct[:1000])
                print()
