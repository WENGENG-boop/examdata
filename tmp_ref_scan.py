"""Scan Edexcel MS entries for official spec refs of form (x.y.z.w) and
compare against the question's current taxonomy label.

Usage: python tmp_ref_scan.py
Output: per-subject counts + mismatch list.
"""
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
con = sqlite3.connect(f"file:{ROOT / '.data' / 'examdata.db'}?mode=ro", uri=True)
c = con.cursor()

SLUGS = [
    'ial-accounting', 'ial-englang', 'ial-englit', 'ial-french', 'ial-geography',
    'ial-german', 'ial-greek', 'ial-history', 'ial-law', 'ial-maths',
    'ial-psychology', 'ial-spanish', 'ial18-biology', 'ial18-business',
    'ial18-chemistry', 'ial18-economics', 'ial18-it', 'ial18-mathematics',
    'ial18-mathematics-extra', 'ial18-physics',
]

pat = re.compile(r'\((\d+\.\d+\.\d+\.\d+)\)')

rows = c.execute(f"""
select mse.id, mse.question_id, mse.number_label, mse.answer_text,
       mse.guidance, s.slug
from mark_scheme_entry mse
join question q on q.id = mse.question_id
join paper p on p.id = q.paper_id
join document d on d.id = p.document_id
join subject s on s.id = d.subject_id
where s.slug in ({','.join('?' * len(SLUGS))})
  and mse.question_id is not null
""", SLUGS).fetchall()
print(f'scanned MS rows: {len(rows)}')

refs_total = 0
per_subject = {}
mismatches = []
no_label = []
multi_ref = []

for mid, qid, nlab, ans, guid, slug in rows:
    text = (ans or '') + ' ' + (guid or '')
    found = pat.findall(text)
    if not found:
        continue
    refs_total += len(found)
    st = per_subject.setdefault(slug, {'refs': 0, 'qids': 0, 'match': 0, 'mismatch': 0, 'nolabel': 0})
    st['refs'] += len(found)
    st['qids'] += 1

    labels = [r[0] for r in c.execute(
        "select tn.code from question_taxonomy qt join taxonomy_node tn on tn.id=qt.node_id "
        "where qt.question_id=? order by tn.code", (qid,))]
    suffix = None
    if labels:
        lab = labels[0]
        suffix = lab.split('-', 1)[1] if '-' in lab else lab

    uniq = sorted(set(found))
    if len(uniq) > 1:
        multi_ref.append((qid, slug, uniq, labels))
    ref = uniq[0]
    windows = ['.'.join(ref.split('.')[:3]), '.'.join(ref.split('.')[1:4])]

    if suffix is None:
        st['nolabel'] += 1
        no_label.append((qid, slug, ref))
    elif suffix in windows:
        st['match'] += 1
    else:
        st['mismatch'] += 1
        mismatches.append((qid, slug, ref, labels, (ans or '')[:180]))

print(f'\nrefs found: {refs_total}')
print('\nper-subject:')
for slug in sorted(per_subject):
    st = per_subject[slug]
    print(f"  {slug:26s} qids={st['qids']:4d} refs={st['refs']:4d} "
          f"match={st['match']:4d} MISMATCH={st['mismatch']:4d} nolabel={st['nolabel']}")

print(f'\n=== MISMATCHES ({len(mismatches)}) ===')
for qid, slug, ref, labels, snippet in mismatches:
    print(f'{qid} [{slug}] ref=({ref}) labels={labels}')
    print('    MS:', re.sub(r'\s+', ' ', snippet)[:160])

print(f'\n=== NO LABEL ({len(no_label)}) ===')
for qid, slug, ref in no_label:
    print(f'{qid} [{slug}] ref=({ref})')

print(f'\n=== MULTI REF ({len(multi_ref)}) ===')
for qid, slug, uniq, labels in multi_ref:
    print(f'{qid} [{slug}] refs={uniq} labels={labels}')
