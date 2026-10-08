import json, os, sys

m = json.load(open('work/codex_verify/9715-2023-Nov-21-manifest.json', encoding='utf-8'))
regs = m['regions'] if isinstance(m, dict) and 'regions' in m else m
for r in regs:
    if r['role'] == 'ms' and r['page'] in (12, 13):
        print(r['id'], r['question'], r['role'], r['page'], r['bbox'], r['w'], 'x', r['h'], os.path.basename(r['crop']))
