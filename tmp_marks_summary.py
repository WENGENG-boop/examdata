"""汇总 6 卷分值覆盖率，确认剩余 None 全是父节点（一次性脚本）。"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from sqlalchemy import select

from examdata.core.db import get_session_factory
from examdata.core.models import Document, Paper, Question, Subject


def main() -> None:
    session = get_session_factory()()
    try:
        sub = session.scalar(select(Subject).where(Subject.code == "ial18-biology"))
        PAPERS = session.scalars(
            select(Paper.id)
            .join(Document, Paper.document_id == Document.id)
            .where(Document.subject_id == sub.id)
        ).all()
        all_q = session.execute(
            select(
                Question.id,
                Question.paper_id,
                Question.number_path,
                Question.parent_id,
                Question.depth,
                Question.marks,
            ).where(Question.paper_id.in_(PAPERS))
        ).all()
        has_child = {parent for _, _, _, parent, _, _ in all_q if parent}
        total_sub = sum(1 for row in all_q if row[4] > 0)
        filled_sub = sum(1 for row in all_q if row[4] > 0 and row[5] is not None)
        none_leaf = [
            (row[1], row[2]) for row in all_q if row[4] > 0 and row[5] is None and row[0] not in has_child
        ]
        none_parent = sum(
            1 for row in all_q if row[4] > 0 and row[5] is None and row[0] in has_child
        )
        depth0 = [row for row in all_q if row[4] == 0]
        depth0_filled = sum(1 for row in depth0 if row[5] is not None)
        print(f"sub-parts: {filled_sub}/{total_sub} filled; None leaves={len(none_leaf)} parents={none_parent}")
        print("none leaves:", none_leaf)
        print(f"top-level: {depth0_filled}/{len(depth0)} filled")
    finally:
        session.close()


if __name__ == "__main__":
    main()
