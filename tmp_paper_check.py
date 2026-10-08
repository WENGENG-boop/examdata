import sqlite3, re
c = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
c.execute('PRAGMA temp_store=MEMORY')
rows = list(c.execute("""
  select p.id, doc.year, count(q.id)
  from paper p join document doc on doc.id=p.document_id join subject s on s.id=doc.subject_id
  left join question q on q.paper_id=p.id
  where s.slug='ial-geography' and doc.paper_code='wge01-01'
  group by p.id, doc.year order by doc.year, p.id"""))
print("wge01-01 papers:", rows)
# the single wge02 ref
REF = re.compile(r'\(\d+\.\d+\.\d+\.\d+\)')
rows2 = list(c.execute("""
  select doc.paper_code, doc.year, mse.question_id, mse.answer_text, mse.guidance
  from mark_scheme_entry mse
  join question q on q.id = mse.question_id join paper p on p.id=q.paper_id join document doc on doc.id=p.document_id
  join subject s on s.id=doc.subject_id
  where s.slug='ial-geography' and doc.paper_code='wge02-01' and doc.year=2023"""))
for pc, yr, qid, ans, gui in rows2:
    blob = (ans or '') + '\n' + (gui or '')
    for m in REF.finditer(blob):
        i = m.start()
        print(pc, yr, qid, repr(blob[max(0,i-120):i+30]))
