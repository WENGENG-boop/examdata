"""examdata.tagging 测试：自建临时 SQLite 库，不依赖真实语料，也不触碰真实数据库。"""

from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from examdata.core.models import (
    Base,
    Board,
    Document,
    Paper,
    Question,
    QuestionTaxonomy,
    Qualification,
    Subject,
    TaxonomyNode,
)
from examdata.tagging import (
    ASSIGNED_BY,
    Bm25Index,
    CorpusSet,
    Doc,
    PointCandidate,
    QuestionRef,
    TagCandidate,
    assign,
    confidence_scores,
    doc_for,
    evaluate_cambridge,
    iter_questions,
    load_points,
    rank_question,
    select_tags,
    tokenize,
    unit_code_from_paper,
)
from examdata.tagging.assign import write_review_files
from examdata.tagging.bm25 import idf
from examdata.tagging.text import term_counts


# ---------------------------------------------------------------------------
# 测试语料
#
# edexcel：一个科目 wbi11，两个单元；WBI11 三个内容点，WBI12 一个。
#   q1 淀粉+糖原（同分并列 → 第二标签 + 低置信）、q2 无关词（unassigned）、
#   q3 空题干（skipped_empty）、q4 在 WBI12 里问淀粉（单元约束）、
#   q5 无科目（skipped_no_subject）、q6 无单元问 DNA（退化为全科目）。
# cambridge：两个 subtopic 种子；cq1 关键词与 BM25 分歧，cq2 两边一致。
# ---------------------------------------------------------------------------


