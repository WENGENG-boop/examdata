import sqlite3, json
con = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
cur = con.cursor()
# spec documents for subject 16 and 24
for sid in (16, 24):
    print('=== subject', sid)
    for r in cur.execute("select id,doc_type,title,year,attrs from document where subject_id=? and doc_type like '%spec%'", (sid,)).fetchall():
        print(r[0], r[1], r[2], r[3])
        a = json.loads(r[4] or '{}')
        print('   attrs:', json.dumps(a, ensure_ascii=False)[:300])
print()
# taxonomy node source for various codes
for code in ['WMA01-1', 'WFM02-1', 'WME01-1', 'WST01-1', 'WMA11-1', 'WDM11-1']:
    r = cur.execute("select id,code,node_type,source,attrs from taxonomy_node where code=?", (code,)).fetchone()
    if r:
        a = json.loads(r[4] or '{}')
        print(r[0], r[1], r[2], 'source=', r[3], 'subj=', a.get('subject'), 'page=', a.get('page'))
