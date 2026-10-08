import sqlite3, re
from pathlib import Path

db = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
db.row_factory = sqlite3.Row

qids = [int(l.split()[1]) for l in Path('tmp_selfjudge/r3/ial-englit/WET03-p01.txt').read_text(encoding='utf-8').splitlines()
        if l.startswith('[') and len(l.split()) > 1]

print('=== STEM CHECK for all 90 ===')
bad = []
for q in qids:
    r = db.execute("SELECT id, number_label, marks, stem_text FROM question WHERE id=?", (q,)).fetchone()
    stem = r['stem_text'] or ''
    flat = re.sub(r'\s+', ' ', stem)
    has_writers = 'the writers of your two chosen texts' in flat
    has_poem = re.search(r'\bpoem\b', flat, re.I) is not None
    m30 = re.search(r'Total for Question\s*\d+\s*[=–-]\s*(\d+)\s*marks', flat)
    mk30 = m30.group(1) if m30 else None
    if not has_writers or has_poem or mk30 != '30':
        bad.append((q, has_writers, has_poem, mk30, flat[:150]))
print('stem anomalies (not "writers/two chosen texts", or mentions poem, or total != 30):', len(bad))
for b in bad:
    print('  ', b)

print()
print('=== number_label vs marks for the 90 ===')
from collections import Counter
c = Counter((r['number_label'], r['marks']) for r in
            db.execute(f"SELECT number_label, marks FROM question WHERE id IN ({','.join('?'*len(qids))})", qids))
for k, v in sorted(c.items()):
    print('  label', k[0], 'marks', k[1], '->', v)

print()
print('=== FULL MS for selected qids ===')
for q in [49359, 49842, 49360, 49846, 49969, 50154]:
    rows = db.execute("SELECT number_label, answer_text, guidance FROM mark_scheme_entry WHERE question_id=?", (q,)).fetchall()
    qrow = db.execute("SELECT number_label, marks, substr(stem_text,1,80) s FROM question WHERE id=?", (q,)).fetchone()
    print('='*100)
    print(f"qid {q} | q.number={qrow['number_label']!r} marks={qrow['marks']} | stem: {qrow['s']!r}")
    for r in rows:
        t = re.sub(r'\s+', ' ', r['answer_text'] or '')
        print(f"  MS[{r['number_label']}] len={len(t)} : {t[:700]}")
        print('  guidance:', (r['guidance'] or '')[:200])