def _seed(session: Session) -> dict[str, int]:
    ids: dict[str, int] = {}

    edexcel = Board(key="edexcel", name="Pearson Edexcel")
    cambridge = Board(key="cambridge", name="Cambridge International")
    session.add_all([edexcel, cambridge])
    session.flush()

    edexcel_qual = Qualification(board_id=edexcel.id, key="ial", name="International A Level")
    cam_qual = Qualification(board_id=cambridge.id, key="igcse", name="IGCSE")
    session.add_all([edexcel_qual, cam_qual])
    session.flush()

    biology = Subject(
        qualification_id=edexcel_qual.id, code="wbi11", title="Biology", slug="wbi11"
    )
    maths = Subject(qualification_id=cam_qual.id, code="0580", title="Mathematics", slug=None)
    session.add_all([biology, maths])
    session.flush()

    def node(board_id, code, name, node_type, parent=None, attrs=None):
        row = TaxonomyNode(
            board_id=board_id,
            parent_id=parent.id if parent is not None else None,
            code=code,
            name=name,
            node_type=node_type,
            source="official",
            attrs=dict(attrs or {}),
        )
        session.add(row)
        session.flush()
        return row

    point_attrs = {"subject": "wbi11", "text": ""}
    unit11 = node(edexcel.id, "WBI11", "Unit 1", "unit")
    topic11 = node(edexcel.id, "WBI11-1", "Biological molecules", "topic", unit11)
    sub11 = node(edexcel.id, "WBI11-1.1", "Molecules", "subtopic", topic11)
    p1 = node(edexcel.id, "WBI11-1.1.1", "The structure of starch as a polysaccharide", "point", sub11, point_attrs)
    p2 = node(edexcel.id, "WBI11-1.1.2", "The structure of glycogen as a polysaccharide", "point", sub11, point_attrs)
    p3 = node(edexcel.id, "WBI11-1.1.3", "The structure of triglycerides", "point", sub11, point_attrs)
    unit12 = node(edexcel.id, "WBI12", "Unit 2", "unit")
    topic12 = node(edexcel.id, "WBI12-1", "Genes and health", "topic", unit12)
    sub12 = node(edexcel.id, "WBI12-1.1", "DNA", "subtopic", topic12)
    p4 = node(edexcel.id, "WBI12-1.1.1", "The structure of DNA nucleotides", "point", sub12, point_attrs)
    ids.update(p1=p1.id, p2=p2.id, p3=p3.id, p4=p4.id)

    def document(board_id, subject_id, identity_key, paper_code):
        row = Document(
            board_id=board_id,
            subject_id=subject_id,
            identity_key=identity_key,
            doc_type="question_paper",
            paper_code=paper_code,
            year=2024,
        )
        session.add(row)
        session.flush()
        return row

    def question(paper, label, stem):
        row = Question(
            paper_id=paper.id,
            number_label=label,
            number_path=label,
            display_order=int(label),
            stem_text=stem,
            marks=1,
        )
        session.add(row)
        session.flush()
        return row

    doc_a = document(edexcel.id, biology.id, "wbi11-01-qp", "mock-01")
    paper_a = Paper(document_id=doc_a.id, attrs={"unit_code": "WBI11"})
    session.add(paper_a)
    session.flush()
    q1 = question(paper_a, "1", "Describe the structure of starch and glycogen as polysaccharides.")
    q2 = question(paper_a, "2", "zzzz qqqq")
    q3 = question(paper_a, "3", "")

    doc_b = document(edexcel.id, biology.id, "wbi12-01-qp", "wbi12-01")
    paper_b = Paper(document_id=doc_b.id, attrs={})
    session.add(paper_b)
    session.flush()
    q4 = question(paper_b, "4", "Describe the structure of starch as a polysaccharide.")

    doc_c = document(edexcel.id, None, "unlinked-01-qp", "unlinked-01")
    paper_c = Paper(document_id=doc_c.id, attrs={})
    session.add(paper_c)
    session.flush()
    q5 = question(paper_c, "5", "Describe the structure of starch as a polysaccharide.")

    doc_d = document(edexcel.id, biology.id, "mock-extra-qp", "mock-paper")
    paper_d = Paper(document_id=doc_d.id, attrs={})
    session.add(paper_d)
    session.flush()
    q6 = question(paper_d, "6", "The structure of DNA nucleotides")
    ids.update(q1=q1.id, q2=q2.id, q3=q3.id, q4=q4.id, q5=q5.id, q6=q6.id)

    c_topic1 = node(cambridge.id, "0580.1", "Number", "topic", attrs={"subject_code": "0580"})
    c_sub14 = node(
        cambridge.id, "0580.1.4", "Estimation and limits of accuracy", "subtopic",
        c_topic1, {"subject_code": "0580"},
    )
    c_topic5 = node(cambridge.id, "0580.5", "Geometry", "topic", attrs={"subject_code": "0580"})
    c_sub51 = node(
        cambridge.id, "0580.5.1", "Perimeter and area", "subtopic",
        c_topic5, {"subject_code": "0580"},
    )
    ids.update(csub14=c_sub14.id, csub51=c_sub51.id, ctopic1=c_topic1.id)

    c_doc = document(cambridge.id, maths.id, "0580-s24-11-qp", "0580_s24_11")
    c_paper = Paper(document_id=c_doc.id, attrs={})
    session.add(c_paper)
    session.flush()
    cq1 = question(c_paper, "1", "Estimate the perimeter of the shape.")
    cq2 = question(c_paper, "2", "Work out the area of the rectangle.")
    ids.update(cq1=cq1.id, cq2=cq2.id)

    session.add_all(
        [
            QuestionTaxonomy(
                question_id=cq1.id, node_id=c_sub14.id, source="auto",
                confidence=0.9, assigned_by="keyword-v1", reviewed=False,
            ),
            QuestionTaxonomy(
                question_id=cq1.id, node_id=c_topic1.id, source="auto",
                confidence=0.81, assigned_by="keyword-v1", reviewed=False,
            ),
            QuestionTaxonomy(
                question_id=cq2.id, node_id=c_sub51.id, source="auto",
                confidence=0.9, assigned_by="keyword-v1", reviewed=False,
            ),
        ]
    )
    session.flush()
    return ids


@pytest.fixture()
def seeded(tmp_path):
    engine = create_engine("sqlite:///" + (tmp_path / "tagging.db").as_posix())
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        ids = _seed(session)
        session.commit()
        yield session, ids
    engine.dispose()


def _taxonomy_rows(session: Session, board_key: str = "edexcel") -> list[QuestionTaxonomy]:
    stmt = (
        select(QuestionTaxonomy)
        .join(Question, Question.id == QuestionTaxonomy.question_id)
        .join(Paper, Paper.id == Question.paper_id)
        .join(Document, Document.id == Paper.document_id)
        .join(Board, Board.id == Document.board_id)
        .where(Board.key == board_key)
        .order_by(QuestionTaxonomy.question_id, QuestionTaxonomy.node_id)
    )
    return list(session.scalars(stmt))


def _point(node_id, code, name, subject="bio", unit="U1", ancestors=()):
    return PointCandidate(
        node_id=node_id, code=code, name=name, text="",
        subject=subject, unit_code=unit, ancestors=tuple(ancestors),
    )


# ---------------------------------------------------------------------------
# text
# ---------------------------------------------------------------------------


