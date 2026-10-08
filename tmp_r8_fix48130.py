"""Fix mis-assigned taxonomy tag for question 48130 (doc 1736, WAC02 unit).

Current row: node_id=257 'Capital structure' (WRONG).
Target row : node_id=260 'Investment evaluation' (dividend cover belongs here).

Delete old row, insert new ai-review row, both confidence=1.0, reviewed=1.
Usage: ./.venv/Scripts/python.exe -X utf8 tmp_r8_fix48130.py [--write]
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

QID = 48130
OLD_NODE = 257
NEW_NODE = 260
OLD_ROW_ID = 305515


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    enable_immediate_writes()
    init_db()
    session = get_session_factory()()
    try:
        rows = session.scalars(
            select(QuestionTaxonomy).where(QuestionTaxonomy.question_id == QID)
        ).all()
        print(f"existing rows for q{QID}: {len(rows)}")
        for r in rows:
            print(
                f"  id={r.id} node={r.node_id} source={r.source} "
                f"conf={r.confidence} reviewed={r.reviewed} by={r.assigned_by}"
            )

        old = [r for r in rows if r.node_id == OLD_NODE]
        have_new = [r for r in rows if r.node_id == NEW_NODE]
        if len(rows) != 1 or not old:
            print(f"ABORT: expected exactly 1 row at node {OLD_NODE}, got {len(rows)}")
            return
        if have_new:
            print(f"ABORT: node {NEW_NODE} row already exists")
            return

        if not args.write:
            print(f"[dry] would delete row id={old[0].id} and insert node={NEW_NODE}")
            return

        session.delete(old[0])
        session.flush()
        new_row = QuestionTaxonomy(
            question_id=QID,
            node_id=NEW_NODE,
            source="ai-review",
            confidence=1.0,
            assigned_by="ai-review-v1",
            reviewed=True,
        )
        session.add(new_row)
        session.commit()
        print(f"WROTE: deleted {old[0].id}, inserted new row id={new_row.id} node={NEW_NODE}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
