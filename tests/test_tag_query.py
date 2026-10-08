"""标签（spec 知识点）-> 题目查询与题目裁剪的离线回归测试。

覆盖范围：

- `tagged_questions`：board 作用域、过滤条件、`total` 不受分页影响、题干摘要；
- `tag_overview`：unit -> topic -> point 子树聚合、subject 继承、include_zero、
  code 自然排序；
- `question_crops`：qp（按当前版本 PDF 重新定位）与 ms（存储的 sha256/page/bbox）
  两条渲染路径，以及各条错误路径；
- `get_question_bundle` 附加的 `ms_regions`；
- `search-questions` 的 board + taxonomy 作用域（跨 board 同 code 不串题）；
- CLI：`tags` / `tag-questions` / `question-crop` 三个新命令。

全部用开启外键约束的内存 SQLite 与合成 PDF，不依赖本地语料与网络。
"""

from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager
from types import SimpleNamespace

import pymupdf
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from typer.testing import CliRunner

from examdata import cli
from examdata import query as query_pkg
from examdata.cli import app as cli_app
from examdata.core.models import (
    Artifact,
    Base,
    Board,
    Document,
    DocumentRevision,
    ExamSeries,
    Paper,
    Qualification,
    Question,
    QuestionTaxonomy,
    Subject,
    TaxonomyNode,
)
from examdata.query import service
from examdata.query.service import (
    QuestionFilter,
    count_questions,
    get_question_bundle,
    question_crops,
    search_questions,
    tag_overview,
    tagged_questions,
)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def configure_sqlite(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA temp_store=MEMORY")

    Base.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            yield session
    finally:
        engine.dispose()


@pytest.fixture
def corpus(db_session):
    """edexcel + cambridge 两个 board 的最小语料。

    跨 board 故意让 code `WBI11-1.2` 在两个 board 上都存在，用来钉住
    (board, code) 的作用域；另有一个 board_id 为空的旧节点保持兼容行为。
    """
    edexcel = Board(key="edexcel", name="Edexcel")
    cambridge = Board(key="cambridge", name="Cambridge")
    db_session.add_all([edexcel, cambridge])
    db_session.flush()

    qualification = Qualification(board_id=edexcel.id, key="ial", name="IAL")
    db_session.add(qualification)
    db_session.flush()
    maths = Subject(qualification_id=qualification.id, code="ial-mathematics", title="IAL Mathematics")
    biology = Subject(qualification_id=qualification.id, code="ial-biology", title="IAL Biology")
    db_session.add_all([maths, biology])
    june = ExamSeries(year=2024, session="june")
    january = ExamSeries(year=2023, session="january")
    db_session.add_all([june, january])
    db_session.flush()

    def node(code, name, node_type, *, board=None, parent=None, attrs=None, source="official"):
        return TaxonomyNode(
            board_id=board.id if board else None, parent_id=parent.id if parent else None,
            code=code, name=name, node_type=node_type, source=source, attrs=attrs or {},
        )

    unit = node("WBI11", "Unit 1", "unit", board=edexcel,
                attrs={"subject": "ial-mathematics", "unit_key": "WBI11"})
    other_unit = node("WBI12", "Unit 2", "unit", board=edexcel,
                      attrs={"subject": "ial-biology", "unit_key": "WBI12"})
    db_session.add_all([unit, other_unit])
    db_session.flush()
    topic = node("WBI11-1", "Topic 1", "topic", board=edexcel, parent=unit)
    db_session.add(topic)
    db_session.flush()
    point = node("WBI11-1.2", "Point 1.2", "point", board=edexcel, parent=topic)
    late_point = node("WBI11-1.10", "Point 1.10", "point", board=edexcel, parent=topic)
    legacy = node("WBI11-1", "Legacy Topic 1", "topic", attrs={"subject_code": "ial-mathematics"})
    cambridge_point = node("WBI11-1.2", "Cambridge Algebra", "topic", board=cambridge)
    db_session.add_all([point, late_point, legacy, cambridge_point])
    db_session.flush()

    def document(key, board, *, subject=None, series=None, year, paper_code, doc_type="question_paper"):
        return Document(
            identity_key=key, board_id=board.id, subject_id=subject.id if subject else None,
            series_id=series.id if series else None, doc_type=doc_type,
            year=year, paper_code=paper_code,
        )

    doc1 = document("edexcel-2024-1", edexcel, subject=maths, series=june, year=2024, paper_code="1")
    doc2 = document("edexcel-2023-2", edexcel, subject=maths, series=january, year=2023, paper_code="2")
    doc3 = document("cambridge-2024-1", cambridge, year=2024, paper_code="1")
    db_session.add_all([doc1, doc2, doc3])
    db_session.flush()

    def question(document, number_path, marks, stem, order):
        paper = Paper(document_id=document.id)
        db_session.add(paper)
        db_session.flush()
        q = Question(
            paper_id=paper.id, number_label=number_path.split("(")[0], number_path=number_path,
            display_order=order, marks=marks, stem_text=stem,
        )
        db_session.add(q)
        db_session.flush()
        return q

    q1 = question(doc1, "1", 4, "Solve  the equation\n  3x + 2 = 11. " + "x" * 250, 0)
    q2 = question(doc1, "2(a)", 2, "Calculate the gradient of the line.", 1)
    q3 = question(doc1, "3", 6, "Sketch the curve.", 2)
    q4 = question(doc1, "4", 5, "Prove the identity.", 3)
    q5 = question(doc2, "1", 3, "Evaluate the integral.", 0)
    q6 = question(doc3, "1", 4, "Cambridge algebra question.", 0)

    def link(question, taxonomy, *, source="auto", confidence=0.0, assigned_by=None):
        db_session.add(QuestionTaxonomy(
            question_id=question.id, node_id=taxonomy.id, source=source,
            confidence=confidence, assigned_by=assigned_by,
        ))

    link(q1, point, source="auto", confidence=0.9, assigned_by="agent")
    link(q2, point, source="manual", confidence=0.4)
    link(q3, topic, source="official", confidence=1.0)
    link(q4, unit, source="auto", confidence=0.5)
    link(q4, legacy, source="auto", confidence=0.5)
    link(q5, late_point, source="auto", confidence=0.8)
    link(q6, cambridge_point, source="auto", confidence=0.7)
    db_session.flush()
    return SimpleNamespace(
        edexcel=edexcel, cambridge=cambridge, unit=unit, other_unit=other_unit,
        topic=topic, point=point, late_point=late_point, legacy=legacy,
        cambridge_point=cambridge_point, maths=maths, biology=biology,
        q1=q1, q2=q2, q3=q3, q4=q4, q5=q5, q6=q6,
    )


# --------------------------------------------------------------------------
# tagged_questions：标签 -> 题目
# --------------------------------------------------------------------------


def test_tagged_questions_scoped_to_board_and_code(corpus, db_session):
    result = tagged_questions(db_session, board="edexcel", taxonomy_code="WBI11-1.2")
    assert result["total"] == 2
    assert [item["question_id"] for item in result["items"]] == [corpus.q1.id, corpus.q2.id]
    first = result["items"][0]
    assert first["number_path"] == "1"
    assert first["marks"] == 4
    assert first["subject_code"] == "ial-mathematics"
    assert first["year"] == 2024
    assert first["session"] == "june"
    assert first["paper_code"] == "1"
    assert first["taxonomy_code"] == "WBI11-1.2"
    assert first["taxonomy_name"] == "Point 1.2"
    assert first["confidence"] == pytest.approx(0.9)
    assert first["source"] == "auto"
    assert first["assigned_by"] == "agent"
    # cambridge 上同 code 的节点不能把 cambridge 的题带进来
    assert corpus.q6.id not in [item["question_id"] for item in result["items"]]


def test_tagged_questions_total_ignores_pagination(corpus, db_session):
    page = tagged_questions(db_session, board="edexcel", taxonomy_code="WBI11-1.2", limit=1)
    assert page["total"] == 2
    assert len(page["items"]) == 1
    second = tagged_questions(db_session, board="edexcel", taxonomy_code="WBI11-1.2", limit=1, offset=1)
    assert second["total"] == 2
    assert second["items"][0]["question_id"] == corpus.q2.id


def test_tagged_questions_filters(corpus, db_session):
    def ids(**kwargs):
        result = tagged_questions(db_session, board="edexcel", **kwargs)
        return [item["question_id"] for item in result["items"]], result["total"]

    assert ids(taxonomy_code="WBI11-1.10") == ([corpus.q5.id], 1)
    assert ids(taxonomy_code="WBI11-1.10", year_from=2024) == ([], 0)
    assert ids(taxonomy_code="WBI11-1.10", session_name="january") == ([corpus.q5.id], 1)
    assert ids(taxonomy_code="WBI11-1.10", session_name="june") == ([], 0)
    assert ids(taxonomy_code="WBI11-1.10", paper_code="2") == ([corpus.q5.id], 1)
    assert ids(taxonomy_code="WBI11-1.2", min_confidence=0.5) == ([corpus.q1.id], 1)
    assert ids(taxonomy_code="WBI11-1.2", subject_code="ial-biology") == ([], 0)
    assert ids(taxonomy_code="WBI11-1.2", subject_code="ial-mathematics") == (
        [corpus.q1.id, corpus.q2.id], 2,
    )


def test_tagged_questions_unknown_tag_is_empty(corpus, db_session):
    result = tagged_questions(db_session, board="edexcel", taxonomy_code="NOPE")
    assert result == {"total": 0, "items": []}


def test_tagged_questions_excerpt_is_flattened_and_truncated(corpus, db_session):
    result = tagged_questions(db_session, board="edexcel", taxonomy_code="WBI11-1.2")
    excerpt = result["items"][0]["stem_excerpt"]
    assert len(excerpt) == 200
    assert "\n" not in excerpt
    assert "  " not in excerpt
    assert excerpt.startswith("Solve the equation 3x + 2 = 11.")


@pytest.mark.parametrize("kwargs", [{"limit": 0}, {"limit": -1}, {"offset": -1}])
def test_tagged_questions_rejects_invalid_page(kwargs):
    with pytest.raises(ValueError):
        tagged_questions(None, board="edexcel", taxonomy_code="WBI11-1.2", **kwargs)


# --------------------------------------------------------------------------
# tag_overview：标签树与题数聚合
# --------------------------------------------------------------------------


def _find(node_list, code):
    for node in node_list:
        if node["code"] == code:
            return node
        found = _find(node["children"], code)
        if found is not None:
            return found
    return None


def test_tag_overview_aggregates_subtree_counts(corpus, db_session):
    roots = tag_overview(db_session, board="edexcel")
    assert [root["code"] for root in roots] == ["WBI11", "WBI12"]

    unit = _find(roots, "WBI11")
    assert unit["direct_questions"] == 1  # q4 直接挂在 unit 上
    assert unit["subtree_questions"] == 5  # q4 + topic 子树（q3 + q1 + q2 + q5）
    topic = _find(roots, "WBI11-1")
    assert topic["direct_questions"] == 1
    assert topic["subtree_questions"] == 4
    point = _find(roots, "WBI11-1.2")
    assert point["direct_questions"] == 2
    assert point["subtree_questions"] == 2
    assert _find(roots, "WBI11-1.10")["direct_questions"] == 1
    assert _find(roots, "WBI12")["subtree_questions"] == 0


def test_tag_overview_natural_sort_and_board_scope(corpus, db_session):
    roots = tag_overview(db_session, board="edexcel")
    topic = _find(roots, "WBI11-1")
    # `1.2` 必须排在 `1.10` 前（自然序，不是字典序）
    assert [child["code"] for child in topic["children"]] == ["WBI11-1.2", "WBI11-1.10"]
    # cambridge 上同 code 的节点不进 edexcel 的树；board 为空的旧节点也不进
    matches = []
    stack = list(roots)
    while stack:
        current = stack.pop()
        if current["code"] == "WBI11-1.2":
            matches.append(current)
        stack.extend(current["children"])
    assert [match["name"] for match in matches] == ["Point 1.2"]


def test_tag_overview_subject_filter_uses_inherited_attrs(corpus, db_session):
    maths = tag_overview(db_session, board="edexcel", subject_code="ial-mathematics")
    assert [root["code"] for root in maths] == ["WBI11"]
    assert _find(maths, "WBI11-1.2")["subtree_questions"] == 2

    biology = tag_overview(db_session, board="edexcel", subject_code="ial-biology")
    assert [root["code"] for root in biology] == ["WBI12"]
    assert _find(biology, "WBI11") is None

    assert tag_overview(db_session, board="edexcel", subject_code="ial-unknown") == []


def test_tag_overview_prunes_zero_subtrees(corpus, db_session):
    roots = tag_overview(db_session, board="edexcel", include_zero=False)
    assert [root["code"] for root in roots] == ["WBI11"]
    assert _find(roots, "WBI12") is None


def test_tag_overview_unknown_board_is_empty(db_session):
    assert tag_overview(db_session, board="nope") == []


# --------------------------------------------------------------------------
# question_crops：题目裁剪
# --------------------------------------------------------------------------


def _synthetic_pdf() -> bytes:
    """第 1 页留空，第 2 页放题号 `1`：定位算法跳过第 1 页，需 ≥2 页。"""
    doc = pymupdf.open()
    doc.new_page(width=595, height=842)
    page = doc.new_page(width=595, height=842)
    page.insert_text((50, 100), "1")
    page.insert_text((50, 160), "Solve the equation for x.")
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture
def artifacts_dir(tmp_path, monkeypatch):
    directory = tmp_path / "artifacts"
    directory.mkdir()
    monkeypatch.setattr(service, "get_settings", lambda: SimpleNamespace(artifacts_dir=directory))
    return directory


def _write_artifact(directory, storage_key: str, data: bytes) -> Artifact:
    path = directory / storage_key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return Artifact(
        sha256=hashlib.sha256(data).hexdigest(), size_bytes=len(data),
        mime="application/pdf", storage_key=storage_key,
    )


def _attach_revision(db_session, document, artifact) -> DocumentRevision:
    revision = DocumentRevision(
        document_id=document.id, artifact_id=artifact.id, revision_no=1, parse_status="parsed",
    )
    db_session.add(revision)
    db_session.flush()
    document.current_revision_id = revision.id
    db_session.flush()
    return revision


def test_question_crops_qp_relocates_on_current_revision(corpus, db_session, artifacts_dir):
    data = _synthetic_pdf()
    artifact = _write_artifact(artifacts_dir, "qp/paper.pdf", data)
    db_session.add(artifact)
    db_session.flush()
    _attach_revision(db_session, db_session.get(Document, corpus.q1.paper.document_id), artifact)

    crops = question_crops(db_session, corpus.q1.id, role="qp")
    assert len(crops) == 1
    crop = crops[0]
    assert crop["page"] == 2
    assert len(crop["bbox"]) == 4
    assert crop["bbox"][0] < crop["bbox"][2] and crop["bbox"][1] < crop["bbox"][3]
    assert crop["png"].startswith(b"\x89PNG")


def test_question_crops_qp_requires_current_revision(corpus, db_session, artifacts_dir):
    with pytest.raises(ValueError, match="当前版本"):
        question_crops(db_session, corpus.q1.id, role="qp")


def test_question_crops_qp_reports_missing_artifact_file(corpus, db_session, artifacts_dir):
    data = _synthetic_pdf()
    artifact = Artifact(
        sha256=hashlib.sha256(data).hexdigest(), size_bytes=len(data),
        mime="application/pdf", storage_key="qp/missing.pdf",
    )
    db_session.add(artifact)
    db_session.flush()
    _attach_revision(db_session, db_session.get(Document, corpus.q1.paper.document_id), artifact)
    with pytest.raises(ValueError, match="内容对象文件缺失"):
        question_crops(db_session, corpus.q1.id, role="qp")


def test_question_crops_ms_renders_stored_regions(corpus, db_session, artifacts_dir):
    data = _synthetic_pdf()
    artifact = _write_artifact(artifacts_dir, "ms/marks.pdf", data)
    db_session.add(artifact)
    db_session.flush()
    corpus.q1.attrs = {
        "ms_regions": [{"page": 2, "bbox": [50.0, 80.0, 300.0, 140.0],
                        "sha256": artifact.sha256}],
    }
    db_session.flush()

    crops = question_crops(db_session, corpus.q1.id, role="ms")
    assert len(crops) == 1
    assert crops[0]["page"] == 2
    assert crops[0]["bbox"] == (50.0, 80.0, 300.0, 140.0)
    assert crops[0]["png"].startswith(b"\x89PNG")


def test_question_crops_ms_requires_regions(corpus, db_session, artifacts_dir):
    with pytest.raises(ValueError, match="ms_regions"):
        question_crops(db_session, corpus.q2.id, role="ms")


def test_question_crops_ms_reports_unknown_sha256(corpus, db_session, artifacts_dir):
    corpus.q1.attrs = {"ms_regions": [{"page": 2, "bbox": [0, 0, 10, 10], "sha256": "f" * 64}]}
    db_session.flush()
    with pytest.raises(ValueError, match="内容对象不存在"):
        question_crops(db_session, corpus.q1.id, role="ms")


def test_question_crops_ms_reports_out_of_range_page(corpus, db_session, artifacts_dir):
    data = _synthetic_pdf()
    artifact = _write_artifact(artifacts_dir, "ms/marks.pdf", data)
    db_session.add(artifact)
    db_session.flush()
    corpus.q1.attrs = {
        "ms_regions": [{"page": 9, "bbox": [0, 0, 10, 10], "sha256": artifact.sha256}],
    }
    db_session.flush()
    with pytest.raises(ValueError, match="超出文档范围"):
        question_crops(db_session, corpus.q1.id, role="ms")


def test_question_crops_rejects_unknown_role(corpus, db_session):
    with pytest.raises(ValueError, match="role"):
        question_crops(db_session, corpus.q1.id, role="tiff")


def test_question_crops_rejects_unknown_question(db_session):
    with pytest.raises(ValueError, match="不存在"):
        question_crops(db_session, 999, role="qp")


# --------------------------------------------------------------------------
# get_question_bundle：ms_regions 附加字段
# --------------------------------------------------------------------------


def test_question_bundle_includes_ms_regions(corpus, db_session):
    regions = [{"page": 2, "bbox": [1.0, 2.0, 3.0, 4.0], "sha256": "a" * 64}]
    corpus.q1.attrs = {"ms_regions": regions}
    db_session.flush()
    bundle = get_question_bundle(db_session, corpus.q1.id)
    assert bundle["question"]["ms_regions"] == regions
    empty = get_question_bundle(db_session, corpus.q2.id)
    assert empty["question"]["ms_regions"] == []


# --------------------------------------------------------------------------
# search-questions 的 board + taxonomy 作用域
# --------------------------------------------------------------------------


def test_search_questions_board_scopes_taxonomy_code(corpus, db_session):
    both = search_questions(db_session, QuestionFilter(taxonomy_code="WBI11-1.2", limit=10))
    assert {row["question_id"] for row in both} == {corpus.q1.id, corpus.q2.id, corpus.q6.id}

    scoped = search_questions(
        db_session, QuestionFilter(board="edexcel", taxonomy_code="WBI11-1.2", limit=10)
    )
    assert {row["question_id"] for row in scoped} == {corpus.q1.id, corpus.q2.id}
    assert count_questions(
        db_session, QuestionFilter(board="edexcel", taxonomy_code="WBI11-1.2")
    ) == 2

    cambridge = search_questions(
        db_session, QuestionFilter(board="cambridge", taxonomy_code="WBI11-1.2", limit=10)
    )
    assert {row["question_id"] for row in cambridge} == {corpus.q6.id}


def test_search_questions_board_scope_keeps_null_board_nodes(corpus, db_session):
    rows = search_questions(
        db_session, QuestionFilter(board="edexcel", taxonomy_code="WBI11-1", limit=10)
    )
    # q3 来自 edexcel 的 topic，q4 来自 board_id 为空的旧节点（保持兼容）
    assert {row["question_id"] for row in rows} == {corpus.q3.id, corpus.q4.id}


# --------------------------------------------------------------------------
# CLI：tags / tag-questions / question-crop
# --------------------------------------------------------------------------


TAG_TREE = [
    {
        "id": 1, "code": "WBI11", "name": "Unit 1", "node_type": "unit",
        "direct_questions": 0, "subtree_questions": 3,
        "children": [
            {
                "id": 2, "code": "WBI11-1", "name": "Topic 1", "node_type": "topic",
                "direct_questions": 1, "subtree_questions": 3,
                "children": [
                    {"id": 3, "code": "WBI11-1.2", "name": "Point 1.2", "node_type": "point",
                     "direct_questions": 2, "subtree_questions": 2, "children": []},
                ],
            },
            {"id": 4, "code": "WBI11-9", "name": "Topic 9", "node_type": "topic",
             "direct_questions": 0, "subtree_questions": 0, "children": []},
        ],
    },
]

TAG_ITEMS = {
    "total": 2,
    "items": [
        {"question_id": 7, "number_path": "1(a)", "marks": 3,
         "subject_code": "ial-mathematics", "year": 2024, "session": "june",
         "paper_code": "1", "taxonomy_code": "WBI11-1.1", "taxonomy_name": "Point 1.1",
         "confidence": 0.9, "source": "auto", "assigned_by": "agent",
         "stem_excerpt": "Solve for x."},
    ],
}


@pytest.fixture
def cli_stubs(monkeypatch):
    @contextmanager
    def fake_session_scope():
        yield SimpleNamespace(get=lambda model, question_id: SimpleNamespace(number_path="2(a)"))

    monkeypatch.setattr(cli, "init_db", lambda: None)
    monkeypatch.setattr(cli, "session_scope", fake_session_scope)
    return monkeypatch


def test_cli_tags_json_and_search(cli_stubs):
    cli_stubs.setattr(query_pkg, "tag_overview", lambda session, **kwargs: TAG_TREE)
    result = CliRunner().invoke(cli_app, ["tags", "--board", "edexcel", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["board"] == "edexcel"
    assert payload["subject"] is None
    assert payload["total"] == 4
    assert [root["code"] for root in payload["roots"]] == ["WBI11"]

    filtered = CliRunner().invoke(cli_app, ["tags", "--search", "WBI11-1.2", "--json"])
    assert filtered.exit_code == 0, filtered.output
    payload = json.loads(filtered.output)
    assert payload["total"] == 3
    root = payload["roots"][0]
    assert [child["code"] for child in root["children"]] == ["WBI11-1"]


def test_cli_tags_table_hides_counts_on_demand(cli_stubs):
    cli_stubs.setattr(query_pkg, "tag_overview", lambda session, **kwargs: TAG_TREE)
    with_counts = CliRunner().invoke(cli_app, ["tags"])
    assert with_counts.exit_code == 0, with_counts.output
    assert "可选题数" in with_counts.output
    assert "WBI11-1.2" in with_counts.output

    without_counts = CliRunner().invoke(cli_app, ["tags", "--no-counts"])
    assert without_counts.exit_code == 0, without_counts.output
    assert "可选题数" not in without_counts.output
    assert "WBI11-1.2" in without_counts.output


def test_cli_tag_questions_json_and_table(cli_stubs):
    cli_stubs.setattr(query_pkg, "tagged_questions", lambda session, **kwargs: TAG_ITEMS)
    result = CliRunner().invoke(cli_app, ["tag-questions", "--tag", "WBI11-1.1", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload == TAG_ITEMS

    table = CliRunner().invoke(cli_app, ["tag-questions", "--tag", "WBI11-1.1"])
    assert table.exit_code == 0, table.output
    assert "1(a)" in table.output
    assert "WBI11-1.1" in table.output
    assert "0.90" in table.output


def test_cli_tag_questions_guards():
    missing = CliRunner().invoke(cli_app, ["tag-questions"])
    assert missing.exit_code == 2, missing.output
    assert "--tag" in missing.output

    bad_limit = CliRunner().invoke(cli_app, ["tag-questions", "--tag", "WBI11-1.1", "--limit", "0"])
    assert bad_limit.exit_code == 2, bad_limit.output
    assert "--limit" in bad_limit.output


def test_cli_question_crop_writes_files_and_refuses_overwrite(cli_stubs, tmp_path):
    crops = [{"page": 2, "bbox": (50.0, 80.0, 300.0, 140.0), "png": b"\x89PNG\r\n\x1a\nfake"}]
    cli_stubs.setattr(query_pkg, "question_crops", lambda session, question_id, *, role="qp": crops)
    out = tmp_path / "crops"

    result = CliRunner().invoke(cli_app, ["question-crop", "7", "--out", str(out)])
    assert result.exit_code == 0, result.output
    written = out / "q7-2_a-qp-p2.png"
    assert written.read_bytes() == crops[0]["png"]
    assert str(written) in result.output

    again = CliRunner().invoke(cli_app, ["question-crop", "7", "--out", str(out)])
    assert again.exit_code == 1, again.output
    assert "不覆盖" in again.output
    assert written.read_bytes() == crops[0]["png"]


def test_cli_question_crop_json_payload(cli_stubs, tmp_path):
    crops = [{"page": 2, "bbox": (1.0, 2.0, 3.0, 4.0), "png": b"\x89PNG"}]
    cli_stubs.setattr(query_pkg, "question_crops", lambda session, question_id, *, role="qp": crops)
    out = tmp_path / "crops"
    result = CliRunner().invoke(
        cli_app, ["question-crop", "7", "--out", str(out), "--role", "ms", "--json"]
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["question_id"] == 7
    assert payload["role"] == "ms"
    assert payload["files"] == [
        {"page": 2, "bbox": [1.0, 2.0, 3.0, 4.0], "path": str(out / "q7-2_a-ms-p2.png")},
    ]


def test_cli_question_crop_rejects_unknown_role(cli_stubs, tmp_path):
    result = CliRunner().invoke(
        cli_app, ["question-crop", "7", "--out", str(tmp_path), "--role", "tiff"]
    )
    assert result.exit_code == 1, result.output
    assert "qp 或 ms" in result.output


def test_cli_question_crop_reports_service_errors(cli_stubs, tmp_path):
    def fail(session, question_id, *, role="qp"):
        raise ValueError(f"题目 {question_id} 不存在")

    cli_stubs.setattr(query_pkg, "question_crops", fail)
    result = CliRunner().invoke(cli_app, ["question-crop", "99", "--out", str(tmp_path)])
    assert result.exit_code == 1, result.output
    assert "不存在" in result.output


def test_cli_question_crop_sanitizes_number_path(cli_stubs, tmp_path):
    @contextmanager
    def sneaky_session_scope():
        yield SimpleNamespace(
            get=lambda model, question_id: SimpleNamespace(number_path="../../evil")
        )

    cli_stubs.setattr(cli, "session_scope", sneaky_session_scope)
    cli_stubs.setattr(
        query_pkg, "question_crops",
        lambda session, question_id, *, role="qp": [
            {"page": 1, "bbox": (0.0, 0.0, 1.0, 1.0), "png": b"\x89PNG"}
        ],
    )
    out = tmp_path / "crops"
    result = CliRunner().invoke(cli_app, ["question-crop", "7", "--out", str(out)])
    assert result.exit_code == 0, result.output
    written = list(out.iterdir())
    assert len(written) == 1
    assert written[0].parent == out
    assert ".." not in written[0].name and "/" not in written[0].name and "\\" not in written[0].name
