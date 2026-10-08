"""查清 biology report 的三个待查项（一次性脚本）。"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from sqlalchemy import func, select

from examdata.core.db import get_session_factory
from examdata.core.models import (
    Document,
    DocumentRevision,
    MarkScheme,
    ParseRun,
    Subject,
)


def main() -> None:
    session = get_session_factory()()
    try:
        sub = session.scalar(select(Subject).where(Subject.code == "ial18-biology"))
        print("subject id:", sub.id)

        print("=== failed parse_runs ===")
        rows = session.execute(
            select(ParseRun.id, ParseRun.error, ParseRun.started_at, ParseRun.finished_at,
                   Document.id, Document.doc_type, Document.paper_code, Document.year,
                   DocumentRevision.source_url)
            .join(DocumentRevision, ParseRun.document_revision_id == DocumentRevision.id)
            .join(Document, DocumentRevision.document_id == Document.id)
            .where(Document.subject_id == sub.id, ParseRun.status == "failed")
        ).all()
        for run_id, err, started, finished, doc_id, doc_type, paper_code, year, url in rows:
            print(f"run {run_id} doc {doc_id} {doc_type} {paper_code} {year}: {err}")
            print(f"   started={started} url={url}")

        print("=== all parse_runs for those docs (history) ===")
        doc_ids = [r[4] for r in rows]
        if doc_ids:
            hist = session.execute(
                select(ParseRun.id, ParseRun.status, ParseRun.document_revision_id,
                       Document.id, ParseRun.started_at)
                .join(DocumentRevision, ParseRun.document_revision_id == DocumentRevision.id)
                .join(Document, DocumentRevision.document_id == Document.id)
                .where(Document.id.in_(doc_ids))
                .order_by(Document.id, ParseRun.id)
            ).all()
            for run_id, status, rev_id, doc_id, started in hist:
                print(f"  doc {doc_id}: run {run_id} status={status} rev={rev_id} at {started}")

        print("=== mark schemes not matched ===")
        ms_rows = session.execute(
            select(MarkScheme.id, MarkScheme.document_id, Document.paper_code, Document.year,
                   Document.title)
            .join(Document, MarkScheme.document_id == Document.id)
            .where(Document.subject_id == sub.id, MarkScheme.matched_paper_document_id.is_(None))
        ).all()
        print(f"unmatched MS: {len(ms_rows)}")
        for ms_id, doc_id, paper_code, year, title in ms_rows:
            print(f"  ms {ms_id} doc {doc_id} {paper_code} {year} {title!r}")

        print("=== document counts ===")
        counts = session.execute(
            select(Document.doc_type,
                   func.count(),
                   func.count(Document.current_revision_id))
            .where(Document.subject_id == sub.id)
            .group_by(Document.doc_type)
        ).all()
        for doc_type, total, downloaded in counts:
            print(f"  {doc_type}: total={total} downloaded={downloaded}")

        print("=== matched MS but different subject? ===")
        # any MS matched to a paper of another subject (should not happen)
        cross = session.execute(
            select(func.count()).select_from(MarkScheme)
            .join(Document, MarkScheme.document_id == Document.id)
            .where(Document.subject_id == sub.id,
                   MarkScheme.matched_paper_document_id.isnot(None))
        ).scalar()
        print("matched MS count:", cross)
    finally:
        session.close()


if __name__ == "__main__":
    main()
