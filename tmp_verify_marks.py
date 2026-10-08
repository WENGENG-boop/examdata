"""对照 PDF 全文验证 june 2024 biology 6 卷的分值解析（一次性脚本）。"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import pymupdf
from sqlalchemy import select

from examdata.core.config import get_settings
from examdata.core.db import get_session_factory
from examdata.core.models import (
    Artifact,
    Document,
    DocumentRevision,
    Paper,
    Question,
    Subject,
)
from examdata.core.storage import ContentAddressedStore


def main() -> None:
    settings = get_settings()
    session = get_session_factory()()
    try:
        subject = session.scalar(select(Subject).where(Subject.code == "ial18-biology"))
        rows = session.execute(
            select(Paper, Document)
            .join(Document, Paper.document_id == Document.id)
            .where(Document.subject_id == subject.id)
            .order_by(Paper.paper_no)
        ).all()
        print(f"subject={subject.id} papers={len(rows)}")
        store = ContentAddressedStore(settings.artifacts_dir)
        grand_ok = grand_total = 0
        for paper, doc in rows:
            rev = session.get(DocumentRevision, doc.current_revision_id)
            artifact = rev and session.get(Artifact, rev.artifact_id)
            path = store.path_for_key(artifact.storage_key) if artifact else None
            if path is None or not path.exists():
                print(f"paper {paper.id} {paper.paper_no}: artifact missing")
                continue
            with pymupdf.open(path) as pdf:
                full = "\n".join(page.get_text() for page in pdf)
            questions = session.scalars(
                select(Question)
                .where(Question.paper_id == paper.id)
                .order_by(Question.display_order)
            ).all()
            depth0 = [q for q in questions if q.depth == 0]
            subs = [q for q in questions if q.depth > 0]
            ok = 0
            for q in depth0:
                pattern = re.compile(
                    r"\(\s*Total for Question\s+"
                    + re.escape(q.number_path)
                    + r"\s*=\s*(\d+)\s*marks?\s*\)",
                    re.I,
                )
                match = pattern.search(full)
                expect = int(match.group(1)) if match else None
                if expect is not None and q.marks == expect:
                    ok += 1
                else:
                    print(
                        f"  MISMATCH paper {paper.id} q{q.number_path}: "
                        f"db={q.marks} pdf={expect}"
                    )
            sub_filled = sum(1 for q in subs if q.marks is not None)
            print(
                f"paper {paper.id} {paper.paper_no}: depth0 {ok}/{len(depth0)} ok, "
                f"marks_total={paper.marks_total}, subs {sub_filled}/{len(subs)} filled"
            )
            for q in subs:
                if q.marks is None:
                    snippet = (q.stem_text or "")[:60].replace("\n", " ")
                    print(f"    sub none: {q.number_path} :: {snippet}")
            grand_ok += ok
            grand_total += len(depth0)
        print(f"TOTAL depth0 marks ok {grand_ok}/{grand_total}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
