"""Probe WBI13 label conventions and missing question content (v2)."""
import sqlite3
con = sqlite3.connect('.data/examdata.db')
cur = con.cursor()

print('== schema document ==')
r = cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='document'").fetchone()
print(r[0] if r else 'MISSING')
print()

print('== papers of interest ==')
for r in cur.execute("""
    SELECT p.id, p.paper_no, p.marks_total, p.question_count, p.page_count, d.id, d.title
    FROM paper p JOIN document d ON d.id=p.document_id
    WHERE p.id IN (715,767,713,720,769) ORDER BY p.id"""):
    print(' ', r)
print()

print('== paper 767 all questions (id, num, marks, len, stem300) ==')
for r in cur.execute("""
    SELECT q.id, q.number_label, q.marks, length(coalesce(q.stem_text,'')),
           substr(replace(coalesce(q.stem_text,''),char(10),' '),1,300)
    FROM question q WHERE q.paper_id=767 ORDER BY q.display_order"""):
    print(' ', r[0], '|', r[1], '|', r[2], 'mk | len', r[3], '|', r[4])
print()

print('== paper 715 questions + label + source ==')
for r in cur.execute("""
    SELECT q.id, q.number_label, q.marks, tn.code, qt.source, qt.confidence, qt.reviewed
    FROM question q
    LEFT JOIN question_taxonomy qt ON qt.question_id=q.id
    LEFT JOIN taxonomy_node tn ON tn.id=qt.node_id
    WHERE q.paper_id=715 ORDER BY q.display_order"""):
    print(' ', r)
print()

print('== WBI13-wide: stems LIKE plot a suitable graph ==')
for r in cur.execute("""
    SELECT q.id, q.number_label, tn.code, qt.source
    FROM question q
    LEFT JOIN question_taxonomy qt ON qt.question_id=q.id
    LEFT JOIN taxonomy_node tn ON tn.id=qt.node_id
    WHERE q.stem_text LIKE '%plot a suitable graph%' AND tn.code LIKE 'WBI13%'
    ORDER BY q.id"""):
    print(' ', r)
print()

print('== WBI13-wide: stems LIKE draw a suitable table ==')
for r in cur.execute("""
    SELECT q.id, q.number_label, tn.code, qt.source
    FROM question q
    LEFT JOIN question_taxonomy qt ON qt.question_id=q.id
    LEFT JOIN taxonomy_node tn ON tn.id=qt.node_id
    WHERE q.stem_text LIKE '%draw a suitable table%' AND tn.code LIKE 'WBI13%'
    ORDER BY q.id"""):
    print(' ', r)
print()

print('== WBI13-wide: describe a procedure / method ==')
for r in cur.execute("""
    SELECT q.id, q.number_label, tn.code, qt.source
    FROM question q
    LEFT JOIN question_taxonomy qt ON qt.question_id=q.id
    LEFT JOIN taxonomy_node tn ON tn.id=qt.node_id
    WHERE (q.stem_text LIKE '%describe a procedure%' OR q.stem_text LIKE '%describe a method%' OR q.stem_text LIKE '%describe a suitable%')
      AND tn.code LIKE 'WBI13%'
    ORDER BY q.id"""):
    print(' ', r)
print()

print('== WBI13-wide: explain why ... used/incubated (condition questions) ==')
for r in cur.execute("""
    SELECT q.id, q.number_label, substr(replace(q.stem_text,char(10),' '),1,80), tn.code, qt.source
    FROM question q
    LEFT JOIN question_taxonomy qt ON qt.question_id=q.id
    LEFT JOIN taxonomy_node tn ON tn.id=qt.node_id
    WHERE q.stem_text LIKE '%incubated%' AND tn.code LIKE 'WBI13%'
    ORDER BY q.id"""):
    print(' ', r)
print()

print('== WBI13 label distribution by source ==')
for r in cur.execute("""
    SELECT tn.code, qt.source, count(*)
    FROM question q
    JOIN question_taxonomy qt ON qt.question_id=q.id
    JOIN taxonomy_node tn ON tn.id=qt.node_id
    WHERE tn.code LIKE 'WBI13%'
    GROUP BY tn.code, qt.source ORDER BY tn.code, qt.source"""):
    print(' ', r)
