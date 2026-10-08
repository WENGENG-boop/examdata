"""Probe special docs for the untagged Jev pass (read-only)."""
import sqlite3

con = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
cur = con.cursor()


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


print('=== docs whose title contains YLA1 (question papers) ===')
for did, title, y, slug in cur.execute(
        "select d.id, d.title, d.year, s.slug from document d join subject s on s.id=d.subject_id "
        "where d.title like '%YLA1%' and d.doc_type='question_paper' order by d.id"):
    n_q, n_t, rows = doc_stat(did)
    print(f'  doc {did} y={y} {slug} q={n_q} tagged={n_t} {title!r}')
    if rows:
        print('      nodes:', rows)

print()
print('=== docs with FP1 / 6667A / 6663A / 6664A ===')
for pat in ['%FP1%', '%6667A%', '%6663A%', '%6664A%']:
    for did, title, y, slug in cur.execute(
            "select d.id, d.title, d.year, s.slug from document d join subject s on s.id=d.subject_id "
            "where d.title like ? order by d.id", (pat,)):
        n_q, n_t, rows = doc_stat(did)
        print(f'  [{pat}] doc {did} y={y} {slug} q={n_q} tagged={n_t} {title!r}')
        if rows:
            print('      nodes:', rows)

print()
print('=== accounting QP docs 2015-2017 (year, title, tagged units) ===')
for did, title, y, slug in cur.execute(
        "select d.id, d.title, d.year, s.slug from document d join subject s on s.id=d.subject_id "
        "where s.slug='ial-accounting' and d.doc_type='question_paper' and d.year between 2015 and 2017 "
        "order by d.year, d.id"):
    n_q, n_t, rows = doc_stat(did)
    print(f'  doc {did} y={y} q={n_q} tagged={n_t} {title!r}')
    if rows:
        print('      nodes:', rows)

print()
print('=== german QP docs with Unit 1 in title ===')
for did, title, y, slug in cur.execute(
        "select d.id, d.title, d.year, s.slug from document d join subject s on s.id=d.subject_id "
        "where s.slug='ial-german' and d.doc_type='question_paper' and d.title like '%Unit 1%' "
        "order by d.year, d.id"):
    n_q, n_t, rows = doc_stat(did)
    print(f'  doc {did} y={y} q={n_q} tagged={n_t} {title!r}')
    if rows:
        print('      nodes:', rows)

print()
print('=== maths legacy question-paper docs (June 2014) sample ===')
for did, title, y, slug in cur.execute(
        "select d.id, d.title, d.year, s.slug from document d join subject s on s.id=d.subject_id "
        "where s.slug='ial-maths' and d.title like '%June 2014%' order by d.id"):
    n_q, n_t, rows = doc_stat(did)
    print(f'  doc {did} y={y} q={n_q} tagged={n_t} {title!r}')
    if rows:
        print('      nodes:', rows)

print()
print('=== law QP docs sample (all) ===')
for did, title, y, slug in cur.execute(
        "select d.id, d.title, d.year, s.slug from document d join subject s on s.id=d.subject_id "
        "where s.slug='ial-law' and d.doc_type='question_paper' order by d.year, d.id"):
    n_q, n_t, rows = doc_stat(did)
    if rows or n_t != n_q:
        print(f'  doc {did} y={y} q={n_q} tagged={n_t} {title!r}')
        if rows:
            print('      nodes:', rows)
