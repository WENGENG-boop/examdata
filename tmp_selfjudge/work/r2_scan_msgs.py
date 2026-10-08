"""Scan agent-824 wire.jsonl for main-agent messages containing report-format hints."""
import json

p = (r'C:/Users/weo/.kimi-code/sessions/wd_api_8f9bde7994a5/'
     r'session_d883c71d-510f-483d-9810-d178a60ee98c/agents/agent-824/wire.jsonl')

hits = []
with open(p, encoding='utf-8') as f:
    for i, line in enumerate(f, 1):
        if 'context.append_message' not in line:
            continue
        if '报告' not in line and '格式' not in line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        s = json.dumps(rec, ensure_ascii=False)
        hits.append((i, len(s), s))

print('total hits:', len(hits))
for i, ln, s in hits[-6:]:
    idx = s.find('报告')
    if idx < 0:
        idx = s.find('格式')
    print(f'===== line {i} (len {ln}) =====')
    print(s[max(0, idx - 700):idx + 900])
    print()