def test_tokenize_normalizes_case_and_plurals():
    assert tokenize(
        "The PLANTS are 42 x a studies classes analysis focus photos photosynthesis"
    ) == ["plant", "study", "class", "analysis", "focus", "photos", "photosynthesis"]


def test_tokenize_nfkc_and_underscore():
    assert tokenize("ＢＭ２５ foo_bar") == ["bm25", "foo", "bar"]


def test_tokenize_empty_inputs():
    assert tokenize(None) == []
    assert tokenize("") == []


def test_stopwords_match_before_folding():
    # "marks" 在停用词表里，即使折叠后是 "mark" 也整体丢弃
    assert tokenize("marks plants") == ["plant"]


def test_term_counts_deduplicates():
    assert term_counts("starch starch glycogen") == {"starch": 1, "glycogen": 1}


# ---------------------------------------------------------------------------
# bm25
# ---------------------------------------------------------------------------


def test_bm25_returns_only_matching_docs_descending():
    index = Bm25Index(
        [
            Doc("A", {"name": (3.0, "starch polysaccharide")}),
            Doc("B", {"name": (3.0, "glycogen lipid")}),
        ]
    )
    ranked = index.score("starch")
    assert [key for key, _ in ranked] == ["A"]
    assert ranked[0][1] > 0
    assert index.best("glycogen")[0] == "B"
    assert index.score("zzz") == []
    assert index.keys == ["A", "B"]
    assert len(index) == 2


def test_bm25_ties_order_by_key():
    index = Bm25Index(
        [
            Doc("B", {"name": (3.0, "starch")}),
            Doc("A", {"name": (3.0, "starch")}),
        ]
    )
    ranked = index.score("starch")
    assert [key for key, _ in ranked] == ["A", "B"]
    assert ranked[0][1] == ranked[1][1]


def test_bm25_name_weight_beats_ancestor_weight():
    index = Bm25Index(
        [
            Doc("name", {"name": (3.0, "starch")}),
            Doc("ancestor", {"name": (3.0, "lipid"), "ancestors": (1.0, "starch")}),
        ]
    )
    scores = dict(index.score("starch"))
    assert scores["name"] > scores["ancestor"] > 0


def test_bm25_empty_index_and_idf_positive():
    index = Bm25Index([])
    assert len(index) == 0
    assert index.avgdl == 0.0
    assert index.score("starch") == []
    assert index.best("starch") is None
    assert idf(10, 10) > 0
    assert idf(10, 1) > idf(10, 9)


# ---------------------------------------------------------------------------
# corpus
# ---------------------------------------------------------------------------


def test_unit_code_from_paper_variants():
    assert unit_code_from_paper({"unit_code": "wbi11"}, None) == "WBI11"
    assert unit_code_from_paper({"unit_code": " wbi12 "}, "mock-01") == "WBI12"
    assert unit_code_from_paper({}, "wbi11-01") == "WBI11"
    assert unit_code_from_paper(None, "WBI11/01") == "WBI11"
    assert unit_code_from_paper({}, "mock-01") is None
    assert unit_code_from_paper({"unit_code": ""}, None) is None
    assert unit_code_from_paper({"unit_code": 123}, None) is None
    assert unit_code_from_paper(None, None) is None


def test_doc_for_weights_and_optional_text():
    point = PointCandidate(
        node_id=1, code="X", name="Name here", text="",
        subject="s", unit_code=None, ancestors=("Anc",),
    )
    doc = doc_for(point)
    assert doc.key == "X"
    assert doc.fields["name"] == (3.0, "Name here")
    assert doc.fields["ancestors"] == (1.0, "Anc")
    assert "text" not in doc.fields

    with_text = PointCandidate(
        node_id=2, code="Y", name="Name", text="Full sentence",
        subject="s", unit_code=None, ancestors=(),
    )
    assert doc_for(with_text).fields["text"] == (1.0, "Full sentence")


def test_resolve_subject_prefers_unit():
    corpora = CorpusSet(
        [_point(1, "P1", "Alpha", subject="bio", unit="U1"),
         _point(2, "P2", "Beta", subject="chem", unit="U2")]
    )
    assert corpora.resolve_subject(unit_code="U2", subject_candidates=["bio"]) == "chem"
    assert corpora.resolve_subject(unit_code="U9", subject_candidates=["bio"]) == "bio"
    assert corpora.resolve_subject(unit_code=None, subject_candidates=[None, "BIO "]) == "bio"
    assert corpora.resolve_subject(unit_code=None, subject_candidates=["nope"]) is None


