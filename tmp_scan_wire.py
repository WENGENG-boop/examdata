"""扫描本会话 wire.jsonl, 找历史上对 locator.py 的 Edit 调用, 看 old_string 的编码方式。"""
import json
from pathlib import Path

WIRE = Path.home() / '.kimi-code/sessions/wd_api_8f9bde7994a5/session_d883c71d-510f-483d-9810-d178a60ee98c/agents/main/wire.jsonl'

hits = []
with WIRE.open('r', encoding='utf-8') as fh:
    for lineno, line in enumerate(fh, 1):
        if 'old_string' not in line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        s = json.dumps(rec, ensure_ascii=False)
        if 'locator.py' in s:
            hits.append((lineno, rec))

print('total edit-records touching locator.py:', len(hits))
for lineno, rec in hits[-4:]:
    print('==== line', lineno)
    dump = json.dumps(rec, ensure_ascii=False)
    print(dump[:1800])
    print('...')
