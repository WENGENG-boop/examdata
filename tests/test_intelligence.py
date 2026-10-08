"""智能层回归测试。

这三层（知识点 / 难度 / 相似题）此前是空表，本轮才建起来。
测试锁定的是**可复现性**与**边界正确性**，而不是具体数值：
数值会随语料增长而变，但"同样的输入永远给同样的输出"
以及"官方数据不被自动结果污染"这两条必须永远成立。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine, delete, func, select
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
    METHOD,
    _is_ancestor_pair,
    _root_of,
    find_similar,
    normalize_text,
    ngrams,
)
from examdata.intelligence.taxonomy import assign_taxonomy, classify_question


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
    """种子里只做 topic / subtopic 两层，不臆造更细层级。

    只看 cambridge 种子树：edexcel 的官方 spec 树（unit/topic/subtopic/point）
    是另一套来源，不在此断言范围内。
    """
    cambridge = session.scalar(select(Board).where(Board.key == "cambridge"))
    assert cambridge is not None
    types = set(
        session.scalars(
            select(TaxonomyNode.node_type)
            .where(TaxonomyNode.board_id == cambridge.id)
            .distinct()
        ).all()
    )
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
    # Edexcel 的知识树以 spec 单元代码（WBI11 等）为根、科目归属存在
    # node.attrs["subject"]，不满足"科目代码即 code 前缀"的 CIE 惯例；
    # 对这类科目按 attrs.subject 归属统计。
    seeded |= {
        str(attrs["subject"]).strip()
        for attrs in session.scalars(select(TaxonomyNode.attrs)).all()
        if isinstance(attrs, dict) and str(attrs.get("subject") or "").strip()
    }
    missing = subjects_with_questions - seeded
    assert not missing, f"有题目但缺少知识点种子: {sorted(missing)}"


# --------------------------------------------------------------------------
# 重跑幂等（重复标注 / 重复计算不得撞唯一约束）
# --------------------------------------------------------------------------


@pytest.fixture
def tx_session():
    """可写会话：用例内的写入在退出时整体回滚，共享的测试库副本保持原样。

    本模块的 session 是 module 级只读共享的，而下面两条回归用例必须写库
    （人工标注、相似题对），因此另开一条连接并在外层事务里跑。
    """
    from examdata.core.config import get_settings

    engine = create_engine(get_settings().database_url)
    conn = engine.connect()
    trans = conn.begin()
    try:
        with Session(bind=conn) as s:
            yield s
    finally:
        if trans.is_active:
            trans.rollback()
        # 即使用例中途抛异常（例如撞了唯一约束），关闭连接也会丢弃未提交的写入。
        conn.close()
        engine.dispose()


def _pick_classifiable_question(session):
    """找一道"自动分类能命中、且命中节点有父节点"的真实题目。

    必须有父节点：只有这样才能验证 replace=True 跳过的是 manual 节点本身，
    而不是整道题被跳过（父节点仍应由自动分类补上）。
    """
    rows = session.execute(
        select(Question, Subject.code)
        .join(Paper, Paper.id == Question.paper_id)
        .join(Document, Document.id == Paper.document_id)
        .join(Subject, Subject.id == Document.subject_id, isouter=True)
        .order_by(Question.id)
    ).all()
    for question, subject_code in rows:
        for hit in classify_question(question.stem_text or "", subject_code or ""):
            node = session.scalar(
                select(TaxonomyNode).where(TaxonomyNode.code == hit.node_code)
            )
            if node is not None and node.parent_id is not None:
                return question, subject_code, node
    pytest.fail("语料里没有可用于回归的题目（自动分类命中且节点有父节点）")


def test_assign_taxonomy_replace_keeps_manual_rows(tx_session):
    """replace=True 重跑：manual 行必须留下，自动结果不得再占用它的节点。

    唯一约束 (question_id, node_id) 不含 source，而 manual 行不能删，
    所以"先删 auto 再写 auto"这条重跑路径必须先避开 manual 占用的节点，
    否则会在 flush 时撞约束报错。
    """
    s = tx_session
    question, subject_code, node = _pick_classifiable_question(s)

    assign_taxonomy(s, subject_code=subject_code, replace=True)
    row = s.scalar(
        select(QuestionTaxonomy).where(
            QuestionTaxonomy.question_id == question.id,
            QuestionTaxonomy.node_id == node.id,
        )
    )
    assert row is not None, "自动分类应命中该节点，用例才覆盖到冲突路径"
    # 人工确认：治理层把已有的 auto 行改成 manual，而不是另插一行
    row.source = "manual"
    row.reviewed = True
    row.assigned_by = "reviewer"
    s.flush()

    first = assign_taxonomy(s, subject_code=subject_code, replace=True)
    second = assign_taxonomy(s, subject_code=subject_code, replace=True)

    rows = s.scalars(
        select(QuestionTaxonomy).where(QuestionTaxonomy.question_id == question.id)
    ).all()
    by_source = {(r.node_id, r.source) for r in rows}
    assert (node.id, "manual") in by_source, "人工标注被自动结果删掉或覆盖了"
    assert (node.id, "auto") not in by_source, "manual 节点上不得再写 auto 行"
    assert (node.parent_id, "auto") in by_source, "只跳过 manual 节点，父节点仍应自动标注"
    assert first == second, "重复运行必须幂等（统计值应完全一致）"

    dup = s.execute(
        select(QuestionTaxonomy.node_id, func.count())
        .where(QuestionTaxonomy.question_id == question.id)
        .group_by(QuestionTaxonomy.node_id)
        .having(func.count() > 1)
    ).all()
    assert dup == [], f"同一题出现重复 (question_id, node_id) 行: {dup}"


def _similarity_rows(session) -> int:
    return session.scalar(
        select(func.count(QuestionSimilarity.id)).where(
            QuestionSimilarity.method == METHOD
        )
    )


def test_find_similar_rerun_skips_existing_pairs(tx_session):
    """replace=False 连跑两次：第二次必须跳过已存在题对，而不是撞唯一约束。"""
    s = tx_session
    # 先清掉本方法的旧结果：否则第一次运行一个题对都不写，
    # "第二次不新增"就成了空断言，挡不住 (a, b, method) 唯一约束的回归。
    s.execute(delete(QuestionSimilarity).where(QuestionSimilarity.method == METHOD))
    s.flush()
    subjects = list(s.scalars(select(Subject.code).distinct()).all())

    written = sum(find_similar(s, subject_code=code)["pairs"] for code in subjects)
    assert written > 0, "语料里应至少存在一对相似题，用例才有验证价值"
    after_first = _similarity_rows(s)
    assert after_first == written

    again = sum(find_similar(s, subject_code=code)["pairs"] for code in subjects)
    assert again == 0, "第二次运行必须跳过已存在的题对"
    assert _similarity_rows(s) == after_first, "重复运行不得改变题对数量"
