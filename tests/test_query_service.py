"""查询层回归测试：使用开启外键约束的内存 SQLite，不依赖本地语料。"""

from __future__ import annotations

import dataclasses
import random
import re

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from examdata.core.models import (
    Base,
    Board,
    Difficulty,
    Document,
    Paper,
    Question,
    QuestionTaxonomy,
    TaxonomyNode,
)
from examdata.query.service import (
    PaperFilter,
    QuestionFilter,
    count_papers,
    count_questions,
    sample_questions,
    search_papers,
    search_questions,
)


@pytest.fixture
def query_session():
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def configure_sqlite(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA temp_store=MEMORY")

    Base.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            board = Board(key="test", name="Test board")
            session.add(board)
            session.flush()
            for index, text in enumerate([
                "Calculate a percentage of 50% for this example",
                "Explain the literal token x_y",
                r"Describe the literal path C:\paper",
                "Evaluate the expression and justify the result",
            ]):
                document = Document(
                    identity_key=f"query-{index}", board_id=board.id,
                    doc_type="question_paper", year=2024 - index // 2,
                    paper_code=str(index % 2 + 1),
                )
                session.add(document)
                session.flush()
                paper = Paper(document_id=document.id)
                session.add(paper)
                session.flush()
                session.add(Question(
                    paper_id=paper.id, number_label="1", number_path="1",
                    display_order=0, marks=index + 1, stem_text=text,
                ))
            session.flush()
            yield session
    finally:
        engine.dispose()


# --------------------------------------------------------------------------
# 分页参数校验
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "searcher,filter_factory",
    [(search_questions, QuestionFilter), (search_papers, PaperFilter)],
    ids=["question", "paper"],
)
@pytest.mark.parametrize("kwargs", [{"limit": 0}, {"limit": -1}, {"offset": -1}])
def test_invalid_page_params_are_rejected(searcher, filter_factory, kwargs):
    """limit<1 或 offset<0 必须直接报错。

    session 传 None：校验要在任何数据库访问之前完成，参数不合法时不该先去
    连库（负 limit 到了 SQLite 就成了"不限制"）。
    """
    with pytest.raises(ValueError):
        searcher(None, filter_factory(**kwargs))


# --------------------------------------------------------------------------
# 计数不受分页影响
# --------------------------------------------------------------------------


def test_count_questions_ignores_limit_and_offset(query_session):
    first_page = count_questions(query_session, QuestionFilter(limit=1, offset=0))
    deep_page = count_questions(query_session, QuestionFilter(limit=5, offset=2))
    assert first_page == deep_page == 4


def test_count_papers_ignores_limit_and_offset(query_session):
    total = count_papers(query_session, PaperFilter())
    assert total == 4
    assert count_papers(query_session, PaperFilter(limit=1, offset=0)) == total
    assert count_papers(query_session, PaperFilter(limit=3, offset=1)) == total


def test_question_pages_do_not_overlap_or_drop_rows(query_session):
    total = count_questions(query_session, QuestionFilter())
    f = QuestionFilter()
    first = search_questions(query_session, dataclasses.replace(f, limit=2, offset=0))
    second = search_questions(query_session, dataclasses.replace(f, limit=2, offset=2))
    ids_first = [q["question_id"] for q in first]
    ids_second = [q["question_id"] for q in second]
    assert len(ids_first) == min(total, 2)
    assert len(ids_second) == min(total, 2)
    assert set(ids_first).isdisjoint(ids_second)
    assert len(set(ids_first) | set(ids_second)) == min(total, 4)


def test_paper_pages_do_not_overlap_or_drop_rows(query_session):
    total = count_papers(query_session, PaperFilter())
    f = PaperFilter()
    first = search_papers(query_session, dataclasses.replace(f, limit=2, offset=0))
    second = search_papers(query_session, dataclasses.replace(f, limit=2, offset=2))
    ids_first = [p["paper_id"] for p in first]
    ids_second = [p["paper_id"] for p in second]
    assert set(ids_first).isdisjoint(ids_second)
    assert len(set(ids_first) | set(ids_second)) == min(total, 4)


def test_question_paging_order_is_stable(query_session):
    f = QuestionFilter(limit=50)
    rows = search_questions(query_session, f)
    again = search_questions(query_session, f)
    ids = [q["question_id"] for q in rows]
    assert ids == [q["question_id"] for q in again]
    assert len(ids) == len(set(ids)), "同一页内不应出现重复题目"
    years = [q["year"] or 0 for q in rows]
    assert years == sorted(years, reverse=True)
    by_year: dict[int | None, list[str]] = {}
    for q in rows:
        by_year.setdefault(q["year"], []).append(q["paper_code"] or "")
    for codes in by_year.values():
        assert codes == sorted(codes)


@pytest.mark.parametrize("keyword", ["%", "_", "\\"])
def test_keyword_does_not_degrade_into_wildcard(query_session, keyword):
    rows = search_questions(query_session, QuestionFilter(keyword=keyword))
    assert len(rows) == count_questions(query_session, QuestionFilter(keyword=keyword)) == 1
    assert keyword in rows[0]["stem_text"]
    assert count_questions(query_session, QuestionFilter(keyword="zzz%zzz")) == 0


