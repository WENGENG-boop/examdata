"""p05 probe: spec texts, family dumps, precedent searches."""
import sqlite3, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
con = sqlite3.connect(f"file:{ROOT / '.data' / 'examdata.db'}?mode=ro", uri=True)
c = con.cursor()

def sq(t, n=300):
    import re
    return re.sub(r"\s+", " ", (t or "").strip())[:n]

def codes(qid, cur=None):
    cur = cur or con.cursor()
    rows = cur.execute("""select tn.code from question_taxonomy qt
        join taxonomy_node tn on tn.id=qt.node_id where qt.question_id=?
        order by tn.code""", (qid,)).fetchall()
    return ",".join(r[0] for r in rows) or "-"

print("=== SPEC TEXTS ===")
for code in ("WCH11-2.18","WCH11-3.12","WCH11-3.10","WCH11-1.7","WCH11-1.8",
             "WCH11-1.11","WCH11-4.12","WCH11-2.17","WCH11-4.9","WCH11-1.2",
             "WCH11-5.1","WCH11-4.15","WCH11-3.16","WCH11-3.19","WCH11-4.13","WCH11-4.14"):
    row = c.execute("select id, attrs from taxonomy_node where code=?", (code,)).fetchone()
    if row:
        import json
        attrs = json.loads(row[1]) if row[1] else {}
        txt = attrs.get("text") or attrs.get("full_text") or str(attrs)[:400]
        print(f"\n--- {code} (node {row[0]}) ---")
        print(sq(txt, 700))

print("\n=== FAMILY DUMPS ===")
for root in (29736, 31525, 30673, 32806, 32814, 32150, 33199, 34222, 32819, 30005, 29547, 29089, 30472, 29248, 29555, 29244, 31152, 31161, 32347, 30000):
    fam = c.execute("""select id, number_path, parent_id, marks, stem_text from question
                       where id=? or parent_id=? order by id""", (root, root)).fetchall()
    print(f"\n--- family root {root} ---")
    for fid, npath, par, mk, stem in fam:
        print(f"  [{fid}] {npath} m={mk} par={par} codes={codes(fid)}")
        print(f"      Q: {sq(stem, 180)}")
        ms = c.execute("select answer_text from mark_scheme_entry where question_id=?", (fid,)).fetchone()
        if ms:
            print(f"      MS: {sq(ms[0], 200)}")

print("\n=== PRECEDENT SEARCHES ===")
def search(label, sql, args, limit=25):
    print(f"\n--- {label} ---")
    cur = con.cursor()
    rows = cur.execute(sql, args).fetchall()
    for r in rows[:limit]:
        qid, npath, mk, stem, mscode = r
        print(f"  [{qid}] {npath} m={mk} codes={mscode} :: {sq(stem, 120)}")

search("stems: melting temp silicon vs phosphorus",
  """select q.id,q.number_path,q.marks,q.stem_text,
     (select group_concat(tn.code) from question_taxonomy qt join taxonomy_node tn on tn.id=qt.node_id where qt.question_id=q.id)
     from question q where q.stem_text like '%melting temperature%' and (q.stem_text like '%silicon%' or q.stem_text like '%phosphorus%')""",
  ())

search("MS: giant covalent",
  """select q.id,q.number_path,q.marks,q.stem_text,
     (select group_concat(tn.code) from question_taxonomy qt join taxonomy_node tn on tn.id=qt.node_id where qt.question_id=q.id)
     from question q join mark_scheme_entry m on m.question_id=q.id
     where m.answer_text like '%giant covalent%'""",
  ())

search("MS: molar volume 24000 / 24 dm3",
  """select q.id,q.number_path,q.marks,q.stem_text,
     (select group_concat(tn.code) from question_taxonomy qt join taxonomy_node tn on tn.id=qt.node_id where qt.question_id=q.id)
     from question q join mark_scheme_entry m on m.question_id=q.id
     where m.answer_text like '%24000%' or m.answer_text like '%24 000%'""",
  ())

search("stems: separated from the mixture / filtration",
  """select q.id,q.number_path,q.marks,q.stem_text,
     (select group_concat(tn.code) from question_taxonomy qt join taxonomy_node tn on tn.id=qt.node_id where qt.question_id=q.id)
     from question q where q.stem_text like '%separate%' and q.stem_text like '%mixture%'""",
  ())

search("stems: squalane",
  """select q.id,q.number_path,q.marks,q.stem_text,
     (select group_concat(tn.code) from question_taxonomy qt join taxonomy_node tn on tn.id=qt.node_id where qt.question_id=q.id)
     from question q where q.stem_text like '%squalane%'""",
  ())
