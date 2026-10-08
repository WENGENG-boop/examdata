"""Probe v3: 26471/26472 content sources; WBI13 explain-why pattern."""
import sqlite3
con = sqlite3.connect('.data/examdata.db')
cur = con.cursor()

print('== MS entries for paper 767 questions (number_path, marks, first 200) ==')
for r in cur.execute("""
    SELECT m.question_id, q.number_label, m.number_path, m.marks,
           substr(replace(coalesce(m.answer_text,''),char(10),' | '),1,200)
    FROM mark_scheme_entry m JOIN question q ON q.id=m.question_id
    JOIN question qq ON qq.id=m.question_id
    WHERE qq.paper_id=767 ORDER BY m.question_id, m.id"""):
    print(' ', r)
print()

print('== MS entries whose question_id in (26471,26472) direct ==')
for r in cur.execute("SELECT question_id, number_path, marks, substr(replace(answer_text,char(10),' | '),1,400) FROM mark_scheme_entry WHERE question_id IN (26471,26472)"):
    print(' ', r)
print()

print('== question_asset schema ==')
r = cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='question_asset'").fetchone()
print(r[0] if r else 'MISSING')
print('== asset schema ==')
r = cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='asset'").fetchone()
print(r[0] if r else 'MISSING')
print()

print('== assets for 26471/26472 ==')
try:
    for r in cur.execute("""SELECT qa.* FROM question_asset qa WHERE qa.question_id IN (26471,26472)"""):
        print(' ', r)
except Exception as e:
    print(' ERR', e)
print()

print('== children of 26471/26472 (parent_id) ==')
for r in cur.execute("SELECT id, parent_id, number_label, marks, length(coalesce(stem_text,'')) FROM question WHERE parent_id IN (26471,26472)"):
    print(' ', r)
print()

print('== artifact/document_revision for document 232 ==')
r = cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='artifact'").fetchone()
print(r[0] if r else 'MISSING')
try:
    for r in cur.execute("SELECT * FROM artifact WHERE document_id=232 LIMIT 20"):
        print(' ', r)
except Exception as e:
    print(' ERR', e)
print()

print('== WBI13 leaf Explain why (depth>=2) label counts ==')
for r in cur.execute("""
    SELECT tn.code, count(*)
    FROM question q
    JOIN question_taxonomy qt ON qt.question_id=q.id
    JOIN taxonomy_node tn ON tn.id=qt.node_id
    WHERE tn.code LIKE 'WBI13%' AND q.depth>=2 AND q.stem_text LIKE '%Explain why%'
    GROUP BY tn.code"""):
    print(' ', r)
print()

print('== WBI13 leaf Explain why samples ==')
for r in cur.execute("""
    SELECT q.id, q.number_label, substr(replace(q.stem_text,char(10),' '),1,90), tn.code
    FROM question q
    JOIN question_taxonomy qt ON qt.question_id=q.id
    JOIN taxonomy_node tn ON tn.id=qt.node_id
    WHERE tn.code LIKE 'WBI13%' AND q.depth>=2 AND q.stem_text LIKE '%Explain why%'
    ORDER BY q.id"""):
    print(' ', r)
print()

print('== WBI13 leaf Suggest why samples ==')
for r in cur.execute("""
    SELECT q.id, q.number_label, substr(replace(q.stem_text,char(10),' '),1,90), tn.code
    FROM question q
    JOIN question_taxonomy qt ON qt.question_id=q.id
    JOIN taxonomy_node tn ON tn.id=qt.node_id
    WHERE tn.code LIKE 'WBI13%' AND q.depth>=2 AND q.stem_text LIKE '%Suggest why%'
    ORDER BY q.id"""):
    print(' ', r)
