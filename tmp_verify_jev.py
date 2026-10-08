"""Verify Jev review decisions landed in DB (semantics-aware, per subject).

Semantics (from review.py):
- keep:  marks ALL unreviewed algo rows reviewed -> batch's current codes must be
         subset of DB codes, all DB rows reviewed
- change: deletes ALL unreviewed algo rows, inserts single ai-review row -> code
          present exactly once (assigned_by='ai-review-v1', reviewed, conf 1.0),
          all other rows reviewed
- drop:  deletes all unreviewed algo rows; all remaining rows reviewed

Usage: python tmp_verify_jev.py --subject ial18-biology
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from examdata.core import models as m

ROOT = Path(__file__).resolve().parent
DB = ROOT / ".data" / "examdata.db"

SUBJECTS = {
    "ial-spanish": ["003"],
    "ial18-biology": [f"{i:03d}" for i in range(3, 14)],
    "ial18-chemistry": [f"{i:03d}" for i in range(1, 10)],
    "ial18-economics": [f"{i:03d}" for i in range(1, 12)],
    "ial18-physics": [f"{i:03d}" for i in range(1, 11)],
    "ial18-mathematics": [f"{i:03d}" for i in range(2, 63) if i != 38],
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--subject", required=True)
    args = ap.parse_args()
    slug = args.subject
    REVIEW = ROOT / ".data" / "tagging" / "review-export" / slug

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
        for b in SUBJECTS[slug]:
            dec_path = REVIEW / "decisions" / f"batch-{b}.jsonl"
            bat_path = REVIEW / "batches" / f"batch-{b}.jsonl"
            decs = [json.loads(l) for l in open(dec_path, encoding="utf-8") if l.strip()]
            cur = {}
            for l in open(bat_path, encoding="utf-8"):
                if not l.strip():
                    continue
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
                else:
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


if __name__ == "__main__":
    main()
