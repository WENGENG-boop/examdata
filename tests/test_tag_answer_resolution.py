"""答案解析（评分标准条目 -> 题目）测试。

覆盖范围：

- 纯函数 `resolve_answer` 的四条分支：exact / ancestor / descendants / none（合成数据，
  不依赖本地语料）；
- 真实库端到端：取真实标签的一页题走 `tagged_questions`，断言精确关联题拿到答案文本、
  来源分布合理；数据库来自 conftest 的私有副本，只读；
- CLI 表格模式的「答案」列与截断规则。

真实库用例在没有已解析语料时自动跳过（`require_parsed_data`）。
"""

from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select
from typer.testing import CliRunner

from examdata import cli
from examdata import query as query_pkg
from examdata.cli import app as cli_app
from examdata.query.service import AnswerEntry, resolve_answer


def entry(entry_id: int, path: str, text: str | None) -> AnswerEntry:
    return AnswerEntry(entry_id, path, text)


# --------------------------------------------------------------------------
# 纯函数：exact / ancestor / descendants / none
# --------------------------------------------------------------------------


def test_resolve_answer_prefers_exact_entry():
    exact = [entry(1, "1(a)", "42")]
    answer = resolve_answer(
        "1(a)",
        exact_entries=exact,
        entries_by_path={"1(a)": exact, "1": [entry(2, "1", "parent text")]},
    )
    assert answer == {
        "source": "exact",
        "text": "42",
        "number_path": "1(a)",
        "entry_ids": [1],
    }


def test_resolve_answer_prefers_official_answer_over_mark_scheme():
    answer = resolve_answer(
        "1(a)",
        exact_entries=[entry(1, "1(a)", "ms text")],
        entries_by_path={"1(a)": [entry(1, "1(a)", "ms text")]},
        official_entries=[entry(9, "", "official text")],
    )
    assert answer is not None
    assert answer["source"] == "exact"
    assert answer["text"] == "official text"
    assert answer["entry_ids"] == [9]


def test_resolve_answer_uses_nearest_ancestor():
    entries_by_path = {
        "1": [entry(1, "1", "whole question")],
        "1(a)": [entry(2, "1(a)", "part a")],
        "2": [entry(3, "2", "other question")],
    }
    answer = resolve_answer("1(a)(i)", entries_by_path=entries_by_path)
    assert answer is not None
    assert answer["source"] == "ancestor"
    assert answer["number_path"] == "1(a)"
    assert answer["text"] == "part a"
    assert answer["entry_ids"] == [2]


def test_resolve_answer_skips_blank_entries_and_keeps_climbing():
    """空白答案文本视为缺失：最近祖先没有可用文本时继续往上找。"""
    entries_by_path = {
        "1": [entry(1, "1", "root text")],
        "1(a)": [entry(2, "1(a)", "   ")],
    }
    answer = resolve_answer("1(a)(i)", entries_by_path=entries_by_path)
    assert answer is not None
    assert answer["source"] == "ancestor"
    assert answer["number_path"] == "1"
    assert answer["text"] == "root text"


def test_resolve_answer_aggregates_descendants_in_tree_order():
    entries_by_path = {
        "1(a)": [entry(1, "1(a)", "alpha")],
        "1(b)": [entry(2, "1(b)", "beta")],
        "1(b)(i)": [entry(3, "1(b)(i)", "bi")],
        "1(b)(ii)": [entry(4, "1(b)(ii)", "bii")],
        # 前缀相同但不是子题（"10(a)" 不属于 "1"），必须排除
        "10(a)": [entry(5, "10(a)", "not a descendant")],
    }
    answer = resolve_answer("1", entries_by_path=entries_by_path)
    assert answer is not None
    assert answer["source"] == "descendants"
    assert answer["number_path"] == "1"
    assert answer["text"] == "(a) alpha\n\n(b) beta\n\n(b)(i) bi\n\n(b)(ii) bii"
    assert answer["entry_ids"] == [1, 2, 3, 4]


