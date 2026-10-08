import json
from collections import Counter

d = json.load(open('ielts-data/runs/20261003T140007Z-repair/changed-files.json', encoding='utf-8'))


def cls(rel):
    r = rel.replace('\\', '/')
    if '/tests/' in r or r.startswith('tests/'):
        return 'tests'
    if '/tools/' in r or r.startswith('tools/'):
        return 'tools'
    if r.startswith('docs/') or '/docs/' in r:
        return 'docs'
    if r.endswith('.mjs') or r.endswith('.cjs') or r.endswith('.js'):
        return 'modules'
    if r.endswith('.json') or r.endswith('.jsonl') or r.endswith('.md5'):
        return 'data'
    return 'other:' + r


k = Counter(cls(c['rel']) for c in d['changes'])
print(dict(k))
print('total:', sum(k.values()))
for c in d['changes'][:5]:
    print(c['rel'], c['action'], c['status'])
