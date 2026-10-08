"""Dump full stems for a list of qids plus MS, and paper-level raw text search."""
import sqlite3
import sys

con = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
con.row_factory = sqlite3.Row
cur = con.cursor()

qids = [a for a in sys.argv[1:] if a.isdigit()]
for qid in qids:
    q = cur.execute('select id, paper_id, number_label, marks, stem_text, display_order from question where id=?', (qid,)).fetchone()
    if not q:
        print(f'=== {qid} NOT FOUND')
        continue
    print('=' * 90)
    print(f'=== {qid} paper={q["paper_id"]} label={q["number_label"]!r} marks={q["marks"]} order={q["display_order"]}')
    print('STEM:')
    print(q['stem_text'])
    ms = cur.execute('select number_label, answer_text, guidance from mark_scheme_entry where question_id=? order by id', (qid,)).fetchall()
    print('MS rows:', len(ms))
    for r in ms:
        print(f'  [{r["number_label"]}] {r["answer_text"]}')
        if r['guidance']:
            print(f'      GUID: {r["guidance"]}')
con.close()
