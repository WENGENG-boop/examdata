"""Read-only precedent context for WST selfjudge: MS + similar already-labeled questions (same unit).

usage: python tmp_precedent_ctx.py WST01 59191 59211 ...
"""
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
con = sqlite3.connect(f"file:{ROOT / '.data' / 'examdata.db'}?mode=ro", uri=True)
c = con.cursor()


BOILER = re.compile(r"(leave blank|question \d+ continued|do not write|total \d+ marks|turn over|_+)")


def norm(t):
    t = (t or "").lower()
    t = BOILER.sub(" ", t)
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return " ".join(t.split())


def grams(t, n=5):
    t = norm(t)
    if len(t) < n:
        return {t} if t else set()
    return {t[i:i + n] for i in range(len(t) - n + 1)}


def sim(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


unit = sys.argv[1]
args = sys.argv[2:]
papers = []
if "--paper" in args:
    i = args.index("--paper")
    papers = [int(args[i + 1])]
    args = args[:i] + args[i + 2:]
qids = [int(x) for x in args if x.isdigit()]
kws = [x for x in args if not x.isdigit()]

for pid in papers:
    doc = c.execute("""select d.title from paper p join document d on d.id = p.document_id
                       where p.id = ?""", (pid,)).fetchone()
    print(f"##### PAPER {pid} :: {doc[0][:70] if doc else '?'}")
    for r in c.execute("""select q.id, q.number_label, q.marks, coalesce(tn.code, '-'),
                                 substr(replace(q.stem_text, char(10), ' '), 1, 120)
                          from question q
                          left join question_taxonomy qt on qt.question_id = q.id
                          left join taxonomy_node tn on tn.id = qt.node_id
                          where q.paper_id = ? order by q.display_order""", (pid,)):
        print(f"  {r[0]} #{r[1]} {r[2]}mk [{r[3]}] {r[4]}")
    print()

cands = []
for cid, stem, code in c.execute(
        """select q.id, q.stem_text, tn.code from question q
           join question_taxonomy qt on qt.question_id = q.id
           join taxonomy_node tn on tn.id = qt.node_id
           where tn.code like ? and q.stem_text is not null""", (unit + "-%",)):
    g = grams(stem)
    if g:
        cands.append((cid, norm(stem), code, g))
print(f"# candidates with existing {unit} labels: {len(cands)}")

for kw in kws:
    from collections import Counter
    hits = [(cid, ns, code) for cid, ns, code, g in cands if norm(kw) in ns]
    dist = Counter(h[2] for h in hits)
    print(f"### KEYWORD {kw!r}: {len(hits)} hits; labels: {dict(dist.most_common(8))}")
    for cid, ns, code in hits[:4]:
        print(f"    ex {cid} [{code}] {ns[:100]}")
    print()

for qid in qids:
    row = c.execute(
        """select q.id, q.paper_id, q.parent_id, q.number_label, q.marks,
                  replace(q.stem_text, char(10), ' ')
           from question q where q.id = ?""", (qid,)).fetchone()
    if not row:
        print(f"Q {qid} NOT FOUND")
        continue
    q_id, pid, par, num, marks, stem = row
    print(f"===== Q {qid} unit={unit} paper={pid} parent={par} #{num} {marks}mk")
    print(f"STEM: {stem[:300]}")
    if par:
        prow = c.execute(
            """select q.id, q.number_label, replace(q.stem_text, char(10), ' ')
               from question q where q.id = ?""", (par,)).fetchone()
        if prow:
            print(f"PARENT {prow[0]} #{prow[1]}: {prow[2][:280]}")
    for ms in c.execute(
            """select number_path, marks, replace(answer_text, char(10), ' | ')
               from mark_scheme_entry where question_id = ? order by id limit 6""", (qid,)):
        print(f"MS [{ms[0]}] {ms[1]}mk: {ms[2][:420]}")
    g = grams(stem)
    scored = sorted(((sim(g, cg), cid, cs, cc) for cid, cs, cc, cg in cands), reverse=True)
    top = [s for s in scored[:8] if s[0] > 0.35]
    print("PRECEDENT:")
    for s, cid, cs, cc in top:
        print(f"  {s:.2f} {cid} [{cc}] {cs[:110]}")
    if not top:
        print("  (none > 0.35)")
    sibs = c.execute(
        """select q.id, q.number_label, coalesce(tn.code, '-')
           from question q
           left join question_taxonomy qt on qt.question_id = q.id
           left join taxonomy_node tn on tn.id = qt.node_id
           where q.paper_id = ? and q.parent_id = ? order by q.display_order""",
        (pid, par)).fetchall()
    print("SAME-PARENT SIBLINGS: " + ", ".join(f"{s[0]}#{s[1]}[{s[2]}]" for s in sibs))
    print()
