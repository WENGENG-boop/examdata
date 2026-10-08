"""p05 probe2: verify open decisions (33204->1.4, 33201, 29092, 33208, 29740) + misc dumps."""
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

print("=== SPEC TEXTS (WCH11 open points) ===")
for code in ("WCH11-1.4","WCH11-1.1","WCH11-1.11","WCH11-4.9","WCH11-4.12",
             "WCH11-1.10","WCH11-1.9","WCH11-1.6","WCH11-2.5","WCH11-4.6","WCH11-4.5"):
    row = c.execute("select id, attrs from taxonomy_node where code=?", (code,)).fetchone()
    if row:
        attrs = json.loads(row[1]) if row[1] else {}
        txt = attrs.get("text") or attrs.get("full_text") or str(attrs)[:400]
        print(f"\n--- {code} (node {row[0]}) ---")
        print(sq(txt, 700))
    else:
        print(f"\n--- {code} NOT FOUND ---")

print("\n=== ALL WCH11 TAXONOMY POINTS (code :: first 100 chars) ===")
rows = c.execute("""select code, attrs from taxonomy_node where code like 'WCH11-%'
                    order by code""").fetchall()
for code, attrs in rows:
    a = json.loads(attrs) if attrs else {}
    txt = a.get("text") or ""
    print(f"  {code} :: {sq(txt, 110)}")

print("\n=== PRECEDENTS: ppm ===")
cur = con.cursor()
rows = cur.execute("""select q.id,q.number_path,q.marks,q.stem_text,
   (select group_concat(tn.code) from question_taxonomy qt join taxonomy_node tn on tn.id=qt.node_id where qt.question_id=q.id)
   from question q where q.stem_text like '%ppm%'""").fetchall()
for qid, npath, mk, stem, cds in rows:
    print(f"  [{qid}] {npath} m={mk} codes={cds} :: {sq(stem, 140)}")

print("\n=== PRECEDENTS: molecular formula of (WCH11) ===")
cur = con.cursor()
rows = cur.execute("""select q.id,q.number_path,q.marks,q.stem_text,
   (select group_concat(tn.code) from question_taxonomy qt join taxonomy_node tn on tn.id=qt.node_id where qt.question_id=q.id)
   from question q where q.stem_text like '%molecular formula of%'""").fetchall()
for qid, npath, mk, stem, cds in rows:
    print(f"  [{qid}] {npath} m={mk} codes={cds} :: {sq(stem, 140)}")

print("\n=== PRECEDENTS: MS climate change / global warming (WCH11) ===")
cur = con.cursor()
rows = cur.execute("""select q.id,q.number_path,q.marks,m.answer_text,
   (select group_concat(tn.code) from question_taxonomy qt join taxonomy_node tn on tn.id=qt.node_id where qt.question_id=q.id)
   from question q join mark_scheme_entry m on m.question_id=q.id
   where (m.answer_text like '%climate change%' or m.answer_text like '%global warming%')
     and exists (select 1 from question_taxonomy qt join taxonomy_node tn on tn.id=qt.node_id
                 where qt.question_id=q.id and tn.code like 'WCH11-%')""").fetchall()
for qid, npath, mk, ms, cds in rows:
    print(f"  [{qid}] {npath} m={mk} codes={cds} :: MS {sq(ms, 160)}")

print("\n=== PRECEDENTS: MS distillation (WCH11) ===")
cur = con.cursor()
rows = cur.execute("""select q.id,q.number_path,q.marks,m.answer_text,
   (select group_concat(tn.code) from question_taxonomy qt join taxonomy_node tn on tn.id=qt.node_id where qt.question_id=q.id)
   from question q join mark_scheme_entry m on m.question_id=q.id
   where m.answer_text like '%distillation%'
     and exists (select 1 from question_taxonomy qt join taxonomy_node tn on tn.id=qt.node_id
                 where qt.question_id=q.id and tn.code like 'WCH11-%')""").fetchall()
for qid, npath, mk, ms, cds in rows:
    print(f"  [{qid}] {npath} m={mk} codes={cds} :: MS {sq(ms, 160)}")

print("\n=== PRECEDENTS: MS filtration (WCH11) ===")
cur = con.cursor()
rows = cur.execute("""select q.id,q.number_path,q.marks,m.answer_text,
   (select group_concat(tn.code) from question_taxonomy qt join taxonomy_node tn on tn.id=qt.node_id where qt.question_id=q.id)
   from question q join mark_scheme_entry m on m.question_id=q.id
   where m.answer_text like '%filtration%'
     and exists (select 1 from question_taxonomy qt join taxonomy_node tn on tn.id=qt.node_id
                 where qt.question_id=q.id and tn.code like 'WCH11-%')""").fetchall()
for qid, npath, mk, ms, cds in rows:
    print(f"  [{qid}] {npath} m={mk} codes={cds} :: MS {sq(ms, 160)}")

print("\n=== DUMPS: 34232..34235 family ===")
for root in (34232,):
    fam = c.execute("""select id, number_path, parent_id, marks, stem_text from question
                       where id=? or parent_id=? order by id""", (root, root)).fetchall()
    for fid, npath, par, mk, stem in fam:
        print(f"  [{fid}] {npath} m={mk} par={par} codes={codes(fid)}")
        print(f"      Q: {sq(stem, 180)}")
        cur2 = con.cursor()
        ms = cur2.execute("select answer_text from mark_scheme_entry where question_id=?", (fid,)).fetchone()
        if ms:
            print(f"      MS: {sq(ms[0], 250)}")

print("\n=== DUMPS: 32359 family + 34236 family ===")
for root in (32359, 34236):
    fam = c.execute("""select id, number_path, parent_id, marks, stem_text from question
                       where id=? or parent_id=? order by id""", (root, root)).fetchall()
    print(f"\n--- root {root} ---")
    for fid, npath, par, mk, stem in fam:
        print(f"  [{fid}] {npath} m={mk} par={par} codes={codes(fid)}")
        print(f"      Q: {sq(stem, 150)}")

print("\n=== MISC: 32772, 31789 codes ===")
for qid in (32772, 31789, 30987):
    row = c.execute("select id, number_path, marks, stem_text from question where id=?", (qid,)).fetchone()
    if row:
        print(f"  [{row[0]}] {row[1]} m={row[2]} codes={codes(qid)} :: {sq(row[3], 140)}")

print("\nDONE")
