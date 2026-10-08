"""Quantify the 85 changed docs: questions, taxonomy by source, derived rows. Read-only."""
from __future__ import annotations
import sqlite3, json
from pathlib import Path
from collections import Counter, defaultdict
ROOT = Path(__file__).resolve().parent
con = sqlite3.connect(ROOT/".data/examdata.db"); con.row_factory = sqlite3.Row; cur = con.cursor()
d = json.load(open("tmp_r8_scan_split.json"))
changed = d["changed"]
print(f"changed docs: {len(changed)}")
doc_ids = [c["doc"] for c in changed]
# map docs -> papers
qmarks = ",".join("?"*len(doc_ids))
papers = cur.execute(f"select id, document_id, question_count from paper where document_id in ({qmarks})", doc_ids).fetchall()
paper_by_doc = {p["document_id"]: p for p in papers}
print("docs with a paper record:", len(paper_by_doc), "/", len(doc_ids))
missing_paper = [i for i in doc_ids if i not in paper_by_doc]
print("docs without paper record:", len(missing_paper), missing_paper[:10])
pids = [p["id"] for p in papers]
if pids:
    ph = ",".join("?"*len(pids))
    nq = cur.execute(f"select count(*) n from question where paper_id in ({ph})", pids).fetchone()["n"]
    print("questions in these papers:", nq)
    print("taxonomy by source:")
    for r in cur.execute(f"""select qt.source, count(*) n from question_taxonomy qt join question q on q.id=qt.question_id
        where q.paper_id in ({ph}) group by 1 order by n desc""", pids):
        print("   ", r["source"], r["n"])
    for tbl in ("official_answer","generated_explanation","difficulty","question_asset","question_similarity","formula","mark_scheme_entry"):
        col = "question_id"
        try:
            n = cur.execute(f"select count(*) n from {tbl} where {col} in (select id from question where paper_id in ({ph}))", pids).fetchone()["n"]
            print(f"   {tbl}: {n}")
        except Exception as ex:
            print(f"   {tbl}: ERR {ex}")
    # per-doc question counts
    print("\nper-doc question counts (old):")
    rows = cur.execute(f"""select q.paper_id, count(*) n, sum(case when qt.n>0 then 1 else 0 end) tagged from question q
        left join (select question_id, count(*) n from question_taxonomy group by 1) qt on qt.question_id=q.id
        where q.paper_id in ({ph}) group by 1 order by n""", pids).fetchall()
    for r in rows[:50]:
        doc = [p["document_id"] for p in papers if p["id"]==r["paper_id"]][0]
        print(f"    doc={doc} paper={r['paper_id']} questions={r['n']} tagged={r['tagged']}")
