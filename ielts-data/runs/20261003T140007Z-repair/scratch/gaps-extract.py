import json
from collections import Counter

d = json.load(open('ielts-data/indexes/rev-8b21015ab64bb73c/questions.json', encoding='utf-8'))

# 1) answer status missing/empty slots
print('== missing/empty answer slots ==')
for q in d['questions']:
    st = q.get('answer_status') or (q.get('answer') or {}).get('status')
    if st in ('missing', 'empty'):
        print(q.get('identity'), q.get('question_number') or q.get('number'), st,
              q.get('book'), q.get('skill'), q.get('test'), q.get('part'))

print()
print('== missing_options by book/skill/test/part ==')
c = Counter()
for q in d['questions']:
    if q.get('content_status') == 'missing_options':
        c[(q.get('book'), q.get('skill'), q.get('variant'), q.get('test'), q.get('part'))] += 1
for k, v in sorted(c.items()):
    print(k, v)
print('total:', sum(c.values()))

print()
print('== missing_asset by book/skill/test/part ==')
c2 = Counter()
for q in d['questions']:
    if q.get('content_status') == 'missing_asset':
        c2[(q.get('book'), q.get('skill'), q.get('variant'), q.get('test'), q.get('part'))] += 1
for k, v in sorted(c2.items()):
    print(k, v)
print('total:', sum(c2.values()))

print()
print('== partial content_status by book/skill/test/part ==')
c3 = Counter()
for q in d['questions']:
    if q.get('content_status') == 'partial':
        c3[(q.get('book'), q.get('skill'), q.get('variant'), q.get('test'), q.get('part'))] += 1
for k, v in sorted(c3.items()):
    print(k, v)
print('total:', sum(c3.values()))
