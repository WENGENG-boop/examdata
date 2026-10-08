"""p06 probe: spec texts + context for borderline items."""
import sqlite3, json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
con = sqlite3.connect(f"file:{ROOT / '.data' / 'examdata.db'}?mode=ro", uri=True)
c = con.cursor()

def sq(t, n=400):
    return re.sub(r"\s+", " ", (t or "").strip())[:n]

def codes(qid):
    cur = con.cursor()
    rows = cur.execute("""select tn.code from question_taxonomy qt
        join taxonomy_node tn on tn.id=qt.node_id where qt.question_id=?
        order by tn.code""", (qid,)).fetchall()
    return ",".join(r[0] for r in rows) or "-"

def fulltext(code):
    row = c.execute("select id, attrs from taxonomy_node where code=?", (code,)).fetchone()
    if row:
        a = json.loads(row[1]) if row[1] else {}
        return a.get("text") or a.get("full_text") or ""
    return None

print("=== FULL SPEC: 5.4, 5.2, 4.6, 4.7, 4.18, 1.8, 1.6, 1.7, 4.2 ===")
for code in ("WCH11-5.4","WCH11-5.2","WCH11-4.6","WCH11-4.7","WCH11-4.18","WCH11-1.8","WCH11-1.6","WCH11-1.7","WCH11-4.2"):
    t = fulltext(code)
    print(f"\n--- {code} ---\n{t}")

print("\n=== pV=nRT questions (WCH11) ===")
cur = con.cursor()
rows = cur.execute("""select q.id,q.number_path,q.marks,q.stem_text,
   (select group_concat(tn.code) from question_taxonomy qt join taxonomy_node tn on tn.id=qt.node_id where qt.question_id=q.id)
   from question q where (q.stem_text like '%pV = nRT%' or q.stem_text like '%pV=nRT%' or q.stem_text like '%nRT%' or q.stem_text like '%Ideal gas%')
     and exists (select 1 from question_taxonomy qt join taxonomy_node tn on tn.id=qt.node_id
                 where qt.question_id=q.id and tn.code like 'WCH11-%')""").fetchall()
for qid, npath, mk, stem, cds in rows:
    print(f"  [{qid}] {npath} m={mk} codes={cds} :: {sq(stem, 160)}")

print("\n=== 29251/29252/29253 context ===")
for qid in (29251, 29252, 29253):
    row = c.execute("select id, number_path, parent_id, marks, stem_text from question where id=?", (qid,)).fetchone()
    if row:
        print(f"\n  [{row[0]}] {row[1]} m={row[3]} par={row[2]} codes={codes(qid)}")
        print(f"  Q: {sq(row[4], 700)}")
        cur2 = con.cursor()
        for ms in cur2.execute("select answer_text from mark_scheme_entry where question_id=?", (qid,)).fetchall():
            print(f"  MS: {sq(ms[0], 400)}")

print("\n=== 33682/33685/33686/33687 context ===")
for qid in (33682, 33685, 33686, 33687):
    row = c.execute("select id, number_path, parent_id, marks, stem_text from question where id=?", (qid,)).fetchone()
    if row:
        print(f"\n  [{row[0]}] {row[1]} m={row[3]} par={row[2]} codes={codes(qid)}")
        print(f"  Q: {sq(row[4], 600)}")
        cur2 = con.cursor()
        for ms in cur2.execute("select answer_text from mark_scheme_entry where question_id=?", (qid,)).fetchall():
            print(f"  MS: {sq(ms[0], 350)}")

print("\n=== 31541 family full ===")
for qid in (31541, 31542, 31543):
    row = c.execute("select id, number_path, parent_id, marks, stem_text from question where id=?", (qid,)).fetchone()
    if row:
        print(f"\n  [{row[0]}] {row[1]} m={row[3]} par={row[2]} codes={codes(qid)}")
        print(f"  Q: {sq(row[4], 500)}")
        cur2 = con.cursor()
        for ms in cur2.execute("select answer_text from mark_scheme_entry where question_id=?", (qid,)).fetchall():
            print(f"  MS: {sq(ms[0], 300)}")

print("\nDONE")
