# -*- coding: utf-8 -*-
import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
R = 'ielts-data/runs/20261003T140007Z-repair'
P = 'tmp_audit_ielts/completeness_20261003'

def pteq(path):
    d = json.load(open(path, encoding='utf-8'))
    return {q['number']: q.get('answer') for q in (d.get('questions') or [])}

def ent(path):
    d = json.load(open(path, encoding='utf-8'))
    return {e['number']: e.get('value') for e in d['entries']}

p1l = pteq(f'{P}/pte-11-1-listening.json')
p4l = pteq(f'{P}/pte-11-4-listening.json')
i4l = ent(f'{R}/scratch/s18/answers/book_11/test_4_listening_shared.json')
o4l = ent(f'{R}/official-keys/book_11/test_4_listening.json')
print('=== LISTENING: pte-1L | pte-4L | INDEX t4L | OFF(extraction) t4L ===')
for n in range(1, 41):
    print(f"{n:>2} | {str(p1l.get(n))[:28]!r:30} | {str(p4l.get(n))[:28]!r:30} | {str(i4l.get(n))[:28]!r:30} | {str(o4l.get(n))[:28]!r:30}")

p1r = pteq(f'{P}/pte-11-1-reading.json')
p4r = pteq(f'{P}/pte-11-4-reading.json')
i4r = ent(f'{R}/scratch/s18/answers/book_11/test_4_reading_academic.json')
o4r = ent(f'{R}/official-keys/book_11/test_4_reading.json')
print()
print('=== READING: pte-1R | pte-4R | INDEX t4R | OFF(extraction) t4R ===')
for n in range(1, 41):
    print(f"{n:>2} | {str(p1r.get(n))[:28]!r:30} | {str(p4r.get(n))[:28]!r:30} | {str(i4r.get(n))[:28]!r:30} | {str(o4r.get(n))[:28]!r:30}")