def test_resolve_answer_descendant_order_handles_roman_labels_and_gaps():
    """中间层没有条目时也要沿父链下钻；罗马数字子标签按数值排序。"""
    entries_by_path = {
        "2(a)(iv)": [entry(1, "2(a)(iv)", "four")],
        "2(a)(v)": [entry(2, "2(a)(v)", "five")],
        "2(a)(x)": [entry(3, "2(a)(x)", "ten")],
    }
    answer = resolve_answer("2", entries_by_path=entries_by_path)
    assert answer is not None
    assert answer["source"] == "descendants"
    assert answer["text"] == "(a)(iv) four\n\n(a)(v) five\n\n(a)(x) ten"
    assert answer["entry_ids"] == [1, 2, 3]


def test_resolve_answer_returns_none_without_any_match():
    entries_by_path = {"1": [entry(1, "1", "other question")], "1(a)": [entry(2, "1(a)", "x")]}
    assert resolve_answer("3(b)", entries_by_path=entries_by_path) is None
    assert resolve_answer("3(b)") is None


# --------------------------------------------------------------------------
# 真实库端到端
# --------------------------------------------------------------------------


def _busiest_tags(session, limit: int) -> list[str]:
    """取 edexcel 下题量最多的若干标签 code，避免把测试钉死在某个会变的标签上。"""
    from examdata.core.models import Board, QuestionTaxonomy, TaxonomyNode

    rows = session.execute(
        select(TaxonomyNode.code, func.count(QuestionTaxonomy.id))
        .join(QuestionTaxonomy, QuestionTaxonomy.node_id == TaxonomyNode.id)
        .join(Board, Board.id == TaxonomyNode.board_id)
        .where(Board.key == "edexcel")
        .group_by(TaxonomyNode.id)
        .order_by(func.count(QuestionTaxonomy.id).desc())
        .limit(limit)
    ).all()
    assert rows, "edexcel 没有任何标签链接"
    return [row[0] for row in rows]


def _busiest_tag(session) -> str:
    return _busiest_tags(session, 1)[0]


def test_tagged_questions_attach_answers_on_real_corpus(require_parsed_data):
    """真实标签的一页题：精确关联题必须带出答案文本，来源分布要合理。"""
    from examdata.core.db import session_scope
    from examdata.core.models import MarkSchemeEntry
    from examdata.query import tagged_questions

    with session_scope() as session:
        code = _busiest_tag(session)
        result = tagged_questions(session, board="edexcel", taxonomy_code=code, limit=50)
        items = result["items"]
        assert items, f"标签 {code} 没有题目"

        # 每题都带 answer 键；精确直连的条目必须解析成 exact 且文本对得上
        question_ids = [item["question_id"] for item in items]
        linked = {}
        for question_id, path, text in session.execute(
            select(
                MarkSchemeEntry.question_id,
                MarkSchemeEntry.number_path,
                MarkSchemeEntry.answer_text,
            ).where(MarkSchemeEntry.question_id.in_(question_ids))
        ):
            if (text or "").strip():
                linked.setdefault(question_id, []).append((path, text.strip()))

        answered = 0
        for item in items:
            assert "answer" in item
            answer = item["answer"]
            if answer is None:
                assert item["question_id"] not in linked
                continue
            answered += 1
            assert answer["source"] in {"exact", "ancestor", "descendants"}
            assert answer["text"].strip()
            assert answer["number_path"]
            assert answer["entry_ids"]
            for _path, text in linked.get(item["question_id"], ()):
                assert answer["source"] == "exact"
                assert text in answer["text"]

        # 这一页至少有一半题能关联到答案，且至少有一题是精确关联
        assert answered >= len(items) / 2
        assert any(item["answer"] and item["answer"]["source"] == "exact" for item in items)


