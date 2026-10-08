"""p05 probe3: full context for 30677/31531/32772/31789/30987/29092 + family checks."""
import sqlite3, re
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

def dump(qid, mslen=400, stemlen=400):
    row = c.execute("select id, number_path, parent_id, marks, stem_text from question where id=?", (qid,)).fetchone()
    if not row:
        print(f"  [{qid}] NOT FOUND"); return
    fid, npath, par, mk, stem = row
    print(f"  [{fid}] {npath} m={mk} par={par} codes={codes(fid)}")
    print(f"      Q: {sq(stem, stemlen)}")
    cur2 = con.cursor()
    for ms in cur2.execute("select answer_text from mark_scheme_entry where question_id=?", (fid,)).fetchall():
        print(f"      MS: {sq(ms[0], mslen)}")

print("=== 30677 (P vs Si melting) full ===")
dump(30677, 500)
print("\n=== 31531 (Si vs P) full ===")
dump(31531, 500)
print("\n=== 32772 (Period3 melting table) full ===")
dump(32772, 500)
print("\n=== 31789 (increasing melting temp series) full ===")
dump(31789, 400)
print("\n=== 30987 (S vs P4) full ===")
dump(30987, 400)

print("\n=== 30677 family (par=?) ===")
row = c.execute("select parent_id from question where id=30677").fetchone()
par = row[0] if row else None
print(f"  parent={par}")
if par:
    fam = c.execute("select id, number_path, marks, stem_text from question where id=? or parent_id=? order by id", (par, par)).fetchall()
    for fid, npath, mk, stem in fam:
        print(f"  [{fid}] {npath} m={mk} codes={codes(fid)} :: {sq(stem, 160)}")

print("\n=== 29092 full + family ===")
dump(29092, 600)
row = c.execute("select parent_id from question where id=29092").fetchone()
par = row[0] if row else None
print(f"  parent={par}")
if par:
    fam = c.execute("select id, number_path, marks, stem_text from question where id=? or parent_id=? order by id", (par, par)).fetchall()
    for fid, npath, mk, stem in fam:
        print(f"  [{fid}] {npath} m={mk} codes={codes(fid)} :: {sq(stem, 140)}")

print("\n=== 34231 family (34232 siblings) ===")
fam = c.execute("select id, number_path, marks, stem_text from question where id=34231 or parent_id=34231 order by id").fetchall()
for fid, npath, mk, stem in fam:
    print(f"  [{fid}] {npath} m={mk} codes={codes(fid)} :: {sq(stem, 140)}")

print("\n=== 33204 full ===")
dump(33204, 500)
print("\n=== 33201 full ===")
dump(33201, 500)

print("\n=== pack membership check ===")
import subprocess
for qid in (29092, 34236, 34237, 33201, 33204, 30677, 31531):
    for pk in ("p05","p06"):
        p = ROOT / "tmp_selfjudge" / "r2" / "ial18-chemistry" / f"WCH11-{pk}.txt"
        txt = p.read_text(encoding="utf-8", errors="replace")
        if f"[{qid}]" in txt or f" {qid} " in txt or f":{qid}" in txt:
            print(f"  {qid} found in WCH11-{pk}")
print("DONE")
