"""r8 fixunits: repair 26 cross-unit mis-tagged rows on 6 papers
(doc 1752/1754 accounting, doc 3106/3122/3123/3143 law).

Delete 26 wrong rows (wrong spec-unit), insert 17 replacement rows as
ai-review (all have manual precedent or semantic adjudication).

Usage: ./.venv/Scripts/python.exe -X utf8 tmp_r8_fixunits.py [--write]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from examdata.core.db import (  # noqa: E402
    enable_immediate_writes,
    get_session_factory,
    init_db,
)
from examdata.core.models import QuestionTaxonomy, TaxonomyNode  # noqa: E402
from sqlalchemy import select  # noqa: E402

# (row_id, question_id, expected node code) -- 26 rows to delete
DELETES = [
    # doc1752 (truth WAC11) -- 15 rows
    (332513, 68429, "WAC01-1.3.3.7"),
    (332515, 68430, "WAC12-2.1.1"),
    (332524, 68437, "WAC01-1.3.3.2"),
    (332525, 68438, "WAC01-1.3.3.2"),
    (332529, 68440, "WAC01-1.3.1.5"),
    (332530, 68441, "WAC12-2.7.1"),
    (332531, 68442, "WAC12-2.7.1"),
    (332533, 68443, "WAC12-2.7.1"),
    (332534, 68444, "WAC12-2.7.1"),
    (332535, 68445, "WAC02-2.3.1.2"),
    (332536, 68445, "WAC01-1.3.4.3"),
    (332537, 68446, "WAC01-1.3.4.3"),
    (332539, 68448, "WAC01-1.3.4.3"),
    (332540, 68449, "WAC12-2.7.1"),
    (332541, 68450, "WAC12-2.7.1"),
    # doc1754 (truth WAC01) -- 6 rows
    (332545, 68453, "WAC11-1.3.1"),
    (332546, 68454, "WAC11-1.1.7"),
    (332548, 68455, "WAC11-1.5.1"),
    (332550, 68456, "WAC11-1.6.2"),
    (332551, 68457, "WAC11-1.5.1"),
    (332552, 68458, "WAC12-2.1.12"),
    # law -- 5 rows
    (332626, 68517, "YLA1-02-2.2.10"),
    (332629, 68520, "YLA0-P1-1.3.3"),
    (332630, 68520, "YLA1-02-2.3.4"),
    (332635, 68525, "YLA1-01-1.2.8"),
    (332643, 68531, "YLA0-P1-1.3.3"),
]

# (question_id, node code, reason) -- 17 replacement rows
INSERTS = [
    (68437, "WAC11-1.1.15", "depreciation charge calc; precedent q46090"),
    (68438, "WAC11-1.1.16", "depreciation ledger accounts; precedent q46091"),
    (68441, "WAC11-1.4.7", "semi-fixed/semi-variable cost behaviour"),
    (68443, "WAC11-1.4.7", "semi-fixed/semi-variable cost behaviour"),
    (68444, "WAC11-1.4.7", "semi-fixed/semi-variable cost behaviour"),
    (68445, "WAC11-1.4.8", "allocated vs apportioned overheads; q46079/q47322"),
    (68446, "WAC11-1.4.8", "overhead apportionment + recovery umbrella"),
    (68448, "WAC11-1.4.10", "overhead recovery rate; q46409/q47327"),
    (68449, "WAC11-1.4.13", "selling price of batch/order; q48708"),
    (68450, "WAC11-1.4.13", "selling price of batch/order; q48708"),
    (68453, "WAC01-1.3.2.3", "revised profit effect of errors"),
    (68456, "WAC01-1.3.5.2", "non-financial factors, business purchase (social acctg)"),
    (68457, "WAC01-1.3.5.1", "ratios + goodwill"),
    (68458, "WAC01-1.3.5.1", "evaluate business purchase"),
    (68517, "YLA1-01-1.1.6", "criminal sanctions; q56386/q56494"),
    (68520, "YLA1-01-1.2.9", "parliamentary sovereignty EU; q56382"),
    (68525, "YLA1-02-2.3.10", "remedies for the individual"),
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    enable_immediate_writes()
    init_db()
    session = get_session_factory()()
    try:
        # resolve node ids by code
        node_by_code = {
            r.code: r
            for r in session.scalars(select(TaxonomyNode))
        }
        code_by_id = {r.id: r.code for r in node_by_code.values()}
        missing = [
            c for c in ({c for _, _, c in DELETES} | {c for _, c, _ in INSERTS})
            if c not in node_by_code
        ]
        if missing:
            print(f"ABORT: node codes missing: {missing}")
            return

        # load all rows in scope
        qids = sorted({q for _, q, _ in DELETES} | {q for q, _, _ in INSERTS})
        rows = session.scalars(
            select(QuestionTaxonomy).where(QuestionTaxonomy.question_id.in_(qids))
        ).all()
        by_id = {r.id: r for r in rows}

        # verify deletes
        errors = []
        for row_id, qid, code in DELETES:
            r = by_id.get(row_id)
            if r is None:
                errors.append(f"row {row_id} not found")
                continue
            if r.question_id != qid:
                errors.append(f"row {row_id} qid={r.question_id} != {qid}")
                continue
            actual = code_by_id.get(r.node_id, f"?{r.node_id}")
            if actual != code:
                errors.append(f"row {row_id} node={actual} != {code}")
        # verify inserts don't already exist
        existing = {(r.question_id, r.node_id) for r in rows}
        for qid, code, _ in INSERTS:
            nid = node_by_code[code].id
            if (qid, nid) in existing:
                errors.append(f"insert already exists: q{qid} {code}")

        if errors:
            print("ABORT:")
            for e in errors:
                print(f"  {e}")
            return

        print(f"plan OK: {len(DELETES)} deletes, {len(INSERTS)} inserts")
        for row_id, qid, code in DELETES:
            print(f"  DEL row{row_id} q{qid} {code}")
        for qid, code, reason in INSERTS:
            print(f"  INS q{qid} {code}  ({reason})")

        if not args.write:
            print("[dry] no changes written")
            return

        # perform
        evidence = []
        for row_id, qid, code in DELETES:
            r = by_id[row_id]
            session.delete(r)
            evidence.append({"action": "delete", "row_id": row_id,
                             "question_id": qid, "code": code})
        session.flush()
        for qid, code, reason in INSERTS:
            row = QuestionTaxonomy(
                question_id=qid,
                node_id=node_by_code[code].id,
                source="ai-review",
                confidence=1.0,
                assigned_by="ai-review-v1",
                reviewed=True,
            )
            session.add(row)
            session.flush()
            evidence.append({"action": "insert", "row_id": row.id,
                             "question_id": qid, "code": code, "reason": reason})
        session.commit()
        out = ROOT / "tmp_r8_fixunits_applied.jsonl"
        with out.open("w", encoding="utf-8") as fh:
            for e in evidence:
                fh.write(json.dumps(e, ensure_ascii=False) + "\n")
        print(f"WROTE {len(evidence)} actions -> {out.name}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
