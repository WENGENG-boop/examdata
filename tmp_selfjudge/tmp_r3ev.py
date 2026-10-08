"""Dump evidence for a batch of qids: question row, MS entries, taxonomy, siblings."""
import sqlite3
import sys

con = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
con.row_factory = sqlite3.Row
cur = con.cursor()

for qid in sys.argv[1:]:
    q = cur.execute(
        'select id, paper_id, number_label, marks, stem_text, display_order from question where id=?',
        (qid,)).fetchone()
    if not q:
        print(f'=== qid {qid}: NOT FOUND ===')
        continue
    print('=' * 100)
    print(f'=== qid {qid} paper={q["paper_id"]} label={q["number_label"]!r} marks={q["marks"]} order={q["display_order"]}')
    p = cur.execute('select id, document_id, paper_no from paper where id=?', (q['paper_id'],)).fetchone()
    if p:
        print(f'    paper: id={p["id"]} doc={p["document_id"]} paper_no={p["paper_no"]}')
    print('--- STEM ---')
    print((q['stem_text'] or '')[:2500])
    print('--- MS ---')
    ms = cur.execute(
        'select number_label, answer_text, guidance from mark_scheme_entry where question_id=? order by id',
        (qid,)).fetchall()
    if not ms:
        print('   (no MS rows)')
    for r in ms:
        print(f'   [{r["number_label"]}] {(r["answer_text"] or "")[:900]}')
        if r['guidance']:
            print(f'        GUID: {r["guidance"][:400]}')
    print('--- TAXONOMY (this q) ---')
    tx = cur.execute(
        'select t.node_id, n.code, n.name, t.source, t.confidence, t.assigned_by, t.reviewed '
        'from question_taxonomy t left join taxonomy_node n on n.id=t.node_id where t.question_id=?',
        (qid,)).fetchall()
    if not tx:
        print('   (no taxonomy rows)')
    for r in tx:
        print(f'   node={r["node_id"]} code={r["code"]} name={(r["name"] or "")[:80]} src={r["source"]} conf={r["confidence"]} by={r["assigned_by"]} rev={r["reviewed"]}')
    print('--- SIBLINGS (same paper) ---')
    sib = cur.execute(
        'select q.id, q.number_label, q.marks, substr(q.stem_text,1,110) as s, '
        '  (select group_concat(n.code) from question_taxonomy t join taxonomy_node n on n.id=t.node_id '
        '   where t.question_id=q.id) as codes '
        'from question q where q.paper_id=? order by q.display_order, q.id',
        (q['paper_id'],)).fetchall()
    for r in sib:
        mark = '>>' if r['id'] == int(qid) else '  '
        print(f' {mark} {r["id"]} {r["number_label"]!r} {r["marks"]}mk [{r["codes"] or "-"}] {(r["s"] or "")[:100]!r}')
con.close()
