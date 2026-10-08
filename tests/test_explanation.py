"""生成解析的官方隔离、替换保护与审核审计，全部使用内存 SQLite。"""

from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine, event, func, inspect, select
from sqlalchemy.orm import Session

from examdata.core.models import (
    Base,
    Board,
    Document,
    GeneratedExplanation,
    MarkScheme,
    MarkSchemeEntry,
    OfficialAnswer,
    Paper,
    Qualification,
    Question,
    QuestionTaxonomy,
    ReviewTask,
    Subject,
    TaxonomyNode,
)
from examdata.intelligence import (
    EXPLANATION_PROVIDER,
    generate_explanations,
    generate_for_question,
    review_explanation,
)
from examdata.intelligence.explanation import PROMPT_VERSION


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    try:
        with Session(engine, expire_on_commit=False) as db:
            board = Board(key="synthetic", name="Synthetic Board")
            db.add(board)
            db.flush()
            qualification = Qualification(board_id=board.id, key="level", name="Level")
            db.add(qualification)
            db.flush()
            subject = Subject(qualification_id=qualification.id, code="MATH", title="Math")
            db.add(subject)
            db.flush()
            qp = Document(
                board_id=board.id,
                qualification_id=qualification.id,
                subject_id=subject.id,
                identity_key="synthetic-qp",
                doc_type="question_paper",
            )
            ms = Document(
                board_id=board.id,
                subject_id=subject.id,
                identity_key="synthetic-ms",
                doc_type="mark_scheme",
            )
            db.add_all([qp, ms])
            db.flush()
            paper = Paper(document_id=qp.id)
            scheme = MarkScheme(document_id=ms.id, matched_paper_document_id=qp.id)
            topic = TaxonomyNode(board_id=board.id, code="algebra", name="Algebra")
            db.add_all([paper, scheme, topic])
            db.flush()
            questions = [
                Question(
                    paper_id=paper.id,
                    number_label=str(index),
                    number_path=str(index),
                    display_order=index,
                    marks=3,
                    stem_text=f"Synthetic question {index}",
                )
                for index in range(1, 4)
            ]
            db.add_all(questions)
            db.flush()
            db.add_all([
                MarkSchemeEntry(
                    mark_scheme_id=scheme.id,
                    question_id=questions[0].id,
                    number_label="1",
                    number_path="1",
                    marks=3,
                    method_marks=1,
                    accuracy_marks=1,
                    independent_marks=1,
                    answer_text="x = 2",
                    acceptable_answers=["2"],
                    ecf=True,
                    guidance="Show the method.",
                ),
                OfficialAnswer(
                    question_id=questions[0].id,
                    source_document_id=ms.id,
                    source="mark_scheme",
                    content="x = 2",
                ),
                OfficialAnswer(
                    question_id=questions[2].id,
                    source_document_id=ms.id,
                    source="mark_scheme",
                    content="y = 4",
                ),
                QuestionTaxonomy(question_id=questions[0].id, node_id=topic.id),
            ])
            db.flush()
            generate_for_question(db, questions[0].id)
            db.commit()
            yield db
    finally:
        engine.dispose()


def _question_with_official(session) -> int:
    return session.scalar(select(MarkSchemeEntry.question_id).order_by(MarkSchemeEntry.id))


def _question_without_official(session) -> int:
    return session.scalar(select(Question.id).where(Question.number_path == "2"))


def _explanation(session) -> GeneratedExplanation:
    return session.scalar(select(GeneratedExplanation).order_by(GeneratedExplanation.id))


def _snapshot(explanation):
    return (
        explanation.id,
        explanation.approach,
        explanation.steps,
        explanation.final_answer,
        explanation.marking_points,
        explanation.common_errors,
        explanation.review_status,
        explanation.is_official,
        explanation.prompt_version,
    )


def test_generated_content_is_never_official(session):
    bad = session.scalar(
        select(func.count(GeneratedExplanation.id)).where(
            GeneratedExplanation.is_official.is_(True)
        )
    )
    assert bad == 0
    assert session.scalar(select(func.count(GeneratedExplanation.id))) > 0


def test_generator_marks_rows_non_official(session):
    obj = generate_for_question(session, _question_with_official(session), replace=True)
    assert obj.is_official is False
    assert obj.provider == EXPLANATION_PROVIDER


def test_generator_never_overwrites_official_answer(session):
    qid = _question_with_official(session)
    before = [
        (answer.id, answer.content)
        for answer in session.scalars(
            select(OfficialAnswer).where(OfficialAnswer.question_id == qid)
        )
    ]
    generate_for_question(session, qid, replace=True)
    session.commit()
    with Session(session.get_bind()) as persisted:
        after = [
            (answer.id, answer.content)
            for answer in persisted.scalars(
                select(OfficialAnswer).where(OfficialAnswer.question_id == qid)
            )
        ]
    assert before == after