def test_tagged_questions_answers_stay_within_own_paper(require_parsed_data):
    """答案条目必须属于题目自己的 QP 文档（或直连题号），不得跨卷串入。

    回归：`_page_answers` 曾把同一页里所有文档的 MS 条目合并按题号索引，
    混卷页面上别的卷同题号条目会被当成答案（WME01-4.2 的 60659 曾混入
    56804 的「beam」条目）。
    """
    from examdata.core.db import session_scope
    from examdata.core.models import MarkScheme, MarkSchemeEntry, Paper, Question
    from examdata.query import tagged_questions

    with session_scope() as session:
        checked = 0
        for code in _busiest_tags(session, 3):
            result = tagged_questions(session, board="edexcel", taxonomy_code=code, limit=50)
            for item in result["items"]:
                answer = item["answer"]
                if not answer:
                    continue
                question = session.get(Question, item["question_id"])
                paper = session.get(Paper, question.paper_id)
                doc_id = paper.document_id
                for entry_id in answer["entry_ids"]:
                    entry_question_id, entry_doc_id = session.execute(
                        select(MarkSchemeEntry.question_id, MarkScheme.matched_paper_document_id)
                        .join(MarkScheme, MarkSchemeEntry.mark_scheme_id == MarkScheme.id)
                        .where(MarkSchemeEntry.id == entry_id)
                    ).one()
                    assert entry_question_id == item["question_id"] or entry_doc_id == doc_id, (
                        f"标签 {code} 题目 {item['question_id']} 的答案条目 {entry_id} 来自其他试卷"
                        f"（entry_qid={entry_question_id}, entry_ms_doc={entry_doc_id}, qp_doc={doc_id}）"
                    )
                    checked += 1
        assert checked > 0


# --------------------------------------------------------------------------
# CLI：答案列
# --------------------------------------------------------------------------


@pytest.fixture
def cli_stubs(monkeypatch):
    @contextmanager
    def fake_session_scope():
        yield SimpleNamespace()

    monkeypatch.setattr(cli, "init_db", lambda: None)
    monkeypatch.setattr(cli, "session_scope", fake_session_scope)
    return monkeypatch


def test_answer_cell_truncates_and_flattens():
    from examdata.cli import _answer_cell

    assert _answer_cell(None) == ""
    assert _answer_cell({"source": "exact", "text": "42"}) == "[exact] 42"
    assert _answer_cell({"source": "ancestor", "text": " a\n  b "}) == "[ancestor] a b"
    long_text = "x" * 100
    assert _answer_cell({"source": "descendants", "text": long_text}) == (
        "[descendants] " + "x" * 60 + "..."
    )


def test_cli_tag_questions_table_shows_answer(cli_stubs):
    result_payload = {
        "total": 1,
        "items": [
            {
                "question_id": 7, "number_path": "1(a)", "marks": 3,
                "subject_code": "ial-mathematics", "year": 2024, "session": "june",
                "paper_code": "1", "taxonomy_code": "WBI11-1.1", "taxonomy_name": "Point 1.1",
                "confidence": 0.9, "source": "auto", "assigned_by": "agent",
                "stem_excerpt": "Solve for x.",
                "answer": {"source": "exact", "text": "42", "number_path": "1(a)",
                           "entry_ids": [11]},
            },
        ],
    }
    cli_stubs.setattr(query_pkg, "tagged_questions", lambda session, **kwargs: result_payload)
    table = CliRunner().invoke(
        cli_app, ["tag-questions", "--tag", "WBI11-1.1"], env={"COLUMNS": "200"}
    )
    assert table.exit_code == 0, table.output
    assert "答案" in table.output
    assert "[exact] 42" in table.output

    # 未解析出答案时留空，不显示来源前缀
    result_payload["items"][0]["answer"] = None
    empty = CliRunner().invoke(cli_app, ["tag-questions", "--tag", "WBI11-1.1"])
    assert empty.exit_code == 0, empty.output
    assert "[exact]" not in empty.output
