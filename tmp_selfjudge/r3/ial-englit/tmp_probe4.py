import sqlite3, re
from pathlib import Path

db = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
db.row_factory = sqlite3.Row

qids = [int(l.split()[1]) for l in Path('tmp_selfjudge/r3/ial-englit/WET03-p01.txt').read_text(encoding='utf-8').splitlines()
        if l.startswith('[') and len(l.split()) > 1]

print('=== per-question final check ===')
issues = 0
for q in qids:
    r = db.execute("SELECT id, paper_id, number_label, marks, stem_text FROM question WHERE id=?", (q,)).fetchone()
    flat = re.sub(r'\s+', ' ', r['stem_text'] or '')
    tail = flat[-120:]
    ms = db.execute("SELECT count(*) n, group_concat(answer_text, ' ') all_txt FROM mark_scheme_entry WHERE question_id=?", (q,)).fetchone()
    mst = re.sub(r'\s+', ' ', ms['all_txt'] or '')
    prose_kw = any(k in mst for k in ('Section B: Prose', 'Candidates may include'))
    poem_kw = bool(re.search(r'\bpoem\b|\bpoetry\b|commentary', mst, re.I))
    stem_ok = ('two chosen texts' in flat) and ('30 marks' in tail or '30 marks' in flat)
    flag = []
    if not stem_ok: flag.append('STEM')
    if poem_kw: flag.append('MS-POEM?')
    if not prose_kw: flag.append('MS-no-indicative')
    if flag:
        issues += 1
        print(f'  {q} marks={r["marks"]} flags={flag}')
        print('    tail:', tail)
        print('    ms head:', mst[:200])
print('total flagged:', issues)

# MS poetry-word hits summary
print()
print('=== MS poem/poetry word scan (should be 0 for prose) ===')
hits = []
for q in qids:
    ms = db.execute("SELECT group_concat(answer_text, ' ') t FROM mark_scheme_entry WHERE question_id=?", (q,)).fetchone()
    t = re.sub(r'\s+', ' ', ms['t'] or '')
    if re.search(r'\bpoem\b|\bpoetry\b', t, re.I):
        hits.append(q)
print('qids with poem/poetry in MS:', hits)

# verify 49846 stem fully
r = db.execute("SELECT stem_text FROM question WHERE id=49846").fetchone()
print()
print('=== 49846 full stem ===')
print(repr(r['stem_text']))
