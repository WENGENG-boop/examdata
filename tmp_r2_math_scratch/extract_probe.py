import sqlite3, re, os, sys
import fitz

pack = sys.argv[1]
outdir = sys.argv[2]
os.makedirs(outdir, exist_ok=True)

con = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
con.execute('pragma temp_store = memory')
cur = con.cursor()


def skey(doc_id):
    return cur.execute(
        "select a.storage_key from document_revision dr join artifact a on a.id=dr.artifact_id "
        "where dr.document_id=? and dr.id=(select current_revision_id from document where id=?)",
        (doc_id, doc_id)).fetchone()[0]


def extract(doc_id, outname):
    path = '.data/artifacts/' + skey(doc_id)
    doc = fitz.open(path)
    lines = []
    for pno in range(len(doc)):
        page = doc[pno]
        words = page.get_text('words')
        ws = sorted(words, key=lambda w: (round(w[1] / 3), w[0]))
        buf = []
        lasty = None
        for w in ws:
            y = round(w[1] / 3)
            if lasty is not None and y != lasty:
                lines.append('[p%d] ' % (pno + 1) + ' '.join(buf))
                buf = []
            buf.append(w[4])
            lasty = y
        if buf:
            lines.append('[p%d] ' % (pno + 1) + ' '.join(buf))
    open(outname, 'w', encoding='utf-8').write('\n'.join(lines))
    return len(lines)


text = open(pack, encoding='utf-8').read()
qids = [int(m.group(2)) for m in re.finditer(r'^\[(\d+)\]\s+(\d+)\s', text, flags=re.M)]

docs = {}
for q in qids:
    r = cur.execute(
        "select d.id, d.year, d.paper_code, d.title from question q "
        "join paper p on p.id=q.paper_id join document d on d.id=p.document_id where q.id=?",
        (q,)).fetchone()
    docs.setdefault(r[0], r)

sessions = []
for did, (did2, year, pc, title) in sorted(docs.items()):
    m = re.search(r'-\s*([A-Za-z]+)\s+(\d{4})', title)
    sess = (m.group(1).lower() + m.group(2)) if m else ('%d_%s' % (year, pc))
    rsuf = 'r' if 'Unit 2R' in title else ''
    sessions.append((did, year, pc, sess + rsuf, title))

for did, year, pc, sess, title in sessions:
    n = extract(did, os.path.join(outdir, 'qp_%s.txt' % sess))
    print('QP', did, sess, title, '->', n, 'lines')
    msrows = cur.execute(
        "select id, title from document where year=? and paper_code=? and doc_type='mark_scheme'",
        (year, pc)).fetchall()
    for mid, mtitle in msrows:
        m2 = re.search(r'([A-Za-z]+)\s+(\d{4})', mtitle)
        msess = (m2.group(1).lower() + m2.group(2)) if m2 else ''
        rsuf2 = 'r' if 'Unit 2R' in mtitle else ''
        if msess + rsuf2 == sess or (msess == sess.rstrip('r') and rsuf2 == sess[-1] == 'r'):
            n2 = extract(mid, os.path.join(outdir, 'ms_%s.txt' % sess))
            print('  MS', mid, mtitle, '->', n2, 'lines')
