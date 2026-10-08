import sqlite3, re
c = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
c.execute('PRAGMA temp_store=MEMORY')
REF = re.compile(r'\(\d+\.\d+\.\d+\.\d+\)')
rows = list(c.execute("""
  select p.id, doc.paper_code, doc.year, doc.session, mse.answer_text, mse.guidance
  from mark_scheme_entry mse
  join question q on q.id = mse.question_id
  join paper p on p.id = q.paper_id
  join document doc on doc.id = p.document_id
  join subject s on s.id = doc.subject_id
  where s.slug='ial-geography'"""))
from collections import Counter
cnt = Counter()
for pid, pc, yr, sess, ans, gui in rows:
    blob = (ans or '') + '\n' + (gui or '')
    n = len(REF.findall(blob))
    if n: cnt[(pid, pc, yr, sess)] += n
for k in sorted(cnt):
    print(k, cnt[k])
