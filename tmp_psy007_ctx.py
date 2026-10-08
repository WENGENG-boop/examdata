import sys, json, glob, os
from sqlalchemy import select, create_engine
from sqlalchemy.orm import Session

sys.path.insert(0, r'C:/Users/weo/Desktop/api/examdata')
from examdata.core import models as m

eng = create_engine('sqlite:///C:/Users/weo/Desktop/api/examdata/.data/examdata.db')
s = Session(eng)
out = []

# ---- 1. Jan 2021 Unit 3 paper structure ----
out.append('##### PAPER: Unit 3 (WPS03) - January 2021 — all questions #####')
docs = s.execute(select(m.Document).where(m.Document.title == 'Question Paper - Unit 3 (WPS03) - January 2021')).scalars().all()
for d in docs:
    for p in s.execute(select(m.Paper).where(m.Paper.document_id == d.id)).scalars().all():
        qs = s.execute(select(m.Question).where(m.Question.paper_id == p.id).order_by(m.Question.id)).scalars().all()
        for q in qs:
            first = (q.stem_text or '').replace(chr(10), ' ')[:90]
            out.append(f'{q.id} | {q.number_label} | m={q.marks} | par={q.parent_id} | {first}')

# ---- 2. Jan 2021 Unit 2 paper around 65977 ----
out.append('')
out.append('##### PAPER: Unit 2 (WPS02) - January 2021 — Q around 65976-65977 #####')
docs = s.execute(select(m.Document).where(m.Document.title == 'Question Paper - Unit 2 (WPS02) - January 2021')).scalars().all()
for d in docs:
    for p in s.execute(select(m.Paper).where(m.Paper.document_id == d.id)).scalars().all():
        qs = s.execute(select(m.Question).where(m.Question.paper_id == p.id).order_by(m.Question.id)).scalars().all()
        for q in qs:
            first = (q.stem_text or '').replace(chr(10), ' ')[:120]
            out.append(f'{q.id} | {q.number_label} | m={q.marks} | par={q.parent_id} | {first}')

# ---- 3. precedents across decisions files ----
out.append('')
out.append('##### PRECEDENT SEARCH #####')
dec_dir = r'C:/Users/weo/Desktop/api/examdata/.data/tagging/review-export/ial-psychology/decisions'
all_rows = []
for f in glob.glob(dec_dir + '/*.jsonl'):
    for line in open(f, encoding='utf-8'):
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        all_rows.append((os.path.basename(f), r))

KEYS = ['volunteer', 'quantitative data', 'qualitative data', 'open-ended',
        'improvement', 'to what extent', 'addiction', 'sampling', '9.3.2', '9.2.1',
        '6.3.1', '7.3.1', '5.3.1', '5.3.4', 'reinforcer', 'psychosexual', 'Freud']
for k in KEYS:
    out.append(f'--- keyword: {k} ---')
    cnt = 0
    for fn, r in all_rows:
        txt = json.dumps(r, ensure_ascii=False)
        if k.lower() in txt.lower():
            cnt += 1
            if cnt <= 14:
                out.append(f'  [{fn}] {txt[:260]}')
    if cnt > 14:
        out.append(f'  ... total {cnt}')
    if cnt == 0:
        out.append('  (none)')

# ---- 4. all decisions involving these 43 ids ----
out.append('')
out.append('##### any prior decisions for batch-007 ids #####')
IDS = [65939, 65977, 65998, 65999, 66006, 66030, 66036, 66040, 66042, 66057,
       66058, 66059, 66067, 66068, 66069, 66103, 66104, 66106, 66111, 66112,
       66113, 66114, 66115, 66122, 66123, 66126, 66150, 66154, 66170, 66180,
       66196, 66203, 66209, 66214, 66241, 66257, 66258, 66259, 66262, 66268,
       66270, 66281, 66283]
for fn, r in all_rows:
    if r.get('question_id') in IDS:
        out.append(f'  [{fn}] {json.dumps(r, ensure_ascii=False)[:220]}')

open(r'C:/Users/weo/Desktop/api/examdata/tmp_psy007_ctx.txt', 'w', encoding='utf-8').write('\n'.join(out))
print('written', len(out), 'lines')
