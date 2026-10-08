import sqlite3

con = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)


def nodes(unit):
    print(f'--- taxonomy nodes for {unit} ---')
    rows = con.execute(
        """select code, name from taxonomy_node
           where code like ? order by code""", (unit + '-%',)).fetchall()
    for c, n in rows:
        print(f'  {c} | {n}')
    print(f'  total={len(rows)}')


def doc_questions(doc_id, label):
    print(f'===== doc {doc_id} ({label}) =====')
    rows = con.execute(
        """select q.id, q.number_label, q.marks, q.kind
           from question q join paper p on q.paper_id = p.id
           where p.document_id = ? order by q.display_order""", (doc_id,)).fetchall()
    qids = [r[0] for r in rows]
    tag = {}
    for qid in qids:
        trs = con.execute(
            """select tn.code, qt.source, qt.assigned_by, qt.reviewed
               from question_taxonomy qt join taxonomy_node tn on qt.node_id = tn.id
               where qt.question_id = ?""", (qid,)).fetchall()
        tag[qid] = trs
    nrev = 0
    for qid, nl, mk, kind in rows:
        trs = tag[qid]
        rev = any(t[3] for t in trs)
        if rev:
            nrev += 1
        mark = 'REV' if rev else '   '
        codes = '; '.join(f'{c}({s},{a})' for c, s, a, _ in trs)
        print(f'  [{qid}] {mark} {nl!r} mk={mk} kind={kind} :: {codes}')
    print(f'  total={len(rows)} reviewed={nrev}')


nodes('WMA12')
nodes('WMA02')
nodes('WMA01')
nodes('WMA13')
