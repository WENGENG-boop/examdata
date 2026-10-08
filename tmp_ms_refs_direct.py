import sqlite3, re
c = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
c.execute('PRAGMA temp_store=MEMORY')
REF = re.compile(r'\((\d+\.\d+\.\d+\.\d+)\)')
pids = [1575, 1579, 1593, 1599]
for pid in pids:
    meta = c.execute("select doc.year, doc.paper_code from paper p join document doc on doc.id=p.document_id where p.id=?", (pid,)).fetchone()
    print(f"\n########## paper {pid} {meta[1]} {meta[0]} ##########")
    rows = list(c.execute("""
      select mse.id, mse.question_id, mse.number_label, q.parent_id, mse.answer_text, mse.guidance
      from mark_scheme_entry mse join question q on q.id = mse.question_id
      where q.paper_id = ? order by mse.id""", (pid,)))
    for eid, qid, nl, par, ans, gui in rows:
        blob = (ans or '') + '\n' + (gui or '')
        refs = list(REF.finditer(blob))
        if not refs:
            continue
        for m in refs:
            before = blob[max(0,m.start()-110):m.start()]
            before = re.sub(r'\s+', ' ', before)
            after = re.sub(r'\s+', ' ', blob[m.end():m.end()+60])
            print(f"e={eid} q={qid} #{nl} (par={par}) ref={m.group(1)}")
            print(f"     ...{before} >>{m.group(0)}<< {after[:50]}")
