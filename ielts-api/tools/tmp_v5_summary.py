import json, sys

with open('ielts-data/runs/20261003T140007Z-repair/evidence/pdf-answer-keys.json', encoding='utf-8') as f:
    d = json.load(f)

out = []
for bk in sorted(d, key=int):
    b = d[bk]
    lines = []
    for tk in b.get('tests', {}):
        t = b['tests'][tk]
        for sk in sorted(t):
            v = t[sk]
            nums = v.get('numbers', [])
            parts = v.get('parts_summary', [])
            ps = []
            for p in parts:
                ps.append('%s:%s%s' % (p.get('part'), p.get('kind', '')[0], p.get('ranges')))
            lines.append('  T%s %-8s n=%-3d src=%-18s %s' % (
                tk, sk, len(nums), v.get('numbers_source'), ' | '.join(ps)))
    out.append('BOOK %s (pages=%s, kp=%s, anomalies=%d)' % (
        bk, b.get('pdf_pages'), b.get('key_pages'), len(b.get('anomalies', []))))
    out.extend(lines)

print('\n'.join(out))
