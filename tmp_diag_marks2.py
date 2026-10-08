"""深挖 q1 失败原因 + 全部剩余 None 子题的文本形态（一次性脚本）。"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import pymupdf
from sqlalchemy import select

from examdata.core.config import get_settings
from examdata.core.db import get_session_factory
from examdata.core.models import Artifact, Document, DocumentRevision, Paper, Question
from examdata.core.storage import ContentAddressedStore
from examdata.edexcel_papers import pipeline as pipe


def artifact_path(session, store, doc):
    rev = session.get(DocumentRevision, doc.current_revision_id)
    artifact = session.get(Artifact, rev.artifact_id)
    return store.path_for_key(artifact.storage_key)


def main() -> None:
    settings = get_settings()
    session = get_session_factory()()
    store = ContentAddressedStore(settings.artifacts_dir)
    try:
        paper = session.get(Paper, 34)
        doc = session.get(Document, paper.document_id)
        path = artifact_path(session, store, doc)
        q1 = session.scalar(
            select(Question).where(Question.paper_id == 34, Question.number_path == "1")
        )
        regions = (q1.attrs or {}).get("regions") or []
        print("q1 regions:", [(r.get("page"), [round(v, 1) for v in r.get("bbox", [])]) for r in regions])
        with pymupdf.open(path) as pdf:
            got = pipe._total_marks_from_pages(pdf, regions, "1")
            print("_total_marks_from_pages ->", got)
            print("page count:", len(pdf))
            if regions:
                last = regions[-1]
                text = pdf[last["page"] - 1].get_text()
                print("last page has marker:", "Total for Question 1" in text)

        # all remaining None sub-parts, across all 6 papers
        print("=== remaining None sub-parts ===")
        rows = session.execute(
            select(Question, Paper.paper_no)
            .join(Paper, Question.paper_id == Paper.id)
            .where(Paper.id.in_([33, 31, 34, 35, 30, 32]), Question.depth > 0, Question.marks.is_(None))
            .order_by(Question.paper_id, Question.display_order)
        ).all()
        for q, paper_no in rows:
            text = q.stem_text or ""
            first = next((ln for ln in text.splitlines() if ln.strip()), "")
            hits = pipe._MARK_LINE.findall(pipe._TOTAL_MARKER.sub(" ", text))
            print(
                f"{paper_no} {q.number_path}: firstline={first[:80]!r} "
                f"standalone_hits={len(hits)} last40={text[-40:]!r}"
            )
    finally:
        session.close()


if __name__ == "__main__":
    main()
