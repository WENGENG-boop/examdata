import sqlite3, json
con = sqlite3.connect('file:.data/examdata.db?mode=ro', uri=True)
cur = con.cursor()

def labels(qid):
    rows = cur.execute("""select t.code, qt.source, qt.confidence from question_taxonomy qt
        join taxonomy_node t on t.id=qt.node_id where qt.question_id=?""", (qid,)).fetchall()
    return [(r[0], r[1], round(r[2],2) if r[2] is not None else None) for r in rows]

def stem(qid, n=110):
    r = cur.execute("select stem_text from question where id=?", (qid,)).fetchone()
    return (r[0] or '').replace('\n',' ')[:n] if r else None

def parent(qid):
    r = cur.execute("select parent_id from question where id=?", (qid,)).fetchone()
    return r[0] if r else None

qids = [56934,56941,56943,56944,56953,56964,56965,57764,57768,57777,57795,57796,57801,57802,58336,58337,58339,58357,58370,58572,58578,58579,58583,58590,58592,58885,58922,58937,58941,58942,58943,58953,
        59375,59379,59381,59384,59393,59394,59396,59399,59404,59407,59409,59410,59834,59845,59849,59857,60363,60379,60394,60399,60685,60689,60716,60725,60727,60897,60898,60899,60907,60921,60925,60982,60986,60990,60991,60993,61027]

print("== target qids: current labels")
for q in qids:
    print(q, labels(q), '|', stem(q, 70))

print()
print("== parent labels + sibling labels")
seen_p = set()
for q in qids:
    p = parent(q)
    if p and p not in seen_p:
        seen_p.add(p)
        sibs = cur.execute("select id, number_label, stem_text from question where parent_id=?", (p,)).fetchall()
        print(f"-- parent {p} {labels(p)} | {stem(p,80)}")
        for s in sibs:
            print(f"    sib {s[0]} {s[1]} {labels(s[0])} | {(s[2] or '')[:60].replace(chr(10),' ')}")
