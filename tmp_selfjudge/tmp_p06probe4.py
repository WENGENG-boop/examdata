"""p06 probe 4: homolytic / flammable precedent + 30463 family + type-of-reaction MS details."""
import sqlite3, json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
con = sqlite3.connect(f"file:{ROOT / '.data' / 'examdata.db'}?mode=ro", uri=True)
c = con.cursor()

def sq(t, n=300):
    return re.sub(r"\s+", " ", (t or "").strip())[:n]

def codes(qid):
    cur = con.cursor()
    rows = cur.execute("""select tn.code from question_taxonomy qt
        join taxonomy_node tn on tn.id=qt.node_id where qt.question_id=?
        order by tn.code""", (qid,)).fetchall()
    return ",".join(r[0] for r in rows) or "-"

def msrows(where):
    cur = con.cursor()
    return cur.execute(f"""select distinct q.id, q.number_path, ms.answer_text,
       (select group_concat(tn.code) from question_taxonomy qt join taxonomy_node tn on tn.id=qt.node_id where qt.question_id=q.id)
       from mark_scheme_entry ms join question q on q.id=ms.question_id
       where {where}
         and exists (select 1 from question_taxonomy qt join taxonomy_node tn on tn.id=qt.node_id
                     where qt.question_id=q.id and tn.code like 'WCH11-%')
       order by q.id""").fetchall()

print("=== MS 'homolytic' (WCH11) ===")
for qid, npath, ans, cds in msrows("ms.answer_text like '%homolytic%'"):
    print(f"[{qid}] {npath} codes={cds} :: {sq(ans, 150)}")

print("\n=== MS 'flammable' or 'non-toxic' (WCH11) ===")
for qid, npath, ans, cds in msrows("ms.answer_text like '%flammable%' or ms.answer_text like '%non-toxic%'"):
    print(f"[{qid}] {npath} codes={cds} :: {sq(ans, 150)}")

print("\n=== 30462/30463, 33844, 33653, 32803, 30473 detail ===")
for qid in (30462, 30463, 33844, 33653, 32803, 30473):
    row = c.execute("select id, number_path, parent_id, marks, stem_text from question where id=?", (qid,)).fetchone()
    if row:
        print(f"\n[{row[0]}] {row[1]} m={row[3]} par={row[2]} codes={codes(qid)}")
        print(f"Q: {sq(row[4], 300)}")
        cur2 = con.cursor()
        for ms in cur2.execute("select answer_text from mark_scheme_entry where question_id=?", (qid,)).fetchall():
            print(f"MS: {sq(ms[0], 250)}")

print("\n=== 33683/33684 detail ===")
for qid in (33683, 33684):
    row = c.execute("select id, number_path, parent_id, marks, stem_text from question where id=?", (qid,)).fetchone()
    if row:
        print(f"\n[{row[0]}] {row[1]} m={row[3]} par={row[2]} codes={codes(qid)}")
        print(f"Q: {sq(row[4], 300)}")
        cur2 = con.cursor()
        for ms in cur2.execute("select answer_text from mark_scheme_entry where question_id=?", (qid,)).fetchall():
            print(f"MS: {sq(ms[0], 250)}")

print("\nDONE")
