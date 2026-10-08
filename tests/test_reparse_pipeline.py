from __future__ import annotations

from hashlib import sha256
import os
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from examdata.core.config import Settings
from examdata.core.models import Artifact, Base, Board, Document, DocumentRevision, Paper, ParseRun
from examdata.governance.reparse import reparse_documents
from examdata.parsing.pipeline import ParsePipeline


@pytest.fixture(autouse=True)
def private_settings(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    monkeypatch.setattr("examdata.core.storage.get_settings", lambda: settings)
    monkeypatch.setattr("examdata.parsing.pipeline.get_settings", lambda: settings)
    return settings


@pytest.fixture
def db() -> Session:
    pg_url = os.environ.get("EXAMDATA_TEST_POSTGRES_URL")
    schema = "examdata_test_" + uuid.uuid4().hex
    admin = None
    if pg_url:
        admin = create_engine(pg_url, isolation_level="AUTOCOMMIT")
        with admin.connect() as conn:
            conn.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
        engine = create_engine(pg_url, connect_args={"options": "-csearch_path=" + schema})
    else:
        engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def on_connect(connection, record):
        if not pg_url:
            connection.isolation_level = None
            connection.execute("PRAGMA foreign_keys=ON")

    @event.listens_for(engine, "begin")
    def on_begin(connection):
        if not pg_url:
            connection.exec_driver_sql("BEGIN")

    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        session.add(Board(id=1, key="test", name="Synthetic board"))
        session.commit()
        yield session
    engine.dispose()
    if admin:
        with admin.connect() as conn:
            conn.exec_driver_sql(f'DROP SCHEMA "{schema}" CASCADE')
        admin.dispose()


def _artifact(tmp_path: Path, key: str = "aa/bb/file.pdf") -> Artifact:
    path = tmp_path / "artifacts" / key
    path.parent.mkdir(parents=True, exist_ok=True)
    data = key.encode()
    path.write_bytes(data)
    return Artifact(
        sha256=sha256(data).hexdigest(),
        size_bytes=len(data),
        storage_key=key,
        source_url="https://example.invalid/local.pdf",
    )


def _document(session: Session, tmp_path: Path, identity: str) -> tuple[Document, DocumentRevision]:
    artifact = _artifact(tmp_path, f"{identity}/artifact.pdf")
    session.add(artifact)
    session.flush()
    doc = Document(identity_key=identity, board_id=1, doc_type="other", status="ok")
    session.add(doc)
    session.flush()
    revision = DocumentRevision(
        document_id=doc.id,
        artifact_id=artifact.id,
        revision_no=1,
        parse_status="pending",
        status="active",
    )
    session.add(revision)
    session.flush()
    doc.current_revision_id = revision.id
    session.flush()
    return doc, revision


def _settings(tmp_path: Path) -> Settings:
    return Settings(data_dir=tmp_path, database_url="sqlite:///:memory:")


def test_pipeline_document_scope_and_stats_are_isolated(db, tmp_path, monkeypatch):
    first, first_rev = _document(db, tmp_path, "first")
    second, second_rev = _document(db, tmp_path, "second")

    def fake_parse(self, revision):
        self.stats.revisions += 1
        revision.parse_status = "parsed"
        run = ParseRun(
            document_revision_id=revision.id,
            parser_version=self.settings.parser_version,
            status="completed",
            stats={"questions": 0, "entries": 0},
        )
        self.session.add(run)
        self.session.flush()

    monkeypatch.setattr(ParsePipeline, "parse_revision", fake_parse)
    pipe = ParsePipeline(db, settings=_settings(tmp_path))
    stats = pipe.run(document_id=first.id)

    assert stats.revisions == 1
    assert first_rev.parse_status == "parsed"
    assert second_rev.parse_status == "pending"
    assert pipe.store.root == tmp_path / "artifacts"

    second_stats = pipe.run()
    assert second_stats.revisions == 1
    assert second_rev.parse_status == "parsed"

    assert db.scalar(select(ParseRun.document_revision_id).where(ParseRun.document_revision_id == first_rev.id)) == first_rev.id


def test_pipeline_failed_revision_isolated_and_retry_is_explicit(db, tmp_path, monkeypatch):
    first, first_rev = _document(db, tmp_path, "first-failure")
    second, second_rev = _document(db, tmp_path, "second-failure")

    def failing_parse(self, revision):
        self.stats.revisions += 1
        self.session.add(ParseRun(
            document_revision_id=revision.id,
            parser_version=self.settings.parser_version,
            status="running",
        ))
        self.session.flush()
        raise ValueError("synthetic parser failure")

    monkeypatch.setattr(ParsePipeline, "parse_revision", failing_parse)
    stats = ParsePipeline(db, settings=_settings(tmp_path)).run(document_id=first.id)

    assert stats.failed == 1
    assert first_rev.parse_status == "failed"
    assert "synthetic parser failure" in (first_rev.parse_error or "")
    assert second_rev.parse_status == "pending"
    failure = db.scalar(select(ParseRun).where(ParseRun.document_revision_id == first_rev.id))
    assert failure.status == "failed"
    assert "synthetic parser failure" in failure.params["error"]

    retry_stats = ParsePipeline(db, settings=_settings(tmp_path)).run(
        document_id=first.id, retry_failed=True
    )
    assert retry_stats.failed == 1
    assert first_rev.parse_status == "failed"


def test_reparse_empty_and_target_validation_do_not_touch_database(db, tmp_path):
    result = reparse_documents(db, document_ids=[])
    assert result["documents"] == 0
    assert result["parse_stats"]["revisions"] == 0

    with pytest.raises(ValueError, match="document 不存在"):
        reparse_documents(db, document_ids=[999])


def test_reparse_scopes_current_revision_and_rolls_back_failed_rebuild(db, tmp_path, monkeypatch):
    first, first_rev = _document(db, tmp_path, "reparse-first")
    second, second_rev = _document(db, tmp_path, "reparse-second")
    first_rev.parse_status = "parsed"
    second_rev.parse_status = "pending"
    paper = Paper(document_id=first.id, paper_no="1")
    db.add(paper)
    db.commit()

    def failing_parse(self, revision):
        raise ValueError("reparse failure")

    monkeypatch.setattr(ParsePipeline, "parse_revision", failing_parse)
    result = reparse_documents(db, document_ids=[first.id], settings=_settings(tmp_path))
    assert result["aborted"] is True
    assert "重新解析失败" in result["reason"]
    assert db.scalar(select(ParseRun.status)) == "failed"
    db.commit()

    db.expire_all()
    assert db.get(Paper, paper.id) is not None
    assert db.get(DocumentRevision, first_rev.id).parse_status == "parsed"
    assert db.get(DocumentRevision, second_rev.id).parse_status == "pending"


@pytest.fixture
def synthetic_parser(monkeypatch):
    from types import SimpleNamespace

    from examdata.parsing.segment import AssetRef, QuestionNode, QuestionTree

    def tree(pdf, **kwargs):
        return QuestionTree(roots=[
            QuestionNode(
                label=str(number), number_path=str(number), depth=0,
                kind="question", order=number, marks=3,
                text_parts=["Calculate the value of this expression."],
                assets=[AssetRef(page=1, bbox=(10, 10, 20, 20), width=1, height=1,
                                 ext="png", data=b"synthetic-image", mime="image/png")],
            ) for number in (1, 2)
        ])

    monkeypatch.setattr("examdata.parsing.pipeline.load_pdf", lambda path: SimpleNamespace(pages=[1]))
    monkeypatch.setattr("examdata.parsing.pipeline.extract_paper_metadata", lambda pdf: SimpleNamespace(
        total_marks=6, subject_code=None, year=None, paper_number=None, duration_minutes=None,
    ))
    monkeypatch.setattr("examdata.parsing.pipeline.build_question_tree", tree)
    monkeypatch.setattr(ParsePipeline, "_record_classification_finding", lambda *args: None)


def _old_question(db, doc, revision):
    from examdata.core.models import Question

    run = ParseRun(document_revision_id=revision.id, parser_version="old", status="completed")
    db.add(run)
    db.flush()
    paper = Paper(document_id=doc.id, parse_run_id=run.id)
    db.add(paper)
    db.flush()
    question = Question(paper_id=paper.id, number_label="1", number_path="1", display_order=1,
                        parse_run_id=run.id, marks=3, stem_text="Old expression.")
    db.add(question)
    db.flush()
    return question, run


@pytest.mark.parametrize("keep_history", [True, False])
def test_reparse_current_revision_and_scoped_derived_and_relink(
    db, tmp_path, synthetic_parser, keep_history
):
    from examdata.core.models import (
        Asset, Difficulty, Formula, GeneratedExplanation, MarkScheme, MarkSchemeEntry,
        OfficialAnswer, Question, QuestionSimilarity, QuestionTaxonomy, ReviewTask,
        TaxonomyNode, ValidationFinding,
    )

    target, old_rev = _document(db, tmp_path, "target")
    target.doc_type = "question_paper"
    target.paper_code = "11"
    old_rev.status = "superseded"
    old_rev.parse_status = "parsed"
    current = DocumentRevision(document_id=target.id, artifact_id=old_rev.artifact_id,
                               revision_no=2, parse_status="parsed")
    db.add(current)
    db.flush()
    target.current_revision_id = current.id
    question, old_run = _old_question(db, target, old_rev)
    old_run_id = old_run.id
    db.add(Formula(question_id=question.id, latex="x+y"))
    review = ReviewTask(target_type="document", target_id=target.id, reason="old_finding",
                        status="done", resolution="reviewed", parse_run_id=old_run.id)
    db.add(review)
    db.add(ValidationFinding(subject_type="document", subject_id=target.id,
                             rule_code="old_finding", severity="warning", message="old",
                             parse_run_id=old_run.id))

    other, pending = _document(db, tmp_path, "other")
    other_question, other_run = _old_question(db, other, pending)
    third, third_rev = _document(db, tmp_path, "third")
    third_question, _ = _old_question(db, third, third_rev)
    third_rev.parse_status = "failed"
    third_rev.parse_error = "unrelated failure"
    node = TaxonomyNode(board_id=1, code="sentinel", name="Sentinel")
    db.add(node)
    db.flush()
    sentinels = [
        Difficulty(question_id=other_question.id, value=0.91, source="estimated"),
        QuestionTaxonomy(question_id=other_question.id, node_id=node.id, source="auto"),
        GeneratedExplanation(question_id=other_question.id, provider="rule-based",
                             prompt_version="old", review_status="approved", approach="Do not replace"),
        QuestionSimilarity(question_a_id=other_question.id, question_b_id=third_question.id,
                           method="tfidf-ngram-v1", score=0.99),
    ]
    db.add_all(sentinels)

    ms_doc, ms_rev = _document(db, tmp_path, "ms-target")
    ms_doc.doc_type = "mark_scheme"
    ms_doc.paper_code = "11"
    ms_rev.parse_status = "parsed"
    ms = MarkScheme(document_id=ms_doc.id, matched_paper_document_id=target.id)
    other_ms = MarkScheme(document_id=other.id, matched_paper_document_id=other.id)
    db.add_all([ms, other_ms])
    db.flush()
    linked = MarkSchemeEntry(mark_scheme_id=ms.id, question_id=question.id, number_label="1",
                             number_path="1", marks=3, answer_text="42")
    untouched_same_ms = MarkSchemeEntry(mark_scheme_id=ms.id, number_label="2", number_path="2")
    untouched_other_ms = MarkSchemeEntry(mark_scheme_id=other_ms.id, number_label="1", number_path="1")
    db.add_all([linked, untouched_same_ms, untouched_other_ms])
    db.commit()
    for sentinel in sentinels:
        db.refresh(sentinel)
    before = [{c.name: getattr(s, c.name) for c in s.__table__.columns} for s in sentinels]
    review_id = review.id

    result = reparse_documents(db, document_ids=[target.id, target.id], keep_history=keep_history,
                               settings=_settings(tmp_path))
    db.flush()
    assert result["documents"] == 1
    assert result["parse_stats"]["revisions"] == 1
    assert result["parse_stats"]["questions"] == 2
    assert old_rev.parse_status == "parsed"
    assert old_rev.status == "superseded"
    assert current.parse_status == "parsed"
    assert pending.parse_status == "pending"
    assert third_rev.parse_status == "failed"
    assert third_rev.parse_error == "unrelated failure"
    assert ms_rev.parse_status == "parsed"
    assert result["relinked"] == {"papers": 1, "entries": 1, "linked": 1}
    assert linked.question_id == db.scalar(select(Question.id).join(Paper).where(
        Paper.document_id == target.id, Question.number_path == "1"
    ))
    assert untouched_same_ms.question_id is None
    assert untouched_other_ms.question_id is None
    assert result["derived"]["difficulty"]["written"] == 2
    assert "pairs" in result["derived"]["similarity"]
    assert "error" not in result["derived"]
    for sentinel, expected in zip(sentinels, before):
        db.refresh(sentinel)
        assert {c.name: getattr(sentinel, c.name) for c in sentinel.__table__.columns} == expected
    assets = list(db.scalars(select(Asset)))
    assert len(assets) == 1
    assert (tmp_path / "artifacts" / assets[0].storage_key).read_bytes() == b"synthetic-image"
    assert db.scalar(select(Formula.id)) is None
    assert db.get(ParseRun, other_run.id) is not None
    assert (db.get(ParseRun, old_run_id) is not None) is keep_history
    assert db.get(ReviewTask, review_id).resolution == "reviewed"
    if not keep_history:
        assert db.get(ReviewTask, review_id).parse_run_id is None
        assert db.scalar(select(ValidationFinding.id)) is None


@pytest.mark.parametrize("limit", [0, -1])
def test_reparse_invalid_limit_does_not_purge(db, tmp_path, limit):
    doc, revision = _document(db, tmp_path, "limit")
    question, _ = _old_question(db, doc, revision)
    with pytest.raises(ValueError, match="limit"):
        reparse_documents(db, document_ids=[doc.id], limit=limit, settings=_settings(tmp_path))
    assert db.get(type(question), question.id) is question


def test_pipeline_rolled_back_counters_and_per_revision_stats(db, tmp_path, synthetic_parser, monkeypatch):
    first, first_rev = _document(db, tmp_path, "first")
    second, second_rev = _document(db, tmp_path, "second")
    third, third_rev = _document(db, tmp_path, "third")
    first.doc_type = second.doc_type = third.doc_type = "question_paper"
    db.commit()
    parse = ParsePipeline._parse_question_paper

    def fail_first(self, doc, revision, run, path):
        parse(self, doc, revision, run, path)
        if doc.id == first.id:
            raise ValueError("after partial writes")

    monkeypatch.setattr(ParsePipeline, "_parse_question_paper", fail_first)
    stats = ParsePipeline(db, settings=_settings(tmp_path)).run()
    assert stats.revisions == 2
    assert stats.failed == 1
    assert stats.papers == 2
    assert stats.questions == 4
    assert first_rev.parse_status == "failed"
    assert second_rev.parse_status == third_rev.parse_status == "parsed"
    runs = list(db.scalars(select(ParseRun).order_by(ParseRun.id)))
    assert len(runs) == 3
    assert runs[0].status == "failed"
    assert "after partial writes" in runs[0].params["error"]
    successful = [r for r in runs if r.status == "completed"]
    assert [r.stats["questions"] for r in successful] == [2, 2]
    assert [r.stats["papers"] for r in successful] == [1, 1]
    assert db.scalar(select(Paper.id).where(Paper.document_id == first.id)) is None


def test_pipeline_scope_validation_and_empty_scopes(db, tmp_path, synthetic_parser):
    first, first_rev = _document(db, tmp_path, "first")
    second, second_rev = _document(db, tmp_path, "second")
    pipe = ParsePipeline(db, settings=_settings(tmp_path))
    for kwargs in ({"document_id": 999}, {"revision_ids": [999]},
                   {"document_ids": [first.id], "revision_ids": [second_rev.id]},
                   {"document_id": first.id, "document_ids": [first.id]}, {"limit": 0}):
        with pytest.raises(ValueError):
            pipe.run(**kwargs)
    assert pipe.run(document_ids=[]).revisions == 0
    assert pipe.run(revision_ids=[]).revisions == 0
    assert first_rev.parse_status == second_rev.parse_status == "pending"


def test_reparse_missing_artifact_preflight_preserves_all_targets(db, tmp_path, synthetic_parser):
    first, first_rev = _document(db, tmp_path, "first")
    second, second_rev = _document(db, tmp_path, "second")
    first_question, _ = _old_question(db, first, first_rev)
    second_question, _ = _old_question(db, second, second_rev)
    (tmp_path / "artifacts" / db.get(Artifact, second_rev.artifact_id).storage_key).unlink()
    with pytest.raises(ValueError, match="artifact"):
        reparse_documents(db, document_ids=[first.id, second.id], settings=_settings(tmp_path))
    assert db.get(type(first_question), first_question.id) is first_question
    assert db.get(type(second_question), second_question.id) is second_question


def test_reparse_success_still_belongs_to_callers_transaction(db, tmp_path, synthetic_parser):
    from examdata.core.models import Question

    doc, rev = _document(db, tmp_path, "target")
    doc.doc_type = "question_paper"
    rev.parse_status = "parsed"
    old_question, old_run = _old_question(db, doc, rev)
    old_question_id, old_run_id = old_question.id, old_run.id
    db.commit()
    result = reparse_documents(db, document_ids=[doc.id], settings=_settings(tmp_path))
    assert result["parse_stats"]["questions"] == 2
    db.rollback()
    assert db.get(Question, old_question_id).stem_text == "Old expression."
    assert list(db.scalars(select(ParseRun.id))) == [old_run_id]


@pytest.mark.parametrize("kind", ["approved", "rejected", "pending", "manual_taxonomy", "official_difficulty", "official_answer", "manual_formula"])
@pytest.mark.parametrize("changed", [False, True])
def test_protected_content_restored_or_reparse_rolled_back(db, tmp_path, synthetic_parser, kind, changed):
    from examdata.core.models import (GeneratedExplanation, QuestionTaxonomy, TaxonomyNode,
                                     Difficulty, OfficialAnswer, Formula, Question)
    doc, rev = _document(db, tmp_path, "protected")
    doc.doc_type = "question_paper"
    question, run = _old_question(db, doc, rev)
    question.stem_text = "changed" if changed else "Calculate the value of this expression."
    old_id, run_id = question.id, run.id
    if kind in {"approved", "rejected", "pending"}:
        row = GeneratedExplanation(question_id=old_id, provider="manual", prompt_version="old",
                                   review_status=kind, approach="Keep exactly")
    elif kind == "manual_taxonomy":
        node = TaxonomyNode(code="manual", name="Manual")
        db.add(node); db.flush()
        row = QuestionTaxonomy(question_id=old_id, node_id=node.id, source="manual", reviewed=True)
    elif kind == "official_difficulty":
        row = Difficulty(question_id=old_id, source="official", value=0.7)
    elif kind == "official_answer":
        row = OfficialAnswer(question_id=old_id, source="mark_scheme", content="42", source_document_id=None)
    else:
        row = Formula(question_id=old_id, source="manual", latex="x+y")
    db.add(row); db.commit(); db.refresh(row)
    model = type(row)
    values = {c.name: getattr(row, c.name) for c in model.__table__.columns}
    if changed:
        result = reparse_documents(db, document_ids=[doc.id], settings=_settings(tmp_path))
        assert result["aborted"] is True
        assert "旧结果已保留" in result["reason"]
        assert db.get(Question, old_id).stem_text == "changed"
        assert db.get(ParseRun, run_id) is not None
        assert db.scalar(select(ParseRun.id).where(ParseRun.status == "failed")) is not None
    else:
        reparse_documents(db, document_ids=[doc.id], settings=_settings(tmp_path))
    restored = db.get(model, values["id"])
    assert restored is not None
    assert {c.name: getattr(restored, c.name) for c in model.__table__.columns if c.name != "question_id"} == {
        k: v for k, v in values.items() if k != "question_id"}
    assert db.get(Question, restored.question_id) is not None
    if db.bind.dialect.name == "sqlite":
        assert db.connection().exec_driver_sql("PRAGMA foreign_key_check").all() == []


@pytest.mark.parametrize("active", [True, False])
def test_reparse_does_not_touch_unrelated_overrides(db, tmp_path, synthetic_parser, active):
    from examdata.core.models import FieldOverride
    target, rev = _document(db, tmp_path, "target")
    target.doc_type = "question_paper"
    _old_question(db, target, rev)
    other, other_rev = _document(db, tmp_path, "other")
    question, _ = _old_question(db, other, other_rev)
    ov = FieldOverride(target_type="question", target_id=question.id, field_path="marks",
                       value=9, source_value=3, author="test", active=active)
    db.add(ov); db.commit(); db.refresh(ov)
    before = {c.name: getattr(ov, c.name) for c in FieldOverride.__table__.columns}
    reparse_documents(db, document_ids=[target.id], settings=_settings(tmp_path))
    db.refresh(ov)
    assert {c.name: getattr(ov, c.name) for c in FieldOverride.__table__.columns} == before


@pytest.mark.parametrize("policy", ["*", ["obsolete"]])
def test_reparse_multiple_overrides_use_version_and_baseline_once(db, tmp_path, synthetic_parser, policy):
    from examdata.core.models import FieldOverride, Question
    doc, rev = _document(db, tmp_path, "overridden")
    doc.doc_type = "question_paper"
    q, _ = _old_question(db, doc, rev)
    for field, baseline, value in [("marks", 3, 9), ("kind", "question", "manual")]:
        db.add(FieldOverride(target_type="question", target_id=q.id, field_path=field,
                             source_value=baseline, value=value, author="test",
                             applies_to_parser_versions=policy))
    db.commit()
    result = reparse_documents(db, document_ids=[doc.id], settings=_settings(tmp_path))
    overrides = list(db.scalars(select(FieldOverride)))
    assert len({ov.target_id for ov in overrides}) == 1
    question = db.get(Question, overrides[0].target_id)
    if policy == "*":
        assert result["overrides"]["applied"] == 2
        assert not any(ov.conflict_detected for ov in overrides)
        assert (question.marks, question.kind) == (9, "manual")
    else:
        assert result["overrides"]["conflicted"] == 2
        assert all(ov.conflict_detected for ov in overrides)
        assert (question.marks, question.kind) == (3, "question")


@pytest.mark.parametrize("combined", [False, True])
@pytest.mark.parametrize("new_answer", ["42", "43", None])
def test_source_reparse_migrates_official_answers_and_preserves_review(db, tmp_path, synthetic_parser, monkeypatch, combined, new_answer):
    from examdata.core.models import MarkScheme, MarkSchemeEntry, OfficialAnswer, GeneratedExplanation, ReviewTask, Question
    from examdata.markscheme.base import MarkSchemeDraft, MarkSchemeEntryDraft
    qp, qp_rev = _document(db, tmp_path, "qp-source")
    qp.doc_type = "question_paper"; qp.paper_code = "11"; qp_rev.parse_status = "parsed"
    q, _ = _old_question(db, qp, qp_rev)
    q.stem_text = "Calculate the value of this expression."
    msdoc, msrev = _document(db, tmp_path, "ms-source")
    msdoc.doc_type = "mark_scheme"; msdoc.paper_code = "11"; msrev.parse_status = "parsed"
    run = ParseRun(document_revision_id=msrev.id, parser_version="old", status="completed")
    db.add(run); db.flush()
    ms = MarkScheme(document_id=msdoc.id, matched_paper_document_id=qp.id, parse_run_id=run.id)
    db.add(ms); db.flush()
    db.add(MarkSchemeEntry(mark_scheme_id=ms.id, question_id=q.id, number_label="1", number_path="1", answer_text="42", marks=3))
    db.add(OfficialAnswer(question_id=q.id, source="mark_scheme", source_document_id=msdoc.id, content="42"))
    generated = GeneratedExplanation(question_id=q.id, provider="rule-based", prompt_version="old", review_status="approved", final_answer="42")
    db.add(generated); db.flush()
    generated_id = generated.id
    db.add(ReviewTask(target_type="generated_explanation", target_id=generated_id, reason="explanation_review", status="done", assignee="teacher", resolution="approved"))
    db.commit()
    monkeypatch.setattr("examdata.parsing.pipeline.CambridgeMarkSchemeParser.parse", lambda *args, **kwargs:
        MarkSchemeDraft(entries=[MarkSchemeEntryDraft("1", "1", answer_text=new_answer, marks=3)], metadata={"total_marks": 3}))
    result = reparse_documents(db, document_ids=[qp.id, msdoc.id] if combined else [msdoc.id], settings=_settings(tmp_path))
    assert not result.get("aborted"), result
    answers = list(db.scalars(select(OfficialAnswer).where(OfficialAnswer.source_document_id == msdoc.id)))
    assert [a.content for a in answers] == ([new_answer] if new_answer is not None else [])
    retained = db.get(GeneratedExplanation, generated_id)
    assert retained.review_status == "approved" and retained.final_answer == "42"
    assert db.get(Question, retained.question_id) is not None
    changed = new_answer != "42"
    assert result["source_migration"]["changed_questions"] == int(changed)
    assert bool(db.scalar(select(ReviewTask.id).where(ReviewTask.reason == "official_source_changed"))) == changed
    assert result["derived"]["difficulty"]["written"] >= 1
    from examdata.api.app import question_explanation
    payload = question_explanation(retained.question_id, db)
    public_retained = next(item for item in payload["generated"] if item["id"] == generated_id)
    assert public_retained["requires_review"] is changed
    if changed:
        from examdata.intelligence.explanation import review_explanation
        review_explanation(db, generated_id, status="approved", author="teacher")
        payload = question_explanation(retained.question_id, db)
        assert not next(item for item in payload["generated"] if item["id"] == generated_id)["requires_review"]
    db.commit()


def test_failed_parse_cleans_new_files_but_keeps_preexisting(db, tmp_path, synthetic_parser, monkeypatch):
    from examdata.core.storage import ContentAddressedStore
    from examdata.core.models import Asset
    doc, rev = _document(db, tmp_path, "file-failure")
    doc.doc_type = "question_paper"; db.commit()
    store = ContentAddressedStore(tmp_path / "artifacts")
    preexisting = store.put_bytes(b"preexisting", "image/png")
    parse = ParsePipeline._parse_question_paper
    def fail(self, *args):
        parse(self, *args)
        raise ValueError("after file publication")
    monkeypatch.setattr(ParsePipeline, "_parse_question_paper", fail)
    stats = ParsePipeline(db, settings=_settings(tmp_path)).run()
    assert stats.failed == 1
    assert preexisting.path.is_file()
    assert not store.exists(sha256(b"synthetic-image").hexdigest())
    assert db.scalar(select(Asset.id)) is None
    assert not db.info.get("parse_file_cleanup_errors")


def test_caller_rollback_cleans_successful_new_files(db, tmp_path, synthetic_parser):
    from examdata.core.storage import ContentAddressedStore
    doc, rev = _document(db, tmp_path, "file-rollback")
    doc.doc_type = "question_paper"; db.commit()
    ParsePipeline(db, settings=_settings(tmp_path)).run(commit=False)
    store = ContentAddressedStore(tmp_path / "artifacts")
    assert store.exists(sha256(b"synthetic-image").hexdigest())
    db.rollback()
    assert not store.exists(sha256(b"synthetic-image").hexdigest())
    assert not db.info.get("parse_file_cleanup_errors")



def test_similarity_rebuild_is_scoped_and_preserves_other_methods(db, tmp_path):
    from examdata.core.models import QuestionSimilarity
    from examdata.intelligence.similarity import find_similar, METHOD
    questions=[]
    for name in ("one", "two", "three"):
        doc, rev = _document(db, tmp_path, name)
        q, _ = _old_question(db, doc, rev)
        q.stem_text = "Solve the quadratic equation and give both roots of the expression."
        questions.append(q)
    a,b,c=questions
    untouched=QuestionSimilarity(question_a_id=b.id,question_b_id=c.id,method=METHOD,score=.123,features={"sentinel":True})
    manual=QuestionSimilarity(question_a_id=a.id,question_b_id=b.id,method="manual",score=.777)
    db.add_all([untouched,manual]);db.commit();db.refresh(untouched);db.refresh(manual)
    before=[{column.name:getattr(row,column.name) for column in QuestionSimilarity.__table__.columns} for row in (untouched,manual)]
    assert find_similar(db,question_ids=[a.id],replace=True)["pairs"]==2
    for row,expected in zip((untouched,manual),before):
        db.refresh(row)
        assert {column.name:getattr(row,column.name) for column in QuestionSimilarity.__table__.columns}==expected
    assert find_similar(db,question_ids=[],replace=True)["pairs"]==0
    assert find_similar(db,question_ids=[a.id],replace=True)["pairs"]==2


def test_similarity_short_scope_removes_stale_pairs(db, tmp_path):
    from examdata.core.models import QuestionSimilarity
    from examdata.intelligence.similarity import find_similar, METHOD
    first,rev = _document(db,tmp_path,"short-one");second,rev2 = _document(db,tmp_path,"short-two")
    a,_=_old_question(db,first,rev);b,_=_old_question(db,second,rev2)
    db.add(QuestionSimilarity(question_a_id=a.id,question_b_id=b.id,method=METHOD,score=.9));db.commit()
    assert find_similar(db,question_ids=[a.id],replace=True)["pairs"]==0
    assert db.scalar(select(QuestionSimilarity.id)) is None



def test_reparse_preserves_manual_similarity_on_rebuilt_question(db, tmp_path, synthetic_parser):
    from examdata.core.models import QuestionSimilarity, Question
    doc,rev=_document(db,tmp_path,"manual-similarity-target");doc.doc_type="question_paper"
    q,_=_old_question(db,doc,rev);q.stem_text="Calculate the value of this expression."
    other,orev=_document(db,tmp_path,"manual-similarity-other");oq,_=_old_question(db,other,orev)
    row=QuestionSimilarity(question_a_id=q.id,question_b_id=oq.id,method="manual",score=.99,features={"author":"teacher"})
    db.add(row);db.commit();row_id=row.id
    result=reparse_documents(db,document_ids=[doc.id],settings=_settings(tmp_path))
    assert not result.get("aborted"),result.get("reason")
    restored=db.get(QuestionSimilarity,row_id)
    assert restored.method=="manual" and restored.score==.99 and restored.features=={"author":"teacher"}
    assert db.get(Question,restored.question_a_id) is not None
    assert db.get(Question,restored.question_b_id) is not None
