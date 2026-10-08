import sys
sys.path.insert(0, r'C:/Users/weo/Desktop/api/examdata')
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from examdata.core import models as m
from examdata.tagging.corpus import load_points, unit_code_from_paper
from collections import Counter, defaultdict

eng = create_engine('sqlite:///C:/Users/weo/Desktop/api/examdata/.data/examdata.db')
s = Session(eng)
pts = load_points(s)
by_subj = defaultdict(set)
for p in pts:
    by_subj[(p.subject or '').strip().lower()].add(p.unit_code)

tagged = select(m.QuestionTaxonomy.question_id).where(
    m.QuestionTaxonomy.assigned_by.in_(['edexcel-bm25-v1', 'ai-review-v1'])
).distinct()
q = m.Question
stmt = select(q.id, m.Subject.slug, m.Document.paper_code, m.Paper.attrs).join(
    m.Paper, m.Paper.id == q.paper_id).join(
    m.Document, m.Document.id == m.Paper.document_id).join(
    m.Subject, m.Subject.id == m.Document.subject_id).where(q.id.in_(tagged))
stats = defaultdict(lambda: {'in': 0, 'out': 0, 'out_units': Counter(), 'no_unit': 0})
n = 0
for qid, slug, paper_code, attrs in s.execute(stmt):
    n += 1
    fresh = unit_code_from_paper(attrs, paper_code)
    d = stats[slug]
    if fresh is None:
        d['no_unit'] += 1
    elif fresh in by_subj[slug]:
        d['in'] += 1
    else:
        d['out'] += 1
        d['out_units'][fresh] += 1
print('tagged questions seen:', n)
for slug in sorted(stats):
    d = stats[slug]
    print(f"{slug}: in={d['in']} out={d['out']} no_unit={d['no_unit']} "
          f"out_units={dict(d['out_units'].most_common(8))}")
