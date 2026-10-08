"""p06 probe 2: conventions for type-of-reaction / neutralisation / termination / molar-volume."""
import sqlite3, json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
con = sqlite3.connect(f"file:{ROOT / '.data' / 'examdata.db'}?mode=ro", uri=True)
c = con.cursor()

def sq(t, n=250):
    return re.sub(r"\s+", " ", (t or "").strip())[:n]

def codes(qid):
    cur = con.cursor()
    rows = cur.execute("""select tn.code from question_taxonomy qt
        join taxonomy_node tn on tn.id=qt.node_id where qt.question_id=?
        order by tn.code""", (qid,)).fetchall()
    return ",".join(r[0] for r in rows) or "-"

def qrows(where):
    cur = con.cursor()
    return cur.execute(f"""select q.id, q.number_path, q.marks, q.stem_text,
       (select group_concat(tn.code) from question_taxonomy qt join taxonomy_node tn on tn.id=qt.node_id where qt.question_id=q.id)
       from question q where {where}
         and exists (select 1 from question_taxonomy qt join taxonomy_node tn on tn.id=qt.node_id
                     where qt.question_id=q.id and tn.code like 'WCH11-%')
       order by q.id""").fetchall()

print("=== A. 'type of reaction' in stem (WCH11) ===")
for qid, npath, mk, stem, cds in qrows("q.stem_text like '%type of reaction%'"):
    print(f"[{qid}] {npath} m={mk} codes={cds} :: {sq(stem, 130)}")

def msrows(where):
    cur = con.cursor()
    return cur.execute(f"""select distinct q.id, q.number_path, ms.answer_text,
       (select group_concat(tn.code) from question_taxonomy qt join taxonomy_node tn on tn.id=qt.node_id where qt.question_id=q.id)
       from mark_scheme_entry ms join question q on q.id=ms.question_id
       where {where}
         and exists (select 1 from question_taxonomy qt join taxonomy_node tn on tn.id=qt.node_id
                     where qt.question_id=q.id and tn.code like 'WCH11-%')
       order by q.id""").fetchall()

print("\n=== B. MS contains 'neutralis' (WCH11) ===")
for qid, npath, ans, cds in msrows("ms.answer_text like '%neutralis%'"):
    print(f"[{qid}] {npath} codes={cds} :: {sq(ans, 130)}")

print("\n=== C. MS contains 'termination' (WCH11) ===")
for qid, npath, ans, cds in msrows("ms.answer_text like '%termination%'"):
    print(f"[{qid}] {npath} codes={cds} :: {sq(ans, 130)}")

print("\n=== D. MS contains 'molar volume' or '24000' (WCH11) ===")
for qid, npath, ans, cds in msrows("ms.answer_text like '%molar volume%' or ms.answer_text like '%24000%'"):
    print(f"[{qid}] {npath} codes={cds} :: {sq(ans, 130)}")

print("\n=== E. 30472 / 34241 / 34232 context ===")
for qid in (30472, 34241, 34232):
    row = c.execute("select id, number_path, parent_id, marks, stem_text from question where id=?", (qid,)).fetchone()
    if row:
        print(f"\n[{row[0]}] {row[1]} m={row[3]} par={row[2]} codes={codes(qid)}")
        print(f"Q: {sq(row[4], 400)}")
        cur2 = con.cursor()
        for ms in cur2.execute("select answer_text from mark_scheme_entry where question_id=?", (qid,)).fetchall():
            print(f"MS: {sq(ms[0], 250)}")

print("\n=== F. MS 'initiation' or 'propagation' (WCH11) ===")
for qid, npath, ans, cds in msrows("ms.answer_text like '%initiation%' or ms.answer_text like '%propagation%'"):
    print(f"[{qid}] {npath} codes={cds} :: {sq(ans, 130)}")

print("\n=== G. stem 'relative formula mass' (WCH11) ===")
for qid, npath, mk, stem, cds in qrows("q.stem_text like '%relative formula mass%'"):
    print(f"[{qid}] {npath} m={mk} codes={cds} :: {sq(stem, 140)}")

print("\nDONE")