def test_rank_question_respects_unit_scope_and_fallback():
    corpora = CorpusSet(
        [_point(1, "P1", "Starch structure", unit="U1"),
         _point(2, "P2", "DNA nucleotides", unit="U2")]
    )
    scoped = QuestionRef(
        question_id=1, number_label="1", stem_text="Describe DNA nucleotides.",
        paper_code=None, subject_code="bio", subject_slug=None, unit_code="U1",
    )
    subject, candidates = rank_question(corpora, scoped)
    assert subject == "bio"
    assert candidates == []  # DNA 点在 U2，被单元约束排除

    fallback = QuestionRef(
        question_id=2, number_label="2", stem_text="Describe DNA nucleotides.",
        paper_code=None, subject_code="bio", subject_slug=None, unit_code=None,
    )
    subject, candidates = rank_question(corpora, fallback)
    assert subject == "bio"
    assert candidates[0].code == "P2"
    assert candidates[0].confidence > 0

    unknown = QuestionRef(
        question_id=3, number_label="3", stem_text="anything",
        paper_code=None, subject_code=None, subject_slug=None, unit_code=None,
    )
    assert rank_question(corpora, unknown) == (None, [])


def test_load_points_resolves_units_subjects_and_ancestors(seeded):
    session, _ = seeded
    points = load_points(session)
    assert [point.code for point in points] == [
        "WBI11-1.1.1", "WBI11-1.1.2", "WBI11-1.1.3", "WBI12-1.1.1",
    ]
    first = points[0]
    assert first.subject == "wbi11"
    assert first.unit_code == "WBI11"
    assert first.ancestors == ("Molecules", "Biological molecules", "Unit 1")
    assert points[3].unit_code == "WBI12"
    assert points[3].ancestors == ("DNA", "Genes and health", "Unit 2")


def test_load_points_missing_board(seeded):
    session, _ = seeded
    assert load_points(session, board_key="nonexistent") == []


def test_load_points_unit_key_fallback(tmp_path):
    engine = create_engine("sqlite:///" + (tmp_path / "fallback.db").as_posix())
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        board = Board(key="edexcel", name="Edexcel")
        session.add(board)
        session.flush()
        session.add(
            TaxonomyNode(
                board_id=board.id, code="ORPHAN-1.1", name="Orphan point",
                node_type="point", source="official",
                attrs={"subject": "wbi11", "unit_key": "wbi12"},
            )
        )
        session.flush()
        points = load_points(session)
        assert len(points) == 1
        assert points[0].unit_code == "WBI12"
        assert points[0].ancestors == ()
    engine.dispose()


def test_iter_questions_subject_filter_and_limit(seeded):
    session, _ = seeded
    all_rows = iter_questions(session)
    assert [row.number_label for row in all_rows] == ["1", "2", "3", "4", "5", "6"]
    assert all_rows[0].unit_code == "WBI11"  # paper.attrs
    assert all_rows[3].unit_code == "WBI12"  # paper_code 前缀
    assert all_rows[4].subject_code is None
    assert all_rows[5].unit_code is None

    filtered = iter_questions(session, subject="wbi11")
    assert [row.number_label for row in filtered] == ["1", "2", "3", "4", "6"]
    assert [row.number_label for row in iter_questions(session, limit=2)] == ["1", "2"]


# ---------------------------------------------------------------------------
# assign：纯函数
# ---------------------------------------------------------------------------


def test_confidence_scores_formula_and_clamp():
    assert confidence_scores([]) == []
    assert confidence_scores([45.0]) == [1.0]  # 超过标定点被截到 1
    assert confidence_scores([0.0]) == [0.0]
    assert confidence_scores([15.0, 15.0]) == [0.65, 0.65]  # margin=0 → 只有绝对份
    assert confidence_scores([7.5]) == [0.5]


def test_confidence_scores_monotonic_non_increasing():
    scores = confidence_scores([12.0, 9.0, 3.0])
    assert scores == [0.59, 0.53, 0.2]
    assert all(0.0 <= value <= 1.0 for value in scores)
    clamped = confidence_scores([2.0, 1.9])  # 第二名 raw 更高 → 压回第一名
    assert clamped[0] == pytest.approx(0.089, abs=1e-4)
    assert clamped[1] <= clamped[0]


