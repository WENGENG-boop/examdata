"""p06 probe 3: 34231 family analogy, gas-volume question framing, 1.12/1.4 full text, acid/base nodes."""
import sqlite3, json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
con = sqlite3.connect(f"file:{ROOT / '.data' / 'examdata.db'}?mode=ro", uri=True)
c = con.cursor()

def sq(t, n=500):
    return re.sub(r"\s+", " ", (t or "").strip())[:n]

def codes(qid):
    cur = con.cursor()
    rows = cur.execute("""select tn.code from question_taxonomy qt
        join taxonomy_node tn on tn.id=qt.node_id where qt.question_id=?
        order by tn.code""", (qid,)).fetchall()
    return ",".join(r[0] for r in rows) or "-"

print("=== 34231 family (GeX4) full ===")
for qid in (34231, 34232, 34233, 34234, 34235):
    row = c.execute("select id, number_path, parent_id, marks, stem_text from question where id=?", (qid,)).fetchone()
    if row:
        print(f"\n[{row[0]}] {row[1]} m={row[3]} par={row[2]} codes={codes(qid)}")
        print(f"Q: {sq(row[4], 400)}")
        cur2 = con.cursor()
        for ms in cur2.execute("select answer_text from mark_scheme_entry where question_id=?", (qid,)).fetchall():
            print(f"MS: {sq(ms[0], 250)}")

print("\n=== 30670 / 31832 stems ===")
for qid in (30670, 31832):
    row = c.execute("select id, number_path, parent_id, marks, stem_text from question where id=?", (qid,)).fetchone()
    if row:
        print(f"\n[{row[0]}] {row[1]} m={row[3]} par={row[2]} codes={codes(qid)}")
        print(f"Q: {sq(row[4], 400)}")
        cur2 = con.cursor()
        for ms in cur2.execute("select answer_text from mark_scheme_entry where question_id=?", (qid,)).fetchall():
            print(f"MS: {sq(ms[0], 250)}")

print("\n=== FULL TEXT: WCH11-1.12, WCH11-1.4, WCH11-1.9, WCH11-1.3 ===")
for code in ("WCH11-1.12","WCH11-1.4","WCH11-1.9","WCH11-1.3"):
    row = c.execute("select attrs from taxonomy_node where code=?", (code,)).fetchone()
    if row:
        a = json.loads(row[0]) if row[0] else {}
        t = a.get("text") or a.get("full_text") or ""
        print(f"\n--- {code} ---\n{t}")

print("\n=== WCH11 nodes whose text mentions acid/base/neutral ===")
cur = con.cursor()
for code, attrs in cur.execute("""select code, attrs from taxonomy_node where code like 'WCH11-%' order by code"""):
    a = json.loads(attrs) if attrs else {}
    t = (a.get("text") or a.get("full_text") or "")
    tl = t.lower()
    if 'acid' in tl or 'base' in tl or 'neutral' in tl:
        print(f"{code}: {sq(t, 160)}")

print("\nDONE")
