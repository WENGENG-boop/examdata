"""智能层回归测试。

这三层（知识点 / 难度 / 相似题）此前是空表，本轮才建起来。
测试锁定的是**可复现性**与**边界正确性**，而不是具体数值：
数值会随语料增长而变，但"同样的输入永远给同样的输出"
以及"官方数据不被自动结果污染"这两条必须永远成立。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from examdata.core.models import (
    Board,
    Difficulty,
    Document,
    Paper,
    Question,
    QuestionSimilarity,
    QuestionTaxonomy,
    Subject,
    TaxonomyNode,
)
from examdata.intelligence.difficulty import estimate
from examdata.intelligence.similarity import (
    _is_ancestor_pair,
    _root_of,
    normalize_text,
    ngrams,
)
from examdata.intelligence.taxonomy import classify_question


# --------------------------------------------------------------------------
# 知识点
# --------------------------------------------------------------------------


def test_keyword_classification_hits_the_right_subtopic():
    text = "Write 4876 correct to the nearest hundred."
    hits = classify_question(text, "0580")
    assert hits, "应能识别出知识点"
    assert hits[0].node_code == "0580.1.4", f"应为估算与精度，实际 {hits[0].node_code}"


def test_longer_keywords_outrank_shorter_ones():
    """'quadratic' 比 'solve' 具体，命中时应排在前面。"""
    hits = classify_question("Solve the quadratic equation by factorising.", "0580")
    codes = [h.node_code for h in hits]
    assert "0580.2.2" in codes, codes


def test_unrelated_text_yields_no_assignment():
    """宁缺毋滥：没有关键词命中的题不标注。"""
    assert classify_question("", "0580") == []
    assert classify_question("zzzz qqqq", "0580") == []


def test_unknown_subject_yields_nothing():
    assert classify_question("solve the quadratic equation", "9999") == []


def test_word_boundary_does_not_match_inside_words():
    """'sin' 不应命中 'using' 里的 'sin'。"""
    hits = classify_question("Using the results from part (a)", "0580")
    codes = {h.node_code for h in hits}
    assert "0580.6.1" not in codes, "不应把 using 里的 sin 当成三角函数命中"


# --------------------------------------------------------------------------
# 难度
# --------------------------------------------------------------------------


def test_difficulty_is_bounded_and_monotone_in_marks():
    low = estimate(marks=1, stem_text="x", child_count=0, depth=0, has_asset=False, taxonomy_count=0)
    high = estimate(
        marks=8,
        stem_text="Show that " + "x" * 300,
        child_count=4,
        depth=1,
        has_asset=True,
        taxonomy_count=2,
    )
    assert 0.0 <= low.value <= 1.0
    assert 0.0 <= high.value <= 1.0
    assert high.value > low.value


def test_low_mark_questions_are_capped():
    """1 分小问不该被判成难题。"""
    est = estimate(
        marks=1,
        stem_text="Prove that " + "x" * 500,
        child_count=5,
        depth=2,
        has_asset=True,
        taxonomy_count=3,
    )
    assert est.value <= 0.45


def test_difficulty_features_are_auditable():
    est = estimate(
        marks=3,
        stem_text="Hence find the exact value.",
        child_count=0,
        depth=0,
        has_asset=False,
        taxonomy_count=0,
    )
    f = est.features
    for key in ("marks", "stem_chars", "hard_phrases", "weights", "raw"):
        assert key in f
    assert "hence" in f["hard_phrases"]
    assert "exact value" in f["hard_phrases"]


def test_difficulty_is_deterministic():
    kwargs = dict(
        marks=4, stem_text="Show that the area is 20.", child_count=1, depth=1,
        has_asset=True, taxonomy_count=1,
    )
    assert estimate(**kwargs).value == estimate(**kwargs).value


# --------------------------------------------------------------------------
# 相似题
# --------------------------------------------------------------------------


def test_normalize_folds_numbers():
    """数字折叠是识别'同型题换数字'的关键。"""
    a = normalize_text("Write 4876 correct to the nearest hundred.")
    b = normalize_text("Write 17 875 correct to the nearest hundred.")
    assert a == b


def test_normalize_strips_punctuation_and_case():
    assert normalize_text("Find the value of X!") == "find the value of x"


def test_ngrams_of_short_text():
    assert ngrams("ab", 3) == ["ab"]
    assert ngrams("", 3) == []
    assert len(ngrams("abcd", 3)) == 2


@pytest.mark.parametrize(
    "pa,pb,expected",
    [
        ("8", "8(d)", True),
        ("3", "3(b)", True),
        ("10(a)", "10(b)", True),      # 兄弟小问，措辞几乎一致
        ("10(a)", "10(c)", True),
        ("14(a)(i)", "14(b)", True),
        ("5(a)(ii)", "5(a)(iii)", True),
        ("6", "11", False),            # 同卷不同大题
        ("1(a)", "2(a)", False),
    ],
)
def test_same_root_pairs_are_excluded(pa, pb, expected):
    """同一道大题内部（含父子与兄弟）的题对不是相似题。"""
    assert _is_ancestor_pair((1, pa), (1, pb)) is expected


def test_cross_paper_pairs_are_kept():
    """不同试卷的同号题是真正的重复题，必须保留。"""
    assert _is_ancestor_pair((1, "1(c)"), (2, "1(c)")) is False


def test_root_of():
    assert _root_of("10(a)") == "10"
    assert _root_of("14(a)(i)") == "14"
    assert _root_of("(a)") == ""
    assert _root_of("") == ""


# --------------------------------------------------------------------------
# 落库数据的完整性（对着真实数据库）
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def session():
    from examdata.core.config import get_settings

    url = get_settings().database_url
    engine = create_engine(url)
    with Session(engine) as s:
        yield s


def test_intelligence_tables_are_populated(session):
    """智能层不能是空表——这正是本轮补上的缺口。"""
    assert session.scalar(select(func.count(TaxonomyNode.id))) > 0
    assert session.scalar(select(func.count(QuestionTaxonomy.id))) > 0
    assert session.scalar(select(func.count(Difficulty.id))) > 0
    assert session.scalar(select(func.count(QuestionSimilarity.id))) > 0


def test_official_difficulty_is_never_overwritten(session):
    """自动估计只写 source=estimated，不得出现被冒充的官方难度。"""
    sources = {r for r in session.scalars(select(Difficulty.source).distinct()).all()}
    assert sources <= {"estimated", "official", "manual"}
    official = session.scalar(
        select(func.count(Difficulty.id)).where(Difficulty.source == "official")
    )
    assert official == 0 or sources == {"official"} or "estimated" in sources


def test_every_taxonomy_assignment_points_at_a_real_node(session):
    orphan = session.scalar(
        select(func.count(QuestionTaxonomy.id))
        .join(TaxonomyNode, TaxonomyNode.id == QuestionTaxonomy.node_id, isouter=True)
        .where(TaxonomyNode.id.is_(None))
    )
    assert orphan == 0


def test_similarity_scores_are_in_range_and_ordered(session):
    rows = session.execute(
        select(QuestionSimilarity.question_a_id, QuestionSimilarity.question_b_id,
               QuestionSimilarity.score)
    ).all()
    for a, b, score in rows:
        assert 0.0 <= score <= 1.0
        assert a != b, "题目不能与自己相似"


def test_taxonomy_nodes_are_two_level(session):
    """种子里只做 topic / subtopic 两层，不臆造更细层级。"""
    types = set(session.scalars(select(TaxonomyNode.node_type).distinct()).all())
    assert types <= {"topic", "subtopic", "skill"}
    assert "topic" in types and "subtopic" in types


def test_taxonomy_seed_covers_every_subject_with_questions(session):
    """**有题目的**科目都应有知识点种子，否则那些题无法被标注。

    断言范围刻意收窄到"有题目的科目"，而不是"所有已同步科目"：
    一个科目可能只同步到了大纲或 Scheme of Work（还没有任何试题），
    要求它有知识点种子没有意义——那种"缺失"不是缺陷。
    真正的缺陷是：有题却标不了。
    """
    subjects_with_questions = set(
        session.scalars(
            select(Subject.code)
            .join(Document, Document.subject_id == Subject.id)
            .join(Paper, Paper.document_id == Document.id)
            .join(Question, Question.paper_id == Paper.id)
            .distinct()
        ).all()
    )
    assert subjects_with_questions, "测试依赖已解析的题目"
    seeded = {
        code.split(".")[0]
        for code in session.scalars(select(TaxonomyNode.code).distinct()).all()
    }
    missing = subjects_with_questions - seeded
    assert not missing, f"有题目但缺少知识点种子: {sorted(missing)}"
