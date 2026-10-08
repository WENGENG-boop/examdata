import json, sys
from pathlib import Path

BR = Path('C:/Users/weo/Desktop/api/cie-location-batch')
key = sys.argv[1]  # e.g. 0413/2026/Jun/11
subject, year, season, paper = key.split('/')
path = BR / 'indexes' / subject / f'{year}-{season}-{paper}' / 'cie-index.json'
idx = json.load(open(path, encoding='utf-8'))
print('index:', path)
print('questions:', len(idx['questions']))
qfilter = sys.argv[2] if len(sys.argv) > 2 else None
for q in idx['questions']:
    if qfilter and q['question'] != qfilter:
        continue
    print(f"\n=== Q {q['question']} (parent={q.get('parent')}) marks={q.get('marks')} uncertain={q.get('uncertain')}")
    print('   text:', (q.get('text') or '')[:100])
    for role in ('qp', 'ms'):
        for r in q.get(role, []):
            print(f"   {role}: p{r['page']} bbox={r['bbox']}")
    print('   notes:', (q.get('notes') or '')[:150])