def test_select_tags_second_tag_rules():
    def cand(code, score):
        return TagCandidate(code=code, node_id=hash(code) % 100, name=code, score=score, confidence=0.5)

    assert select_tags([]) == []
    assert len(select_tags([cand("A", 10.0)])) == 1
    assert len(select_tags([cand("A", 10.0), cand("B", 9.0)])) == 2
    assert len(select_tags([cand("A", 10.0), cand("B", 8.0)])) == 1  # 8 < 0.85*10
    assert len(select_tags([cand("A", 0.49), cand("B", 0.49)])) == 1  # top-1 未达 min_score
    chosen = select_tags([cand("A", 10.0), cand("B", 9.5), cand("C", 9.4)])
    assert [item.code for item in chosen] == ["A", "B"]  # 只看前两名


def test_write_review_files_sanitizes_and_sorts(tmp_path):
    entries = [
        {"question_id": 2, "subject": "a/b", "top_confidence": 0.1},
        {"question_id": 1, "subject": "a/b", "top_confidence": 0.2},
    ]
    written = write_review_files(entries, review_dir=tmp_path)
    assert written == [str(tmp_path / "a_b.jsonl")]
    lines = (tmp_path / "a_b.jsonl").read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["question_id"] for line in lines] == [1, 2]


# ---------------------------------------------------------------------------
# assign：落库
# ---------------------------------------------------------------------------


def test_assign_dry_run_has_no_side_effects(seeded, tmp_path):
    session, _ = seeded
    review_dir = tmp_path / "review"
    stats = assign(session, dry_run=True, review_dir=review_dir)

    assert stats["board"] == "edexcel"
    assert stats["dry_run"] is True
    assert stats["scanned"] == 6
    assert stats["tagged"] == 3
    assert stats["assigned"] == 4
    assert stats["second_tags"] == 1
    assert stats["unassigned"] == 1
    assert stats["skipped_empty"] == 1
    assert stats["skipped_no_subject"] == 1
    assert stats["low_confidence"] == 3
    assert stats["score_distribution"]["n"] == 3
    assert len(stats["review_samples"]) == 3
    assert stats["review_sample_cap"] == 20
    assert stats["review_files"] == []
    assert not review_dir.exists()
    assert _taxonomy_rows(session) == []


def test_assign_write_persists_rows_and_review_files(seeded, tmp_path):
    session, ids = seeded
    review_dir = tmp_path / "review"
    stats = assign(session, dry_run=False, review_dir=review_dir)
    session.commit()

    assert stats["dry_run"] is False
    assert stats["assigned"] == 4
    rows = _taxonomy_rows(session)
    assert len(rows) == 4
    for row in rows:
        assert row.source == "auto"
        assert row.assigned_by == ASSIGNED_BY
        assert row.reviewed is False
        assert row.confidence > 0

    q1_rows = [row for row in rows if row.question_id == ids["q1"]]
    assert [row.node_id for row in q1_rows] == [ids["p1"], ids["p2"]]
    assert q1_rows[0].confidence == pytest.approx(0.1346, abs=2e-4)
    assert q1_rows[1].confidence == q1_rows[0].confidence

    path = review_dir / "wbi11.jsonl"
    assert stats["review_files"] == [str(path)]
    entries = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert {entry["question_id"] for entry in entries} == {ids["q1"], ids["q4"], ids["q6"]}
    top1 = next(entry for entry in entries if entry["question_id"] == ids["q1"])
    assert [cand["code"] for cand in top1["candidates"]] == [
        "WBI11-1.1.1", "WBI11-1.1.2", "WBI11-1.1.3",
    ]


def test_assign_skips_manual_and_existing_questions(seeded, tmp_path):
    session, ids = seeded
    assign(session, dry_run=False, review_dir=tmp_path / "r1")
    session.commit()
    session.add(
        QuestionTaxonomy(
            question_id=ids["q1"], node_id=ids["p3"], source="manual",
            confidence=1.0, assigned_by="human", reviewed=True,
        )
    )
    session.commit()

    stats = assign(session, dry_run=False, review_dir=tmp_path / "r2")
    session.commit()
    assert stats["scanned"] == 6
    assert stats["skipped_manual"] == 1
    assert stats["skipped_existing"] == 2
    assert stats["assigned"] == 0
    assert stats["tagged"] == 0
    assert stats["unassigned"] == 1
    assert len(_taxonomy_rows(session)) == 5  # 4 条旧 auto + 1 条 manual，原样保留
    assert stats["review_files"] == []


