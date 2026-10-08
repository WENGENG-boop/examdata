"""Probe special docs (round 2, corrected paper/doc ids)."""
import sqlite3

con = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
cur = con.cursor()


def paper_info(pid):
    row = cur.execute(
        "select p.id, p.document_id, d.title, d.year, d.paper_code, p.attrs "
        "from paper p join document d on d.id=p.document_id where p.id=?", (pid,)).fetchone()
    return row


def doc_stat(did):
    n_q = cur.execute(
        "select count(*) from question q join paper p on p.id=q.paper_id "
        "where p.document_id=?", (did,)).fetchone()[0]
    n_t = cur.execute(
        "select count(distinct q.id) from question q join paper p on p.id=q.paper_id "
        "join question_taxonomy qt on qt.question_id=q.id where p.document_id=?", (did,)).fetchone()[0]
    rows = cur.execute(
        "select tn.code, count(*) from question q "
        "join paper p on p.id=q.paper_id "
        "join question_taxonomy qt on qt.question_id=q.id "
        "join taxonomy_node tn on tn.id=qt.node_id "
        "where p.document_id=? group by tn.code order by 2 desc", (did,)).fetchall()
    return n_q, n_t, rows


for pid in [1407, 1626, 1952, 1940, 1953, 1955, 1956, 2083, 2084, 2039, 2043, 2060]:
    row = paper_info(pid)
    if row is None:
        print(f'paper {pid}: MISSING')
        continue
    pid_, did, title, y, pcode, attrs = row
    n_q, n_t, rows = doc_stat(did)
    print(f'paper {pid_} doc={did} y={y} pcode={pcode!r} attrs={str(attrs)[:60]!r}')
    print(f'    doc q={n_q} tagged={n_t} {title!r}')
    print(f'    nodes={[(c, n) for c, n in rows][:10]}')

print()
print('=== all papers of doc containing paper 1407 ===')
did = paper_info(1407)[1]
for row in cur.execute(
        "select p.id, p.paper_no, p.attrs from paper p where p.document_id=?", (did,)):
    print('  paper:', row[0], row[1], str(row[2])[:100])

print()
print('=== accounting QP docs all ===')
for did, title, y in cur.execute(
        "select d.id, d.title, d.year from document d "
        "where d.subject_id=(select id from subject where slug='ial-accounting') "
        "and d.doc_type='question_paper' order by d.year, d.id"):
    n_q, n_t, rows = doc_stat(did)
    print(f'  doc {did} y={y} q={n_q} t={n_t} {title!r} units={[(c[:8], n) for c, n in rows][:8]}')

print()
print('=== german Unit 1 QP docs all ===')
for did, title, y in cur.execute(
        "select d.id, d.title, d.year from document d "
        "where d.subject_id=(select id from subject where slug='ial-german') "
        "and d.doc_type='question_paper' and d.title like '%Unit 1%' order by d.year, d.id"):
    n_q, n_t, rows = doc_stat(did)
    print(f'  doc {did} y={y} q={n_q} t={n_t} {title!r} units={[(c, n) for c, n in rows][:8]}')

print()
print('=== FP1 doc 3270: tagged qids + their taxonomy rows ===')
for qid, num, tn_code, ab in cur.execute(
        "select q.id, q.number_label, tn.code, qt.assigned_by from question q "
        "join paper p on p.id=q.paper_id "
        "join question_taxonomy qt on qt.question_id=q.id "
        "join taxonomy_node tn on tn.id=qt.node_id "
        "where p.document_id=3270 order by q.id"):
    print(f'  qid={qid} {num!r} -> {tn_code} by {ab}')
qids = [r[0] for r in cur.execute(
    "select q.id from question q join paper p on p.id=q.paper_id where p.document_id=3270 order by q.id")]
print('  all qids:', qids)
