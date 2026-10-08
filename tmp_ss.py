"""One-off DB introspection for the full Jev pass planning."""
import sqlite3

con = sqlite3.connect('.data/examdata.db')
cur = con.cursor()

print('=== tables ===')
for (name,) in cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
    print(name)

print('=== schema (subject/taxonomy related) ===')
for (name, sql) in cur.execute(
    "SELECT name, sql FROM sqlite_master WHERE type='table' ORDER BY name"
):
    if any(k in name.lower() for k in ('subject', 'taxonomy', 'question', 'paper', 'document')):
        print('---', name)
        print(sql)

print('=== subjects ===')
cols = [r[1] for r in cur.execute('PRAGMA table_info(subject)')]
print('cols:', cols)
sel = ', '.join(c for c in ('id', 'code', 'slug', 'title', 'name') if c in cols)
for row in cur.execute(f'SELECT {sel} FROM subject ORDER BY id'):
    print(row)

print('=== taxonomy stats by source/reviewed ===')
for row in cur.execute(
    'SELECT assigned_by, reviewed, COUNT(*) FROM question_taxonomy GROUP BY 1, 2 ORDER BY 1, 2'
):
    print(row)

print('=== taxonomy total ===')
print(cur.execute('SELECT COUNT(*) FROM question_taxonomy').fetchone())

print('=== extra-subject question->subject mapping sample ===')
try:
    for row in cur.execute(
        'SELECT s.slug, COUNT(DISTINCT q.id) FROM question q '
        'JOIN paper p ON p.id = q.paper_id '
        'JOIN document d ON d.id = p.document_id '
        'JOIN subject s ON s.id = d.subject_id '
        'GROUP BY s.slug ORDER BY 2 DESC'
    ):
        print(row)
except Exception as exc:
    print('ERR', exc)
