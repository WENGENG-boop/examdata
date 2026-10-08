"""Dump full detail for geography questions whose MS entries contain refs (x.y.z.w).

Usage: python tmp_ref_detail.py > tmp_ref_detail.txt
"""
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
con = sqlite3.connect(f"file:{ROOT / '.data' / 'examdata.db'}?mode=ro", uri=True)
c = con.cursor()

pat = re.compile(r'\((\d+\.\d+\.\d+\.\d+)\)')

rows = c.execute("""
select mse.question_id, mse.answer_text, mse.guidance
from mark_scheme_entry mse
join question q on q.id = mse.question_id
join paper p on p.id = q.paper_id
join document d on d.id = p.document_id
join subject s on s.id = d.subject_id
where s.slug = 'ial-geography' and mse.question_id is not null
order by mse.question_id
""").fetchall()
qids = sorted({r[0] for r in rows if pat.search((r[1] or '') + ' ' + (r[2] or ''))})

for qid in qids:
    q = c.execute("select id, paper_id, parent_id, number_label, marks, stem_text from question where id=?", (qid,)).fetchone()
    pid = q[1]
    d = c.execute("select doc.year, doc.paper_code from paper p join document doc on doc.id=p.document_id where p.id=?", (pid,)).fetchone()
    labels = [r[0] for r in c.execute(
        "select tn.code from question_taxonomy qt join taxonomy_node tn on tn.id=qt.node_id "
        "where qt.question_id=? order by tn.code", (qid,))]
    print(f"##### {qid} #{q[3]} m={q[4]} paper={d[1]} {d[0]} labels={labels}")
    print("STEM:", re.sub(r'\s+', ' ', q[5] or '')[:260])
    ms = c.execute("select number_label, answer_text, guidance from mark_scheme_entry where question_id=? order by id", (qid,)).fetchall()
    for n, a, g in ms:
        a2 = re.sub(r'\s+', ' ', a or '')
        print(f"  MS[{n}]:", a2[:900])
        refs = pat.findall((a or '') + ' ' + (g or ''))
        print(f"    refs: {sorted(set(refs))}")
    # siblings
    root = q[2] if q[2] else qid
    fam = c.execute("select id, number_label, coalesce(marks,-1), substr(coalesce(stem_text,''),1,110) from question where id=? or parent_id=? order by id", (root, root)).fetchall()
    if len(fam) > 1:
        print("  family:")
        for fid, fnum, fmk, fstem in fam:
            print(f"    {fid} #{fnum} {fmk}mk :: {re.sub(chr(92)+'s+',' ', fstem)}")
    print()
