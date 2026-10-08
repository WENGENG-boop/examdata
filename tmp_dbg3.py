import sqlite3
from pathlib import Path
ROOT = Path(__file__).resolve().parent
con = sqlite3.connect(f"file:{ROOT / '.data' / 'examdata.db'}?mode=ro", uri=True)
c = con.cursor()
c.execute('PRAGMA temp_store=MEMORY')
qs = c.execute("""
select q.id, q.paper_id, q.number_label, q.stem_text
from question q
join paper p on p.id = q.paper_id
join document d on d.id = p.document_id
join subject s on s.id = d.subject_id
where s.slug = 'ial-geography'
order by q.paper_id, q.id
""").fetchall()
print('rows:', len(qs))