def test_keyword_matches_real_substring(query_session):
    sample = search_questions(query_session, QuestionFilter(limit=1))[0]
    word = re.search(r"[A-Za-z]{6,}", sample["stem_text"]).group(0)
    f = QuestionFilter(keyword=word)
    total = count_questions(query_session, f)
    assert total > 0, f"题干里的 {word!r} 应能检索到"
    hits = [q["question_id"] for q in search_questions(
        query_session, dataclasses.replace(f, limit=total)
    )]
    assert sample["question_id"] in hits


@pytest.fixture
def tagged_questions(query_session):
    questions = list(query_session.scalars(select(Question).order_by(Question.id)))
    board = query_session.scalar(select(Board))
    other_board = Board(key="other", name="Other board")
    query_session.add(other_board)
    query_session.flush()
    nodes = [
        TaxonomyNode(board_id=board.id, code="algebra", name="Algebra"),
        TaxonomyNode(board_id=other_board.id, code="algebra", name="Algebra"),
        TaxonomyNode(board_id=board.id, code="geometry", name="Geometry"),
    ]
    query_session.add_all(nodes)
    query_session.flush()
    query_session.add_all([
        QuestionTaxonomy(question_id=questions[0].id, node_id=nodes[0].id, source="manual"),
        QuestionTaxonomy(question_id=questions[0].id, node_id=nodes[1].id, source="auto"),
        QuestionTaxonomy(question_id=questions[1].id, node_id=nodes[0].id, source="auto"),
        QuestionTaxonomy(question_id=questions[2].id, node_id=nodes[2].id, source="manual"),
        Difficulty(question_id=questions[0].id, source="manual", value=0.2),
        Difficulty(question_id=questions[0].id, source="estimated", value=0.4),
        Difficulty(question_id=questions[1].id, source="estimated", value=0.3),
        Difficulty(question_id=questions[2].id, source="manual", value=0.9),
    ])
    query_session.flush()
    return questions


def test_relation_filters_do_not_multiply_question_rows(query_session, tagged_questions):
    f = QuestionFilter(taxonomy_code="algebra", difficulty_max=0.5, limit=1)
    assert count_questions(query_session, f) == 2
    first = search_questions(query_session, f)
    second = search_questions(query_session, dataclasses.replace(f, offset=1))
    assert [q["question_id"] for q in first + second] == [
        q.id for q in tagged_questions[:2]
    ]
    composition = sample_questions(query_session, f, count=10, seed=0)
    assert {q["question_id"] for q in composition.questions} == {
        q.id for q in tagged_questions[:2]
    }
    assert len(composition.questions) == 2
    assert composition.marks_total == 3


@pytest.mark.parametrize("filters", [
    {"taxonomy_source": "manual"},
    {"difficulty_source": "manual"},
    {"taxonomy_source": "manual", "difficulty_source": "manual"},
])
def test_sources_filter_independently(query_session, tagged_questions, filters):
    f = QuestionFilter(**filters)
    assert count_questions(query_session, f) == 2
    assert [q["question_id"] for q in search_questions(query_session, f)] == [
        tagged_questions[0].id, tagged_questions[2].id,
    ]


@pytest.mark.parametrize("filters", [
    {"taxonomy_code": "algebra", "taxonomy_source": "manual"},
    {"difficulty_min": 0.1, "difficulty_max": 0.3, "difficulty_source": "manual"},
])
def test_source_and_value_require_the_same_relation(query_session, tagged_questions, filters):
    f = QuestionFilter(**filters)
    assert count_questions(query_session, f) == 1
    assert search_questions(query_session, f)[0]["question_id"] == tagged_questions[0].id


def test_difficulty_range_cannot_match_two_different_rows(query_session, tagged_questions):
    f = QuestionFilter(difficulty_min=0.3, difficulty_max=0.3, difficulty_source="manual")
    assert count_questions(query_session, f) == 0
    assert search_questions(query_session, f) == []


@pytest.mark.parametrize("mode", ["count", "marks"])
def test_sampling_uses_all_matches_not_first_5000(query_session, mode):
    paper = query_session.scalar(select(Paper).order_by(Paper.id))
    questions = [Question(
        paper_id=paper.id, number_label=str(index + 2), number_path=str(index + 2),
        display_order=index + 1, marks=1, stem_text="Sample pool",
    ) for index in range(5001)]
    query_session.add_all(questions)
    query_session.flush()
    f = QuestionFilter(paper_code="1", year=2024, limit=1, offset=5000)
    pool = search_questions(query_session, dataclasses.replace(f, limit=6000, offset=0))
    expected = [row["question_id"] for row in pool]
    random.Random(17).shuffle(expected)
    kwargs = {"count": len(pool)} if mode == "count" else {"marks_target": len(pool)}
    composition = sample_questions(query_session, f, seed=17, **kwargs)
    assert len(pool) == 5002
    assert [row["question_id"] for row in composition.questions] == expected
    assert composition.marks_total == len(pool)
    assert composition.requested_marks == kwargs.get("marks_target")
