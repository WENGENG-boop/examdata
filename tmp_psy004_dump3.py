import json, sys
from pathlib import Path
from sqlalchemy import select, create_engine
from sqlalchemy.orm import Session

sys.path.insert(0, r'C:/Users/weo/Desktop/api/examdata')
from examdata.core import models as m

out = []
eng = create_engine('sqlite:///C:/Users/weo/Desktop/api/examdata/.data/examdata.db')
s = Session(eng)


def tags_of(qid):
    rows = s.execute(select(m.QuestionTaxonomy, m.TaxonomyNode).join(
        m.TaxonomyNode, m.QuestionTaxonomy.node_id == m.TaxonomyNode.id
    ).where(m.QuestionTaxonomy.question_id == qid)).all()
    return [n.code for _, n in rows]


def ctx(qid, par_len=300, own_len=300):
    q = s.get(m.Question, qid)
    if not q:
        out.append(f'[{qid}] MISSING')
        return
    paper = s.get(m.Paper, q.paper_id) if q.paper_id else None
    doc = s.get(m.Document, paper.document_id) if paper else None
    par = s.get(m.Question, q.parent_id) if q.parent_id else None
    out.append(f'[{qid}] {doc.title if doc else "?"} | {q.number_label} | parent={q.parent_id} | marks={q.marks}')
    if par:
        out.append(f'   PAR {par.number_label}: {par.stem_text[:par_len].replace(chr(10), " ")}')
    out.append(f'   OWN: {q.stem_text[:own_len].replace(chr(10), " ")}')
    out.append(f'   TAGS: {tags_of(qid)}')


# PART 1: all 55 batch-004 qids -> tags
b4 = [64737, 64746, 64760, 64776, 64778, 64779, 64781, 64783, 64784, 64791, 64796,
      64809, 64818, 64822, 64826, 64865, 64890, 64897, 64898, 64899, 64900, 64906,
      64907, 64908, 64910, 64918, 64919, 64921, 64940, 64941, 64952, 64968, 64987,
      64989, 64990, 65005, 65007, 65008, 65021, 65048, 65049, 65060, 65067, 65071,
      65072, 65073, 65094, 65101, 65103, 65106, 65111, 65122, 65124, 65140, 65144]
out.append(f'===== batch-004 current tags ({len(b4)}) =====')
for qid in b4:
    q = s.get(m.Question, qid)
    out.append(f'{qid} | {q.number_label if q else "?"} | {tags_of(qid)}')

# PART 2: contexts for the gap questions + key pendings
qids2 = [64778, 64897, 65067, 64952, 64968, 65008, 65005, 65007, 65071, 65072,
         65073, 65094, 65103, 65122, 65124, 64822, 64890, 64910, 64921, 64737,
         65101, 65123, 65100, 65102, 65099, 65070, 65004, 65006, 64951, 64967,
         64820, 64905, 64916, 65091]
out.append('===== Q CONTEXTS (part 2) =====')
for qid in qids2:
    ctx(qid)

# PART 3: children lists for family parents
parents = [64734, 64725, 64951, 64967, 64820, 64905, 64916, 65091, 65099, 64897,
           65122, 65070, 65004, 65006, 64985, 64987, 64737]
out.append('===== CHILDREN =====')
for pid in parents:
    kids = s.execute(select(m.Question).where(m.Question.parent_id == pid)).scalars().all()
    out.append(f'-- parent {pid}: {len(kids)} children')
    for k in sorted(kids, key=lambda x: x.id):
        out.append(f'   {k.id} | {k.number_label} | {tags_of(k.id)} | {k.stem_text[:110].replace(chr(10), " ")}')

# PART 4: contexts for precedent qids
qids4 = [64249, 64250, 64251, 64252, 65359, 65500, 61382, 64657, 61913, 65557,
         65890, 61856, 61870, 64257, 64400, 64507, 64464, 64656, 65704, 65712,
         65713, 65568, 65569, 65580, 65581, 61917, 61928, 64281, 64288, 64298,
         64399, 65744, 65754, 65559, 65892, 61605, 61612, 61621, 65658, 65257, 64569]
out.append('===== Q CONTEXTS (precedents) =====')
for qid in qids4:
    ctx(qid, par_len=200, own_len=150)

# PART 5: ALL applied rows compact
app = Path(r'C:/Users/weo/Desktop/api/examdata/.data/tagging/review-export/ial-psychology/decisions')
rows = []
for c in sorted(set(list(app.glob('*.applied.jsonl')) + list(app.glob('applied*.jsonl')))):
    for line in c.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
out.append(f'===== ALL applied rows ({len(rows)}) =====')
for r in sorted(rows, key=lambda x: x.get('question_id', 0)):
    out.append(f"{r.get('question_id')} | {r.get('decision')} | {r.get('code')} | {str(r.get('reason',''))[:70]}")

Path(r'C:/Users/weo/Desktop/api/examdata/tmp_psy004_dump3.txt').write_text(
    '\n'.join(out), encoding='utf-8')
print('written', len(out), 'lines')
