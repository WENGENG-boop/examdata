"""Dump all questions (with stems) of the papers containing pending low-conf items."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from examdata.core.db import get_session_factory, init_db  # noqa: E402
from examdata.core.models import Document, Paper, Question  # noqa: E402

PENDING = [68324, 68343, 68380, 68412, 68414, 68471, 68472, 68494, 68555, 68563, 68570]


def main() -> None:
    init_db()
    session: Session = get_session_factory()()
    papers = {}
    for qid in PENDING:
        q = session.get(Question, qid)
        if q:
            papers.setdefault(q.paper_id, []).append(qid)
    lines = []
    for pid, qids in papers.items():
        paper = session.get(Paper, pid)
        doc = session.get(Document, paper.document_id) if paper else None
        code = doc.paper_code if doc else "?"
        lines.append("#" * 100)
        lines.append(f"### paper_id={pid} code={code} (for qids {qids})")
        qs = list(
            session.scalars(
                select(Question).where(Question.paper_id == pid).order_by(Question.page_from, Question.id)
            )
        )
        for q in qs:
            stem = (q.stem_text or "").replace("\r", "").replace("\n", " ¶ ")
            if len(stem) > 700:
                stem = stem[:700] + " …[TRUNC]"
            lines.append(f"[q{q.id}] p{q.page_from} path={q.number_path} marks={q.marks} | {stem}")
    session.close()
    (ROOT / "tmp_r11_paper_dump.txt").write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {len(lines)} lines")


if __name__ == "__main__":
    main()
