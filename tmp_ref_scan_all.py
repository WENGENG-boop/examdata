import sqlite3, re
c = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
c.execute('PRAGMA temp_store=MEMORY')
REF = re.compile(r'\(\d+\.\d+\.\d+\.\d+\)')
rows = list(c.execute("""
  select doc.paper_code, doc.year, count(*), sum(case when mse.answer_text like '%(' || '1.' || '%' then 1 else 0 end)
  from mark_scheme_entry mse
  join question q on q.id = mse.question_id
  join paper p on p.id = q.paper_id
  join document doc on doc.id = p.document_id
  join subject s on s.id = doc.subject_id
  where s.slug='ial-geography'
  group by doc.paper_code, doc.year order by doc.paper_code, doc.year"""))
print("paper_code | year | entries | entries_with_(1.")
for pc, yr, n, m in rows:
    print(f"{pc} {yr} entries={n} with_1x_ref={m}")
print()
# count actual ref matches per paper
rows2 = list(c.execute("""
  select doc.paper_code, doc.year, mse.answer_text, mse.guidance
  from mark_scheme_entry mse
  join question q on q.id = mse.question_id
  join paper p on p.id = q.paper_id
  join document doc on doc.id = p.document_id
  join subject s on s.id = doc.subject_id
  where s.slug='ial-geography'"""))
from collections import Counter
cnt = Counter()
for pc, yr, ans, gui in rows2:
    blob = (ans or '') + '\n' + (gui or '')
    for m in REF.finditer(blob):
        cnt[(pc, yr)] += 1
for k in sorted(cnt):
    print(k, cnt[k])
