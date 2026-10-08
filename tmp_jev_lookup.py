import json, sys
from pathlib import Path
p = Path('tmp_jev_full_decisions/ial18-it/applied.jsonl')
qids = set(sys.argv[1:])
for ln in p.read_text(encoding='utf-8').splitlines():
    if not ln.strip():
        continue
    o = json.loads(ln)
    if str(o.get('question_id')) in qids:
        print('='*10, o['question_id'])
        print('code:', o.get('code'), '| decision:', o.get('decision'))
        print('reason:', o.get('reason'))
