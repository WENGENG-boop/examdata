"""6 个叶子 None：每个独立 (N) 行的上下文（一次性脚本）。"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from sqlalchemy import select

from examdata.core.db import get_session_factory
from examdata.core.models import Paper, Question

LINE = re.compile(r"^[ \t]*\((\d+)\)[ \t]*$", re.M)


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
            select(Question.id, Question.parent_id).where(
                Question.paper_id.in_([33, 31, 34, 35, 30, 32])
            )
        ).all()
        has_child = {parent for _, parent in all_q if parent}
        for q, paper_no in rows:
            if q.id in has_child:
                continue
            text = q.stem_text or ""
            print(f"=== {paper_no} {q.number_path} len={len(text)} ===")
            for m in LINE.finditer(text):
                start = max(0, m.start() - 70)
                end = min(len(text), m.end() + 70)
                ctx = text[start:end].replace("\n", "\\n")
                print(f"  hit ({m.group(1)}) at {m.start()}: ...{ctx}...")
    finally:
        session.close()


if __name__ == "__main__":
    main()
