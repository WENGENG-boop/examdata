import sqlite3
con = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
con.row_factory = sqlite3.Row
# MS document 3424 -> mark_scheme row
ms = con.execute("SELECT id FROM mark_scheme WHERE document_id=3424").fetchone()
print("mark_scheme row for doc 3424:", ms['id'] if ms else None)
if ms:
    msid = ms['id']
    rows = con.execute("""SELECT id, question_id, number_label, number_path, marks,
        substr(answer_text,1,400) a, substr(guidance,1,300) g
        FROM mark_scheme_entry WHERE mark_scheme_id=? ORDER BY id""", (msid,)).fetchall()
    print(f"entries: {len(rows)}")
    for r in rows:
        qid = r['question_id']
        # only Q8-related (number_path starting 8) or question ids 67714-67717
        if (r['number_path'] or '').startswith('8') or (qid in (67714,67715,67716,67717)):
            print(f"--- [{r['id']}] qid={qid} num={r['number_label']} path={r['number_path']} marks={r['marks']}")
            print("   ANS:", (r['a'] or '')[:400].replace(chr(10),' | '))
            if r['g']: print("   GD:", (r['g'] or '')[:300].replace(chr(10),' | '))
    # also print all entries summary
    print()
    print("=== all entries (num, marks, ans head) ===")
    for r in rows:
        print(f"  [{r['id']}] qid={r['question_id']} num={r['number_label']} path={r['number_path']} m={r['marks']} | {(r['a'] or '')[:80].replace(chr(10),' / ')}")
con.close()
