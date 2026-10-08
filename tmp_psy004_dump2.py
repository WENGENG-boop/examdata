import json, sys
from pathlib import Path
from sqlalchemy import select, create_engine
from sqlalchemy.orm import Session

sys.path.insert(0, r'C:/Users/weo/Desktop/api/examdata')
from examdata.core import models as m

out = []
eng = create_engine('sqlite:///C:/Users/weo/Desktop/api/examdata/.data/examdata.db')
s = Session(eng)

# PART 1: all taxonomy nodes for the four units
for unit in ['WPS01', 'WPS02', 'WPS03', 'WPS04']:
    rows = s.execute(select(m.TaxonomyNode).where(
        m.TaxonomyNode.code.like(unit + '-%')).order_by(m.TaxonomyNode.code)).scalars().all()
    out.append(f'===== {unit} nodes ({len(rows)}) =====')
    for n in rows:
        out.append(f'{n.code} | {n.name[:110]}')

# PART 2: question contexts
qids = [64728, 64737, 64890, 64905, 64910, 64916, 64921, 64967, 64968,
        65004, 65005, 65006, 65007, 65008, 65091, 65094, 65099, 65103,
        65122, 65123, 65124, 64820, 64822, 65140, 65144, 65106, 65111,
        65060, 64951, 64952, 64985, 64986, 64987, 65070, 65071, 65072, 65073]
out.append('===== Q CONTEXTS =====')
for qid in qids:
    q = s.get(m.Question, qid)
    if not q:
        out.append(f'[{qid}] MISSING')
        continue
    paper = s.get(m.Paper, q.paper_id) if q.paper_id else None
    doc = s.get(m.Document, paper.document_id) if paper else None
    par = s.get(m.Question, q.parent_id) if q.parent_id else None
    out.append(f'[{qid}] {doc.title if doc else "?"} | {q.number_label} | parent={q.parent_id}')
    if par:
        out.append(f'   PAR {par.number_label}: {par.stem_text[:260].replace(chr(10), " ")}')
    out.append(f'   OWN: {q.stem_text[:220].replace(chr(10), " ")}')

# PART 3: applied rows
app = Path(r'C:/Users/weo/Desktop/api/examdata/.data/tagging/review-export/ial-psychology/decisions')
out.append('===== decisions dir =====')
for f in sorted(app.iterdir()):
    out.append(f'{f.name} ({f.stat().st_size} bytes)')
cand = sorted(set(list(app.glob('*.applied.jsonl')) + list(app.glob('applied*.jsonl'))))
out.append('applied files: ' + str([str(c) for c in cand]))
rows = []
for c in cand:
    for line in c.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            pass
out.append(f'total applied rows: {len(rows)}')
targets = {61823, 64660, 64657, 61382, 61759, 64405, 64728, 65359, 65343,
           65264, 65591, 65592, 65854, 65855, 61821, 61822, 64268, 65509,
           65510, 65821, 64940, 64941, 64865, 64251, 64250, 64441, 64710,
           64507, 61917, 61928, 64288, 65568, 65569, 65713, 65723, 65744,
           65754, 65581, 65559, 65892, 64598, 61859, 64656, 64464, 64569, 65067}
kw = ['假设', '抽样', '样本', 'IV', '变量', '实验设计', '信度', '改进']
out.append('===== applied rows (targets+keywords) =====')
for r in rows:
    qid = r.get('question_id')
    rs = str(r.get('reason', ''))
    if qid in targets or any(k in rs for k in kw):
        out.append(json.dumps(r, ensure_ascii=False))
out.append('===== applied rows (key codes in code/reason) =====')
codes = ['9.1.13', '9.3.1', '9.3.2', '9.1.6', '9.1.9', '5.4.2', '6.3.1',
         '7.3.1', '1.2.5', '1.4.1', '4.2.6', '4.2.5', '3.2.7', '2.2.11', '4.2.8', '3.1.5']
for r in rows:
    rs = str(r.get('reason', '')) + '|' + str(r.get('code', ''))
    if any(k in rs for k in codes):
        out.append(json.dumps(r, ensure_ascii=False))

Path(r'C:/Users/weo/Desktop/api/examdata/tmp_psy004_dump2.txt').write_text(
    '\n'.join(out), encoding='utf-8')
print('written', len(out), 'lines')