def test_generated_rows_are_pending_by_default(session):
    obj = generate_for_question(session, _question_with_official(session), replace=True)
    assert obj.review_status == "pending"


def test_no_generation_without_official_basis(session):
    before = session.scalar(select(func.count(GeneratedExplanation.id)))
    result = generate_for_question(session, _question_without_official(session), replace=True)
    assert result is None
    assert session.scalar(select(func.count(GeneratedExplanation.id))) == before


def test_missing_question_returns_none(session):
    assert generate_for_question(session, 10**9) is None


def test_generate_all_reports_skips(session):
    stats = generate_explanations(session, limit=40)
    assert stats == {
        "scanned": 3,
        "generated": 1,
        "skipped_no_official": 1,
        "skipped_existing": 1,
    }


def test_explanation_has_structure(session):
    row = _explanation(session)
    assert row.approach
    assert "Algebra" in row.approach
    assert isinstance(row.steps, list) and row.steps
    assert isinstance(row.marking_points, list) and row.marking_points
    assert isinstance(row.common_errors, list) and row.common_errors


def test_explanation_is_reproducible(session):
    qid = _question_with_official(session)
    first = generate_for_question(session, qid, replace=True)
    snapshot = (first.approach, list(first.steps), list(first.marking_points))
    second = generate_for_question(session, qid, replace=True)
    assert snapshot == (second.approach, second.steps, second.marking_points)


def test_marking_points_come_from_official_marks(session):
    row = _explanation(session)
    assert {point["kind"] for point in row.marking_points} == {
        "method", "accuracy", "independent"
    }
    assert sum(point["marks"] for point in row.marking_points) == 3


def test_provider_and_model_are_honest(session):
    row = _explanation(session)
    assert row.provider == "rule-based"
    assert row.model is None
    assert row.prompt_version == PROMPT_VERSION


def test_review_transitions_and_stays_non_official(session):
    row = _explanation(session)
    result = review_explanation(session, row.id, status="approved", author="tester")
    assert result == {"id": row.id, "review_status": "approved", "reviewed_by": "tester"}
    session.commit()
    with Session(session.get_bind()) as persisted:
        assert persisted.get(GeneratedExplanation, row.id).is_official is False


def test_review_rejects_invalid_status(session):
    row = _explanation(session)
    with pytest.raises(ValueError, match="status"):
        review_explanation(session, row.id, status="looks-good", author="tester")
    assert row.review_status == "pending"
    assert session.scalar(select(func.count(ReviewTask.id))) == 0


def test_review_unknown_id_raises(session):
    with pytest.raises(ValueError, match="不存在"):
        review_explanation(session, 10**9, status="approved", author="tester")
    assert session.scalar(select(func.count(ReviewTask.id))) == 0


@pytest.mark.parametrize("status", ["approved", "rejected"])
def test_replace_preserves_legacy_reviewed_explanations(session, status):
    row = _explanation(session)
    row.review_status = status
    row.approach = "Human-reviewed approach"
    snapshot = _snapshot(row)
    pending = GeneratedExplanation(
        question_id=row.question_id,
        provider=EXPLANATION_PROVIDER,
        prompt_version="obsolete-unreviewed",
    )
    other_provider = GeneratedExplanation(
        question_id=row.question_id,
        provider="another-provider",
        prompt_version="other-v1",
        approach="Other provider content",
    )
    session.add_all([pending, other_provider])
    session.flush()
    official = session.scalar(
        select(OfficialAnswer).where(OfficialAnswer.question_id == row.question_id)
    )
    official.content = "Changed official answer"

    result = generate_for_question(session, row.question_id, replace=True)

    assert result is row
    assert _snapshot(row) == snapshot
    assert inspect(pending).deleted
    assert session.get(GeneratedExplanation, other_provider.id) is other_provider
    session.commit()
    with Session(session.get_bind()) as persisted:
        assert _snapshot(persisted.get(GeneratedExplanation, row.id)) == snapshot
        assert persisted.get(GeneratedExplanation, other_provider.id).approach == "Other provider content"


def test_replace_retains_reviewed_previous_rule_version(session):
    row = _explanation(session)
    row.prompt_version = "rules-old"
    row.review_status = "approved"
    snapshot = _snapshot(row)

    result = generate_for_question(session, row.question_id, replace=True)

    assert result is not row
    assert result.prompt_version == PROMPT_VERSION
    assert result.review_status == "pending"
    assert _snapshot(row) == snapshot
    assert session.get(GeneratedExplanation, row.id) is row
    assert session.scalar(select(func.count(GeneratedExplanation.id))) == 2


