import sqlite3, pymupdf
con = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
con.row_factory = sqlite3.Row
def path_for(doc_id):
    r = con.execute("""SELECT dr.document_id,dr.revision_no,dr.artifact_id,a.sha256,a.storage_key
        FROM document_revision dr JOIN artifact a ON a.id=dr.artifact_id
        WHERE dr.document_id=? ORDER BY dr.revision_no DESC""",(doc_id,)).fetchall()
    return r
for did, out in ((1775,'tmp_ms_wac12_oct2022.txt'),(1732,'tmp_qp_wac02_jan2016.txt'),(1773,'tmp_qp_wac12_oct2022.txt')):
    rows = path_for(did)
    if not rows:
        print(did, "NO REVISION"); continue
    r = rows[0]
    p = '.data/artifacts/' + r['storage_key']
    try:
        doc = pymupdf.open(p)
        txt = '\n'.join(f'===== PAGE {i+1} =====\n' + pg.get_text() for i,pg in enumerate(doc))
        open(out,'w',encoding='utf-8').write(txt)
        print(did, r['storage_key'][:40], 'pages=', len(doc), 'chars=', len(txt), '->', out)
    except Exception as e:
        print(did, 'ERR', e)
