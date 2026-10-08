"""Verify business batches 001-007 landed in DB (semantics-aware).

Semantics encoded from review.py:
- export filter: reviewed=False AND confidence < 0.35 (above-threshold rows not exported)
- keep:  marks ALL unreviewed algo rows reviewed -> batch set must be subset of DB codes,
         all DB rows reviewed
- change: deletes ALL unreviewed algo rows, inserts single ai-review row -> code present,
          all other rows reviewed
- drop:  deletes all unreviewed algo rows
"""
import json
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from examdata.core import models as m

ROOT = Path(__file__).resolve().parent
DB = ROOT / ".data" / "examdata.db"
DEC = ROOT / ".data" / "tagging" / "review-export" / "ial18-business" / "decisions"
BAT = ROOT / ".data" / "tagging" / "review-export" / "ial18-business" / "batches"

engine = create_engine(f"sqlite:///{DB}")
with Session(engine) as s:
    def rows_of(qid):
        return s.execute(
            select(m.QuestionTaxonomy, m.TaxonomyNode.code)
            .join(m.TaxonomyNode, m.QuestionTaxonomy.node_id == m.TaxonomyNode.id)
            .where(m.QuestionTaxonomy.question_id == qid)
            .order_by(m.TaxonomyNode.code)
        ).all()

    total_bad = 0
    all_qids = []
    for b in ["001", "002", "003", "004", "005", "006", "007"]:
        decs = [json.loads(l) for l in open(DEC / f"batch-{b}.jsonl", encoding="utf-8")]
        cur = {}
        for l in open(BAT / f"batch-{b}.jsonl", encoding="utf-8"):
            rec = json.loads(l)
            cur[rec["question_id"]] = {c["code"] for c in rec["current"]}
        all_qids.extend(cur.keys())
        bad = []
        nchg = nkeep = ndrop = 0
        for d in decs:
            qid = d["question_id"]
            rows = rows_of(qid)
            codes = [r[1] for r in rows]
            if d["decision"] == "change":
                nchg += 1
                ok = d["code"] in codes and all(
                    (r.assigned_by == "ai-review-v1" and r.reviewed
                     and abs((r.confidence or 0) - 1.0) < 1e-9)
                    if c == d["code"] else r.reviewed
                    for r, c in rows
                ) and sum(1 for c in codes if c == d["code"]) == 1
            elif d["decision"] == "keep":
                nkeep += 1
                ok = cur[qid] <= set(codes) and all(r[0].reviewed for r in rows)
            else:  # drop
                ndrop += 1
                ok = all(r[0].reviewed for r in rows)
            if not ok:
                bad.append((qid, d["decision"], d.get("code"), codes,
                            [(r[0].assigned_by, r[0].reviewed, r[0].confidence) for r in rows]))
        total_bad += len(bad)
        print(f"batch-{b}: {len(decs)} decisions ({nchg} change / {nkeep} keep / {ndrop} drop), bad: {len(bad)}")
        for row in bad[:8]:
            print("   BAD", row)
    print("TOTAL BAD:", total_bad)

    # global: no unreviewed rows remain on any of the batch questions
    unreviewed = []
    for qid in all_qids:
        rows = rows_of(qid)
        if not rows:
            unreviewed.append((qid, "NO_ROWS"))
            continue
        bad_rows = [(r[1], r[0].assigned_by, r[0].confidence) for r in rows if not r[0].reviewed]
        if bad_rows:
            unreviewed.append((qid, bad_rows))
    print("questions with unreviewed rows or no rows:", len(unreviewed))
    for u in unreviewed[:20]:
        print("   ", u)
