import sys
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


def head(qid):
    q = s.get(m.Question, qid)
    if not q:
        return f'[{qid}] MISSING'
    paper = s.get(m.Paper, q.paper_id) if q.paper_id else None
    doc = s.get(m.Document, paper.document_id) if paper else None
    return f'[{qid}] {doc.title if doc else "?"} | {q.number_label} | marks={q.marks} | parent={q.parent_id} | TAGS={tags_of(qid)}'


done = set()


def full(qid, n=2000):
    if qid in done:
        return
    done.add(qid)
    out.append('===== ' + head(qid))
    q = s.get(m.Question, qid)
    if q:
        out.append((q.stem_text or '')[:n])


def ctx(qid, par_len=300, own_len=300):
    if qid in done:
        return
    done.add(qid)
    q = s.get(m.Question, qid)
    if not q:
        out.append(f'[{qid}] MISSING')
        return
    out.append(head(qid))
    par = s.get(m.Question, q.parent_id) if q.parent_id else None
    if par:
        out.append(f'   PAR {par.number_label}: {(par.stem_text or "")[:par_len].replace(chr(10), " ")}')
    out.append(f'   OWN: {(q.stem_text or "")[:own_len].replace(chr(10), " ")}')


# PART 1: full stems for option-list questions + auto parents
out.append('##### PART 1: full stems #####')
for qid in [64249, 64250, 64251, 64252, 65070, 65071, 65072, 65073,
            65005, 65006, 65007, 65004, 64775, 64776, 64777, 64778,
            65065, 65066, 65067, 65068]:
    full(qid)
    q = s.get(m.Question, qid)
    if q and q.parent_id:
        full(q.parent_id, 2500)

# PART 2: contexts for pendings/precedents
out.append('##### PART 2: contexts #####')
for qid in [61823, 65398, 65298, 65535, 65666, 64987, 64985, 64986,
            65359, 65500, 61856, 64464, 64656]:
    ctx(qid)

# PART 3: children lists
out.append('##### PART 3: children #####')
for pid in [64775, 65065, 65070]:
    kids = s.execute(select(m.Question).where(m.Question.parent_id == pid)).scalars().all()
    out.append(f'-- parent {pid}: {len(kids)} children')
    for k in sorted(kids, key=lambda x: x.id):
        out.append(f'   {k.id} | {k.number_label} | {tags_of(k.id)} | {(k.stem_text or "")[:130].replace(chr(10), " ")}')
for qid in [64249, 64251]:
    q = s.get(m.Question, qid)
    if q and q.parent_id:
        kids = s.execute(select(m.Question).where(m.Question.parent_id == q.parent_id)).scalars().all()
        out.append(f'-- parent {q.parent_id} (of {qid}): {len(kids)} children')
        for k in sorted(kids, key=lambda x: x.id):
            out.append(f'   {k.id} | {k.number_label} | {tags_of(k.id)} | {(k.stem_text or "")[:130].replace(chr(10), " ")}')

# PART 4: keyword searches
out.append('##### PART 4: searches #####')


def search(pat, cap=60):
    out.append(f'--- search: {pat}')
    rows = s.execute(select(m.Question).where(m.Question.stem_text.like(pat)).order_by(m.Question.id)).scalars().all()
    out.append(f'    {len(rows)} hits')
    for k in rows[:cap]:
        out.append(f'   {k.id} | {k.number_label} | {tags_of(k.id)} | {(k.stem_text or "")[:120].replace(chr(10), " ")}')


search('%contemporary%')
search('%quantitative data%')
search('%improve the sample%')
search('%sample of participants%')

out_path = r'C:/Users/weo/Desktop/api/examdata/tmp_psy004_dump4.txt'
with open(out_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(out))
print('written', len(out), 'lines')
