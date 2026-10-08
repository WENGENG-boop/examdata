"""Read-only context dump for r3 re-check qids.

usage: python r3_ctx.py <qid> [qid...]
Prints: full stem, parent chain, siblings with taxonomy labels, MS rows.
"""
import sqlite3
import sys

db = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)


def labels_for(qid):
    rows = db.execute(
        '''select tn.code, tn.name, qt.source, qt.confidence, qt.assigned_by, qt.reviewed
           from question_taxonomy qt join taxonomy_node tn on tn.id = qt.node_id
           where qt.question_id=?''', (qid,)).fetchall()
    return rows


def dump(qid):
    r = db.execute(
        'select id, paper_id, parent_id, number_label, number_path, depth, kind, marks, stem_text from question where id=?',
        (qid,)).fetchone()
    if not r:
        print(f'!! question {qid} not found')
        return
    qid_, paper, parent, label, path, depth, kind, marks, stem = r
    print('=' * 70)
    print(f'QID {qid_} paper={paper} label={label!r} path={path!r} depth={depth} kind={kind} marks={marks}')
    print('CURRENT LABELS:', labels_for(qid) or 'NONE')
    print('--- stem ---')
    print(stem)
    # parent chain
    p = parent
    chain = []
    while p:
        pr = db.execute('select id, parent_id, number_label, marks, substr(stem_text,1,1200) from question where id=?', (p,)).fetchone()
        if not pr:
            break
        chain.append(pr)
        p = pr[1]
    if chain:
        print('--- parent chain ---')
        for pr in chain:
            print(f'  parent {pr[0]} label={pr[2]!r} marks={pr[3]}')
            print('   ', (pr[4] or '').replace('\n', ' | ')[:1100])
    # siblings under same parent
    sibrows = db.execute(
        'select id, number_label, marks, substr(stem_text,1,200) from question where paper_id=? and ifnull(parent_id,-1)=ifnull(?,-1) and id!=? order by display_order',
        (paper, parent, qid)).fetchall()
    if sibrows:
        print('--- siblings (same parent) ---')
        for s in sibrows:
            print(f'  sib {s[0]} label={s[1]!r} marks={s[2]} labels={labels_for(s[0])}')
            print('   ', (s[3] or '').replace('\n', ' | ')[:180])
    # all questions on paper with labels
    allrows = db.execute(
        '''select q.id, q.number_label, q.marks,
                  (select group_concat(tn.code, ',') from question_taxonomy qt join taxonomy_node tn on tn.id=qt.node_id where qt.question_id=q.id)
           from question q where q.paper_id=? order by q.display_order''', (paper,)).fetchall()
    print('--- paper questions w/ labels ---')
    for a in allrows:
        print(f'  {a[0]} {a[1]!r} {a[2]}mk -> {a[3]}')
    # MS rows
    ms = db.execute(
        'select id, number_label, marks, answer_text, guidance from mark_scheme_entry where question_id=?', (qid,)).fetchall()
    print(f'--- mark scheme rows: {len(ms)} ---')
    for m in ms:
        print(f'  ms#{m[0]} label={m[1]!r} marks={m[2]}')
        print('   ans:', (m[3] or '')[:2000])
        if m[4]:
            print('   guid:', (m[4] or '')[:900])


for q in sys.argv[1:]:
    dump(int(q))
