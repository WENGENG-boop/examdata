import json, sys
from pathlib import Path

BR = Path('C:/Users/weo/Desktop/api/cie-location-batch')
slug = sys.argv[1] if len(sys.argv) > 1 else '0413-2026-Jun-11'
m = json.load(open(BR / 'work' / 'codex_verify' / f'{slug}-manifest.json', encoding='utf-8'))
sheets = m['sheets']
print('sheets:', len(sheets))
for s in sheets[:12]:
    p = s.get('path', '?')
    name = p.split('\\')[-1].split('/')[-1]
    print(name, '| ids:', s.get('ids'))
