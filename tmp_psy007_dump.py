import sys
from sqlalchemy import select, create_engine
from sqlalchemy.orm import Session

sys.path.insert(0, r'C:/Users/weo/Desktop/api/examdata')
from examdata.core import models as m

eng = create_engine('sqlite:///C:/Users/weo/Desktop/api/examdata/.data/examdata.db')
s = Session(eng)

IDS = [65939, 65977, 65998, 65999, 66006, 66030, 66036, 66040, 66042, 66057,
       66058, 66059, 66067, 66068, 66069, 66103, 66104, 66106, 66111, 66112,
       66113, 66114, 66115, 66122, 66123, 66126, 66150, 66154, 66170, 66180,
       66196, 66203, 66209, 66214, 66241, 66257, 66258, 66259, 66262, 66268,
       66270, 66281, 66283]

out = []


def node_name(nid):
    n = s.get(m.TaxonomyNode, nid)
    return f'{n.code}={n.name}' if n else f'?{nid}'


def tags_of(qid):
    rows = s.execute(select(m.QuestionTaxonomy, m.TaxonomyNode).join(
        m.TaxonomyNode, m.QuestionTaxonomy.node_id == m.TaxonomyNode.id
    ).where(m.QuestionTaxonomy.question_id == qid)).all()
    return [f'{n.code}({n.name})' + ('' if qt.reviewed else '*') for qt, n in rows]


def head(qid):
    q = s.get(m.Question, qid)
    if not q:
        return f'[{qid}] MISSING'
    paper = s.get(m.Paper, q.paper_id) if q.paper_id else None
    doc = s.get(m.Document, paper.document_id) if paper else None
    return f'[{qid}] {doc.title if doc else "?"} | {q.number_label} | marks={q.marks} | parent={q.parent_id} | TAGS={tags_of(qid)}'


out.append('########## NODES for ial-psychology ##########')
nodes = s.execute(select(m.TaxonomyNode).where(m.TaxonomyNode.code.like('WPS%')).order_by(m.TaxonomyNode.code)).scalars().all()
for n in nodes:
    out.append(f'{n.code} | {n.name}')

out.append('')
out.append('########## QUESTIONS ##########')
for qid in IDS:
    q = s.get(m.Question, qid)
    out.append('===== ' + head(qid))
    if not q:
        continue
    par = s.get(m.Question, q.parent_id) if q.parent_id else None
    if par:
        out.append(f'   PAR {par.number_label} [{par.id}]: {(par.stem_text or "")[:700]}')
    out.append('   OWN: ' + (q.stem_text or '')[:900])

open(r'C:/Users/weo/Desktop/api/examdata/tmp_psy007_dump.txt', 'w', encoding='utf-8').write('\n'.join(out))
print('written', len(out), 'lines')
