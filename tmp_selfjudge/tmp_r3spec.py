import json, sys

path, unit = sys.argv[1], sys.argv[2]
d = json.load(open(path, encoding='utf-8'))
for u in d['units']:
    if u.get('unit_key') == unit or u.get('code') == unit:
        print('UNIT', u.get('unit_key'), u['name'])
        for n in u['nodes']:
            print('===', n['label'], '|', n['title'])
            print(n['text'][:900])
            print()
            for c in n['children']:
                print('  --', c['label'], '|', c['title'])
                print('     ', c['text'][:700].replace('\n', ' | '))
                print()
