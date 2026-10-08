import json

cat = json.load(open('ielts-data/runs/20261003T140007Z-repair/audio/audio-catalog.json', encoding='utf-8'))
print('== candidate audio (26) ==')
for r in cat['records']:
    if r.get('status') == 'candidate':
        print(r.get('identity') or r.get('audio_id'), '|', r.get('source') or r.get('derived_from'), '|', r.get('reason') or '')
print()
print('== unverified identity (26) sample fields ==')
n = 0
for r in cat['records']:
    if r.get('identity_status') == 'unverified':
        n += 1
        if n <= 5:
            print(json.dumps(r, ensure_ascii=False)[:300])
print('total unverified:', n)

print()
print('== answer_form_mismatch in cam21 alignment ==')
import glob
for p in sorted(glob.glob('ielts-data/runs/20261003T140007Z-repair/alignment/cambridge_21*.json')):
    d = json.load(open(p, encoding='utf-8'))
    al = d.get('provider', {}).get('alignment', {})
    for q in al.get('questions', []):
        for w in (q.get('windows') or [q]):
            if isinstance(w, dict) and w.get('reason') == 'answer_form_mismatch' or (isinstance(w, dict) and 'form_mismatch' in json.dumps(w.get('reason') or w.get('status') or '')):
                print(p.split('alignment/')[-1], json.dumps(w, ensure_ascii=False)[:250])
