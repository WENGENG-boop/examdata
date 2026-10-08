import json, sys
from pathlib import Path
from collections import Counter

BR = Path('C:/Users/weo/Desktop/api/cie-location-batch')
slug = sys.argv[1]
recs = json.load(open(BR / 'work' / 'codex_verify' / f'{slug}-records.json', encoding='utf-8'))
print('total records:', len(recs))

# group by role
print('by role:', Counter(r.get('role') for r in recs))
print('with issues:', sum(1 for r in recs if r.get('issues')))
print('content_complete false:', sum(1 for r in recs if not r.get('checks', {}).get('content_complete')))
print('boundary_checked false:', sum(1 for r in recs if not r.get('checks', {}).get('boundary_checked')))
print('role_matches false:', sum(1 for r in recs if not r.get('checks', {}).get('role_matches')))
print()
print('=== records with issues ===')
for r in recs:
    if r.get('issues'):
        c = r.get('checks', {})
        print(f"{r['question']}/{r['role']}/p{r['page']} bbox={r['bbox']}")
        print(f"   issues: {r['issues']}")
        print(f"   checks: cc={c.get('content_complete')} bc={c.get('boundary_checked')} rm={c.get('role_matches')}")
        print(f"   observed: {str(c.get('observed',''))[:110]}")
        cx = r.get('codex', {})
        print(f"   codex: qnums={cx.get('question_numbers')} edge_cut={cx.get('edge_cut')}")
        print()