def test_replace_preserves_pending_with_review_history(session):
    row = _explanation(session)
    review_explanation(session, row.id, status="approved", author="first-reviewer")
    review_explanation(session, row.id, status="pending", author="second-reviewer")
    row.approach = "Previously reviewed content awaiting another review"
    snapshot = _snapshot(row)
    session.commit()
    session.expire_all()

    result = generate_for_question(session, row.question_id, replace=True)

    assert result is row
    assert _snapshot(result) == snapshot
    assert session.scalar(select(func.count(ReviewTask.id))) == 2


def test_replace_rebuilds_unreviewed_pending_only(session):
    row = _explanation(session)
    entry = session.scalar(
        select(MarkSchemeEntry).where(MarkSchemeEntry.question_id == row.question_id)
    )
    official = session.scalar(
        select(OfficialAnswer).where(OfficialAnswer.question_id == row.question_id)
    )
    entry.answer_text = "x = 3"
    official.content = "x = 3"
    unrelated_qid = session.scalar(select(Question.id).where(Question.number_path == "3"))
    unrelated = generate_for_question(session, unrelated_qid)
    unrelated_snapshot = _snapshot(unrelated)

    result = generate_for_question(session, row.question_id, replace=True)

    assert result is not row
    assert inspect(row).deleted
    assert result.final_answer == "x = 3"
    assert result.review_status == "pending"
    assert _snapshot(unrelated) == unrelated_snapshot
    assert session.scalar(select(func.count(ReviewTask.id))) == 0


def test_existing_explanation_is_idempotent_without_replace(session):
    row = _explanation(session)
    row.approach = "Existing generated content"
    snapshot = _snapshot(row)
    assert generate_for_question(session, row.question_id) is row
    assert _snapshot(row) == snapshot


def test_generate_all_replace_counts_protected_as_existing(session):
    row = _explanation(session)
    review_explanation(session, row.id, status="approved", author="reviewer")
    unrelated_qid = session.scalar(select(Question.id).where(Question.number_path == "3"))
    pending = generate_for_question(session, unrelated_qid)

    stats = generate_explanations(session, replace=True)

    assert stats == {
        "scanned": 3,
        "generated": 1,
        "skipped_no_official": 1,
        "skipped_existing": 1,
    }
    assert session.get(GeneratedExplanation, row.id) is row
    assert row.review_status == "approved"
    assert inspect(pending).deleted


@pytest.mark.parametrize("author", ["", "   ", "\t\r\n", None])
def test_review_rejects_empty_author_without_changes(session, author):
    row = _explanation(session)
    snapshot = _snapshot(row)
    with pytest.raises(ValueError, match="author"):
        review_explanation(session, row.id, status="approved", author=author)
    assert _snapshot(row) == snapshot
    assert session.scalar(select(func.count(ReviewTask.id))) == 0


def test_review_persists_author_and_status_audit(session):
    row = _explanation(session)
    result = review_explanation(session, row.id, status="approved", author="  reviewer  ")
    assert result == {"id": row.id, "review_status": "approved", "reviewed_by": "reviewer"}
    session.commit()

    with Session(session.get_bind()) as persisted:
        reviewed = persisted.get(GeneratedExplanation, row.id)
        task = persisted.scalar(select(ReviewTask))
        assert reviewed.review_status == "approved"
        assert task.target_type == "generated_explanation"
        assert task.target_id == reviewed.id
        assert task.reason == "explanation_review"
        assert task.status == "done"
        assert task.assignee == "reviewer"
        assert task.created_at is not None and task.updated_at is not None
        assert json.loads(task.resolution) == {
            "previous_status": "pending", "review_status": "approved"
        }


def test_each_review_keeps_its_own_audit_record(session):
    row = _explanation(session)
    for status, author in [("approved", "alice"), ("rejected", "bob"), ("pending", "carol")]:
        review_explanation(session, row.id, status=status, author=author)
    session.commit()

    with Session(session.get_bind()) as persisted:
        tasks = list(persisted.scalars(select(ReviewTask).order_by(ReviewTask.id)))
        assert [task.assignee for task in tasks] == ["alice", "bob", "carol"]
        assert [json.loads(task.resolution) for task in tasks] == [
            {"previous_status": "pending", "review_status": "approved"},
            {"previous_status": "approved", "review_status": "rejected"},
            {"previous_status": "rejected", "review_status": "pending"},
        ]
        assert {task.target_id for task in tasks} == {row.id}
        assert {task.status for task in tasks} == {"done"}
        assert persisted.get(GeneratedExplanation, row.id).review_status == "pending"


def test_review_and_audit_rollback_together(session):
    row = _explanation(session)
    review_explanation(session, row.id, status="approved", author="reviewer")
    assert session.scalar(select(func.count(ReviewTask.id))) == 1
    session.rollback()

    with Session(session.get_bind()) as persisted:
        assert persisted.get(GeneratedExplanation, row.id).review_status == "pending"
        assert persisted.scalar(select(func.count(ReviewTask.id))) == 0