def test_assign_replace_keeps_manual_and_is_idempotent(seeded, tmp_path):
    session, ids = seeded
    assign(session, dry_run=False, review_dir=tmp_path / "r1")
    session.commit()
    session.add(
        QuestionTaxonomy(
            question_id=ids["q1"], node_id=ids["p3"], source="manual",
            confidence=1.0, assigned_by="human", reviewed=True,
        )
    )
    session.commit()

    stats = assign(session, dry_run=False, replace=True, review_dir=tmp_path / "r2")
    session.commit()
    assert stats["replaced"] == 4  # q1 两条 + q4 + q6
    rows = _taxonomy_rows(session)
    assert len(rows) == 5
    manual = [row for row in rows if row.source == "manual"]
    assert len(manual) == 1
    assert manual[0].node_id == ids["p3"]
    assert manual[0].reviewed is True

    again = assign(session, dry_run=False, replace=True, review_dir=tmp_path / "r3")
    session.commit()
    assert again["replaced"] == 4
    assert len(_taxonomy_rows(session)) == 5


def test_assign_replace_never_writes_manual_nodes(seeded, tmp_path):
    # manual 先占住 q1 的第一候选点；唯一约束 (question_id, node_id) 不含 source，
    # 所以自动结果只能退到第二候选点。
    session, ids = seeded
    session.add(
        QuestionTaxonomy(
            question_id=ids["q1"], node_id=ids["p1"], source="manual",
            confidence=1.0, assigned_by="human", reviewed=True,
        )
    )
    session.commit()

    stats = assign(session, dry_run=False, replace=True, review_dir=tmp_path / "r1")
    session.commit()
    assert stats["replaced"] == 0  # 还没有自动行可删
    assert stats["assigned"] == 3  # q1 只写 p2；q4、q6 各一条
    q1_rows = [row for row in _taxonomy_rows(session) if row.question_id == ids["q1"]]
    by_node = {row.node_id: row for row in q1_rows}
    assert by_node[ids["p1"]].source == "manual"
    assert by_node[ids["p1"]].reviewed is True
    assert by_node[ids["p2"]].source == "auto"
    assert len(q1_rows) == 2

    again = assign(session, dry_run=False, replace=True, review_dir=tmp_path / "r2")
    session.commit()
    assert again["replaced"] == 3  # q1 p2 + q4 p4 + q6 p4
    q1_rows = [row for row in _taxonomy_rows(session) if row.question_id == ids["q1"]]
    assert len(q1_rows) == 2
    assert {row.node_id: row.source for row in q1_rows} == {
        ids["p1"]: "manual", ids["p2"]: "auto",
    }


def test_assign_subject_filter_and_limit(seeded):
    session, _ = seeded
    assert assign(session, subject="wbi11", dry_run=True)["scanned"] == 5
    assert assign(session, subject="wbi11", limit=2, dry_run=True)["scanned"] == 2
    unknown = assign(session, subject="nonexistent", dry_run=True)
    assert unknown["scanned"] == 0
    assert unknown["assigned"] == 0


# ---------------------------------------------------------------------------
# cambridge 只读对照
# ---------------------------------------------------------------------------


def test_evaluate_cambridge_read_only_and_metrics(seeded):
    session, _ = seeded
    before = len(_taxonomy_rows(session, "cambridge"))
    assert before == 3

    report = evaluate_cambridge(session, examples=10)

    assert report["board"] == "cambridge"
    assert report["candidates"] == 2
    assert report["subjects"] == ["0580"]
    assert report["questions"] == 2
    assert report["bm25_assigned"] == 2
    assert report["bm25_coverage"] == 1.0
    assert report["keyword_assigned"] == 2
    assert report["keyword_coverage"] == 1.0
    assert report["both"] == 2
    assert report["agree_top1"] == 1
    assert report["agreement_strict"] == 0.5
    assert report["agree_any"] == 0
    assert report["agreement_lenient"] == 0.5
    assert report["agree_top3"] == 1
    assert report["agreement_top3"] == 0.5
    assert report["bm25_only"] == 0
    assert report["keyword_only"] == 0
    assert report["neither"] == 0
    assert report["keyword_methods"] == ["keyword-v1"]
    assert report["per_subject"]["0580"]["agreement_strict"] == 0.5
    assert len(report["disagreements"]) == 1
    sample = report["disagreements"][0]
    assert sample["keyword_top1"]["code"] == "0580.1.4"
    assert sample["bm25_top1"]["code"] == "0580.5.1"

    assert evaluate_cambridge(session, examples=0)["disagreements"] == []
    assert len(_taxonomy_rows(session, "cambridge")) == before  # 只读
