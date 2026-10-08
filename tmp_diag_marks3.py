"""剩余 None 子题：叶子/父节点分类 + 全文样例（一次性脚本）。"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from sqlalchemy import select

from examdata.core.db import get_session_factory
from examdata.core.models import Paper, Question
from examdata.edexcel_papers import pipeline as pipe


def main() -> None:
    session = get_session_factory()()
    try:
        rows = session.execute(
            select(Question, Paper.paper_no)
            .join(Paper, Question.paper_id == Paper.id)
            .where(Paper.id.in_([33, 31, 34, 35, 30, 32]), Question.depth > 0, Question.marks.is_(None))
            .order_by(Question.paper_id, Question.display_order)
        ).all()
        all_q = session.execute(
            select(Question.id, Question.paper_id, Question.number_path, Question.parent_id)
            .where(Question.paper_id.in_([33, 31, 34, 35, 30, 32]))
        ).all()
        has_child = {parent for _, _, _, parent in all_q if parent}
        by_id = {qid: path for qid, _, path, _ in all_q}
        leaf_none, parent_none = [], []
        for q, paper_no in rows:
            if q.id in has_child:
                parent_none.append((paper_no, q.number_path))
            else:
                leaf_none.append((paper_no, q.number_path, q))
        print(f"None sub-parts: leaves={len(leaf_none)} parents={len(parent_none)}")
        print("parents:", [f"{p} {n}" for p, n in parent_none])
        print("=== leaf full texts (first 3 + interesting) ===")
        for paper_no, path, q in leaf_none:
            if path in {"8(a)", "1(b)", "4(a)", "3(a)", "2(d)", "1(a)", "3(b)"}:
                text = (q.stem_text or "").replace("\n", "\\n")
                print(f"--- {paper_no} {path} ---")
                print(text[:500])
    finally:
        session.close()


if __name__ == "__main__":
    main()
