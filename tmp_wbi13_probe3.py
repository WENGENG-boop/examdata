"""Probe v4: paper 767 tree structure + parse runs."""
import sqlite3
con = sqlite3.connect('.data/examdata.db')
cur = con.cursor()

print('== paper 767 full tree ==')
for r in cur.execute("""
    SELECT id, parent_id, number_label, marks, depth, display_order,
           length(coalesce(stem_text,'')) as len,
           substr(replace(coalesce(stem_text,''),char(10),' '),1,110)
    FROM question WHERE paper_id=767 ORDER BY display_order"""):
    print(' ', r)
print()

print('== paper 767 parse runs ==')
for r in cur.execute("SELECT * FROM parse_run WHERE id IN (SELECT DISTINCT parse_run_id FROM question WHERE paper_id=767)"):
    print(' ', r)
print()

print('== official_answer for paper 767 ==')
try:
    r = cur.execute("SELECT sql FROM sqlite_master WHERE name='official_answer'").fetchone()
    print(r[0])
    for r2 in cur.execute("""SELECT oa.* FROM official_answer oa JOIN question q ON q.id=oa.question_id WHERE q.paper_id=767 LIMIT 10"""):
        print(' ', r2)
except Exception as e:
    print(' ERR', e)
print()

print('== document 232 revisions ==')
for r in cur.execute("SELECT * FROM document_revision WHERE document_id=232"):
    print(' ', r)
print()

print('== document 232 title/series ==')
for r in cur.execute("""SELECT d.id, d.identity_key, d.title, d.year, d.paper_code, es.name
    FROM document d LEFT JOIN exam_series es ON es.id=d.series_id WHERE d.id=232"""):
    print(' ', r)
print()

print('== check duplicate-ish nodes: questions on paper 767 mentioning beetroot ==')
for r in cur.execute("""SELECT id, number_label, substr(replace(coalesce(stem_text,''),char(10),' '),1,100)
    FROM question WHERE paper_id=767 AND stem_text LIKE '%beetroot%'"""):
    print(' ', r)
