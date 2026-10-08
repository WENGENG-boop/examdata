from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.orm import Session
from examdata.core.models import Base, Board, Document, Paper, Question

spec = spec_from_file_location("reset_derived_script", Path(__file__).resolve().parents[1] / "scripts/reset_derived.py")
reset = module_from_spec(spec)
spec.loader.exec_module(reset)

@pytest.mark.parametrize("kind", ["override", "official_answer", "approved", "rejected", "reviewed_pending", "manual_taxonomy", "official_difficulty", "manual_formula"])
def test_reset_refuses_protected_data_atomically(tmp_path, kind):
    from examdata.core.models import (FieldOverride, OfficialAnswer, GeneratedExplanation,
        ReviewTask, TaxonomyNode, QuestionTaxonomy, Difficulty, Formula)
    engine = create_engine("sqlite:///" + (tmp_path / "test.db").as_posix())
    @event.listens_for(engine, "connect")
    def fk(conn, record):
        conn.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(Board(id=1, key="test", name="Test")); db.flush()
        doc = Document(board_id=1, identity_key="test", doc_type="question_paper")
        db.add(doc); db.flush()
        paper = Paper(document_id=doc.id); db.add(paper); db.flush()
        q = Question(paper_id=paper.id, number_path="1", number_label="1", display_order=1)
        db.add(q); db.flush()
        if kind == "override":
            row = FieldOverride(target_type="question", target_id=q.id, field_path="marks", value=3, source_value=None, active=False)
        elif kind == "official_answer":
            row = OfficialAnswer(question_id=q.id, source="mark_scheme", content="42")
        elif kind in {"approved", "rejected", "reviewed_pending"}:
            row = GeneratedExplanation(question_id=q.id, provider="rule", prompt_version="1",
                review_status="pending" if kind == "reviewed_pending" else kind)
            db.add(row); db.flush()
            if kind == "reviewed_pending":
                db.add(ReviewTask(target_type="generated_explanation", target_id=row.id, reason="explanation_review", status="done"))
        elif kind == "manual_taxonomy":
            node = TaxonomyNode(code="manual", name="Manual"); db.add(node); db.flush()
            row = QuestionTaxonomy(question_id=q.id, node_id=node.id, source="manual")
        elif kind == "official_difficulty":
            row = Difficulty(question_id=q.id, source="official", value=.7)
        else:
            row = Formula(question_id=q.id, source="manual", latex="x")
        db.add(row); db.commit()
    with engine.connect() as conn:
        before = {t.name: conn.execute(text(f'SELECT * FROM "{t.name}"')).all() for t in Base.metadata.tables.values()}
    with pytest.raises(ValueError, match="protected"):
        reset.reset_derived(engine, confirm=True)
    with engine.connect() as conn:
        after = {t.name: conn.execute(text(f'SELECT * FROM "{t.name}"')).all() for t in Base.metadata.tables.values()}
        assert conn.exec_driver_sql("PRAGMA foreign_key_check").all() == []
    assert before == after
    engine.dispose()


def test_reset_rejects_other_backends_before_connecting():
    with pytest.raises(ValueError, match="SQLite"):
        reset.reset_derived(SimpleNamespace(dialect=SimpleNamespace(name="postgresql")), confirm=True)


def test_reset_unprotected_empty_database(tmp_path):
    engine = create_engine("sqlite:///" + (tmp_path / "empty.db").as_posix())
    Base.metadata.create_all(engine)
    with pytest.raises(ValueError, match="confirmation"):
        reset.reset_derived(engine)
    assert reset.reset_derived(engine, confirm=True)["question"] == 0
    engine.dispose()
