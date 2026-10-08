"""r8: assign ai-review taxonomy rows for the 6 new questions BM25 could not tag.

Judgments (based on sibling/family convention + cross-paper precedent):
  68248 [2(b)(i)] wbi13  "Complete the key by naming the molecules"
      -> WBI13-implementation (3263): family 2(b)/2(b)(iii) implementation;
         historical label/diagram questions in wbi13 all implementation.
  68249 [2(b)(ii)] wbi13 "Complete diagram A by labelling inside/outside"
      -> WBI13-implementation (3263): same family.
  68401 [4(e)] wac11  "Evaluate the advice given by the friend to Bitani"
      (advice: only profitability matters) -> WAC11-1.5.2 (168):
      precedent q46068 "Evaluate the use of profitability ratios as the only way...".
  68404 [3(d)(i)] wac12 "one wind turbine" (NPV 13m) -> WAC12-2.6.1 (211):
      parent 68403 already WAC12-2.6.1; all NPV questions in wac12 are 2.6.1.
  68405 [3(d)(ii)] wac12 "the 40 wind turbines." (NPV 1m) -> WAC12-2.6.1 (211).
  68416 [3(d)] wac11  "Evaluate this advice" (ICT removes all errors)
      -> WAC11-1.1.7 (105): precedent q48836 "Evaluate the friend's advice
         that the use of ICT..."; MS is all ICT points.

Usage: ./.venv/Scripts/python.exe -X utf8 tmp_r8_tag6.py [--write]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from examdata.core.db import (  # noqa: E402
    enable_immediate_writes,
    get_session_factory,
    init_db,
)
from examdata.core.models import QuestionTaxonomy  # noqa: E402
from sqlalchemy import select  # noqa: E402

ASSIGNMENTS = [
    (68248, 3263, "WBI13-implementation"),
    (68249, 3263, "WBI13-implementation"),
    (68401, 168, "WAC11-1.5.2"),
    (68404, 211, "WAC12-2.6.1"),
    (68405, 211, "WAC12-2.6.1"),
    (68416, 105, "WAC11-1.1.7"),
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    enable_immediate_writes()
    init_db()
    session = get_session_factory()()
    try:
        for qid, node_id, code in ASSIGNMENTS:
            rows = session.scalars(
                select(QuestionTaxonomy).where(QuestionTaxonomy.question_id == qid)
            ).all()
            if rows:
                print(f"SKIP q{qid}: already has {len(rows)} row(s)")
                continue
            print(f"{'WROTE' if args.write else '[dry]'} q{qid} -> {code} (node {node_id})")
            if args.write:
                session.add(
                    QuestionTaxonomy(
                        question_id=qid,
                        node_id=node_id,
                        source="ai-review",
                        confidence=1.0,
                        assigned_by="ai-review-v1",
                        reviewed=True,
                    )
                )
        if args.write:
            session.commit()
            print("committed")
    finally:
        session.close()


if __name__ == "__main__":
    main()
