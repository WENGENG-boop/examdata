import sqlite3, json, re

con = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
con.row_factory = sqlite3.Row
cur = con.cursor()


def clean(s, maxlen=8000):
    if not s:
        return ''
    s = re.sub(r'\.{3,}', ' … ', s)
    s = re.sub(r'\s+', ' ', s)
    return s[:maxlen]


def qdump(qid, maxlen=8000):
    print(f'\n########## QID {qid} ##########')
    for r in cur.execute('select id, paper_id, parent_id, number_label, number_path, display_order, marks, kind, stem_text from question where id=?', (qid,)):
        d = dict(r)
        d['stem_text'] = clean(d['stem_text'], maxlen)
        print(json.dumps(d, ensure_ascii=False, indent=1))
    for r in cur.execute('''select qt.node_id, qt.source, qt.confidence, tn.code, tn.name from question_taxonomy qt
                            join taxonomy_node tn on tn.id=qt.node_id where qt.question_id=?''', (qid,)):
        print('  TAX', json.dumps(dict(r), ensure_ascii=False))


def paperdump(qid, stemlen=200):
    row = cur.execute('select paper_id from question where id=?', (qid,)).fetchone()
    if not row:
        print(f'no paper for {qid}')
        return
    pid = row['paper_id']
    print(f'\n===== PAPER {pid} (from qid {qid}) =====')
    for r in cur.execute('''select q.id, q.number_label, q.marks, q.display_order, q.kind,
              substr(q.stem_text,1,?) as stem, group_concat(tn.code, '|') as codes
        from question q
        left join question_taxonomy qt on qt.question_id=q.id
        left join taxonomy_node tn on tn.id=qt.node_id
        where q.paper_id=? group by q.id order by q.display_order, q.id''', (stemlen, pid)):
        d = dict(r)
        d['stem'] = clean(d['stem'], stemlen)
        print(json.dumps(d, ensure_ascii=False))


qdump(56196)
qdump(56466, 1200)
paperdump(56279, 160)
paperdump(53271, 160)
paperdump(53549, 160)

print('\n===== ADR-tagged YLA1-01 questions =====')
for r in cur.execute('''select q.id, substr(q.stem_text,1,300) as stem, tn.code from question q
    join question_taxonomy qt on qt.question_id=q.id
    join taxonomy_node tn on tn.id=qt.node_id
    where tn.code in ('YLA1-01-1.2.15','YLA1-01-1.2.16','YLA1-01-1.2.17','YLA1-01-1.2.18') order by tn.code, q.id'''):
    d = dict(r)
    d['stem'] = clean(d['stem'], 300)
    print(json.dumps(d, ensure_ascii=False))

print('\n===== WHI02 partition/Jinnah questions =====')
for r in cur.execute('''select q.id, substr(q.stem_text,1,300) as stem, tn.code from question q
    join question_taxonomy qt on qt.question_id=q.id
    join taxonomy_node tn on tn.id=qt.node_id
    where (q.stem_text like '%partition%' or q.stem_text like '%Jinnah%') and tn.code like 'WHI02%' order by tn.code, q.id'''):
    d = dict(r)
    d['stem'] = clean(d['stem'], 300)
    print(json.dumps(d, ensure_ascii=False))

con.close()
