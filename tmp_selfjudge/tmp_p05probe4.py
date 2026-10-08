"""p05 probe4: final checks - 2.18 full text, 4.13/4.14/4.15, methane/landfill, 29740, 34231/34232, squalane family."""
import sqlite3, json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
con = sqlite3.connect(f"file:{ROOT / '.data' / 'examdata.db'}?mode=ro", uri=True)
c = con.cursor()

def sq(t, n=600):
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

print("=== FULL SPEC: 2.18, 4.13, 4.14, 4.15 ===")
for code in ("WCH11-2.18","WCH11-4.13","WCH11-4.14","WCH11-4.15","WCH11-3.22","WCH11-1.11"):
    t = fulltext(code)
    print(f"\n--- {code} ---\n{t}")

print("\n=== MS methane (WCH11) ===")
cur = con.cursor()
rows = cur.execute("""select q.id,q.number_path,q.marks,m.answer_text,
   (select group_concat(tn.code) from question_taxonomy qt join taxonomy_node tn on tn.id=qt.node_id where qt.question_id=q.id)
   from question q join mark_scheme_entry m on m.question_id=q.id
   where m.answer_text like '%methane%'
     and exists (select 1 from question_taxonomy qt join taxonomy_node tn on tn.id=qt.node_id
                 where qt.question_id=q.id and tn.code like 'WCH11-%')""").fetchall()
for qid, npath, mk, ms, cds in rows:
    print(f"  [{qid}] {npath} m={mk} codes={cds} :: {sq(ms, 130)}")

print("\n=== stems landfill (WCH11) ===")
cur = con.cursor()
rows = cur.execute("""select q.id,q.number_path,q.marks,q.stem_text,
   (select group_concat(tn.code) from question_taxonomy qt join taxonomy_node tn on tn.id=qt.node_id where qt.question_id=q.id)
   from question q where q.stem_text like '%landfill%'
     and exists (select 1 from question_taxonomy qt join taxonomy_node tn on tn.id=qt.node_id
                 where qt.question_id=q.id and tn.code like 'WCH11-%')""").fetchall()
for qid, npath, mk, stem, cds in rows:
    print(f"  [{qid}] {npath} m={mk} codes={cds} :: {sq(stem, 130)}")

print("\n=== 29740 full ===")
row = c.execute("select id, number_path, parent_id, marks, stem_text from question where id=29740").fetchone()
if row:
    print(f"  [{row[0]}] {row[1]} m={row[3]} par={row[2]} codes={codes(29740)}")
    print(f"  Q: {sq(row[4], 700)}")
    cur2 = con.cursor()
    for ms in cur2.execute("select answer_text from mark_scheme_entry where question_id=29740").fetchall():
        print(f"  MS: {sq(ms[0], 500)}")
# parent context
row = c.execute("select parent_id from question where id=29740").fetchone()
if row and row[0]:
    par = row[0]
    fam = c.execute("select id, number_path, marks, stem_text from question where id=? or parent_id=? order by id", (par, par)).fetchall()
    print(f"  --- family root {par} ---")
    for fid, npath, mk, stem in fam:
        print(f"  [{fid}] {npath} m={mk} codes={codes(fid)} :: {sq(stem, 120)}")

print("\n=== 34231/34232 full ===")
for qid in (34231, 34232, 34233):
    row = c.execute("select id, number_path, parent_id, marks, stem_text from question where id=?", (qid,)).fetchone()
    if row:
        print(f"\n  [{row[0]}] {row[1]} m={row[3]} par={row[2]} codes={codes(qid)}")
        print(f"  Q: {sq(row[4], 900)}")
        cur2 = con.cursor()
        for ms in cur2.execute("select answer_text from mark_scheme_entry where question_id=?", (qid,)).fetchall():
            print(f"  MS: {sq(ms[0], 400)}")

print("\n=== squalane family 33199..33206 ===")
fam = c.execute("select id, number_path, parent_id, marks, stem_text from question where id=33199 or parent_id=33199 order by id").fetchall()
for fid, npath, par, mk, stem in fam:
    print(f"\n  [{fid}] {npath} m={mk} par={par} codes={codes(fid)}")
    print(f"  Q: {sq(stem, 300)}")
    cur2 = con.cursor()
    for ms in cur2.execute("select answer_text from mark_scheme_entry where question_id=?", (fid,)).fetchall():
        print(f"  MS: {sq(ms[0], 200)}")

print("\n=== 33817/33819 (p03 precedents for 2.18) ===")
for qid in (33817, 33819):
    row = c.execute("select id, number_path, parent_id, marks, stem_text from question where id=?", (qid,)).fetchone()
    if row:
        print(f"\n  [{row[0]}] {row[1]} m={row[3]} par={row[2]} codes={codes(qid)}")
        print(f"  Q: {sq(row[4], 400)}")
        cur2 = con.cursor()
        for ms in cur2.execute("select answer_text from mark_scheme_entry where question_id=?", (qid,)).fetchall():
            print(f"  MS: {sq(ms[0], 300)}")

print("\nDONE")
