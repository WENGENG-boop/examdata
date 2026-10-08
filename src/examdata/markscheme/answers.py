"""Rebuild only official answers derived from the selected current mark schemes."""
from sqlalchemy import select
from ..core.models import Document, MarkScheme, MarkSchemeEntry, OfficialAnswer, ParseRun


def rebuild_official_answers(session, *, document_ids):
    if not document_ids:
        return 0
    schemes = list(session.scalars(select(MarkScheme).join(ParseRun, ParseRun.id == MarkScheme.parse_run_id)
        .join(Document, Document.id == MarkScheme.document_id).where(
            Document.id.in_(document_ids), ParseRun.document_revision_id == Document.current_revision_id,
            ParseRun.status == "completed")))
    source_ids = [ms.document_id for ms in schemes]
    for answer in session.scalars(select(OfficialAnswer).where(
        OfficialAnswer.source_document_id.in_(source_ids), OfficialAnswer.source == "mark_scheme"
    )):
        session.delete(answer)
    session.flush()
    written = 0
    for ms in schemes:
        for entry in session.scalars(select(MarkSchemeEntry).where(MarkSchemeEntry.mark_scheme_id == ms.id)):
            if entry.question_id is None or not entry.answer_text or not entry.answer_text.strip():
                continue
            session.add(OfficialAnswer(question_id=entry.question_id, source="mark_scheme",
                source_document_id=ms.document_id, content=entry.answer_text, is_official=True,
                attrs={"number_path": entry.number_path, "marks": entry.marks, "parse_run_id": ms.parse_run_id}))
            written += 1
    session.flush()
    return written
