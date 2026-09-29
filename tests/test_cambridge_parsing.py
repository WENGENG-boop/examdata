"""Cambridge 解析端到端测试（基于真实试卷样本）。

这些测试锁定已验证的解析行为：
- 0580/11 June 2024 试卷：25 道题，1..25 连续，总分 56（与封面声明一致）
- 对应 Mark Scheme：34 条评分条目，分值合计 56，与试卷 100% 关联

若解析器改动导致这些数字变化，说明产生了回归。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from examdata.markscheme.cambridge import (
    CambridgeMarkSchemeParser,
    link_entries_to_questions,
    normalize_chars,
    normalize_number_path,
)
from examdata.parsing.metadata import extract_paper_metadata
from examdata.parsing.pdfdoc import load_pdf
from examdata.parsing.segment import build_question_tree

FIXTURES = Path(__file__).parent / "fixtures"
QP = FIXTURES / "0580_qp_11.pdf"
MS = FIXTURES / "0580_ms_11.pdf"

pytestmark = pytest.mark.skipif(
    not QP.exists() or not MS.exists(), reason="需要真实试卷样本 fixtures"
)


# --------------------------------------------------------------------------
# 封面元数据
# --------------------------------------------------------------------------


def test_paper_metadata_from_cover():
    doc = load_pdf(QP)
    md = extract_paper_metadata(doc)
    assert md.subject_code == "0580"
    assert md.paper_code == "11"
    assert md.component == "1"
    assert md.variant == "1"
    assert md.session == "june"
    assert md.year == 2024
    assert md.duration_minutes == 60
    assert md.total_marks == 56
    assert md.declared_page_count == 12


# --------------------------------------------------------------------------
# 题目切分
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def qp_tree():
    doc = load_pdf(QP)
    md = extract_paper_metadata(doc)
    return build_question_tree(doc, expected_total_marks=md.total_marks), doc


def test_question_count_and_sequence(qp_tree):
    tree, _doc = qp_tree
    assert len(tree.roots) == 25
    # 题号必须是从 1 开始的连续序列
    assert tree.top_number_sequence == list(range(1, 26))
    assert [int(q.label) for q in tree.roots] == list(range(1, 26))


def test_marks_reconcile_with_declared_total(qp_tree):
    tree, _doc = qp_tree
    assert tree.total_marks == 56
    assert not [f for f in tree.findings if f["rule"] == "marks_total_mismatch"]


def test_no_numbering_gaps(qp_tree):
    tree, _doc = qp_tree
    gaps = [f for f in tree.findings if f["rule"] == "numbering_gap"]
    assert gaps == [], f"出现题号缺口: {gaps}"


def test_subquestion_hierarchy(qp_tree):
    """小问层级必须恢复，且父子路径正确。"""
    tree, _doc = qp_tree
    by_path = {q.number_path: q for q in tree.walk()}
    assert "1(a)" in by_path
    assert "1(b)" in by_path
    assert "1(c)" in by_path
    q1 = by_path["1"]
    assert [c.number_path for c in q1.children] == ["1(a)", "1(b)", "1(c)"]
    # 有 2 个小问的题
    assert [c.number_path for c in by_path["3"].children] == ["3(a)", "3(b)"]
    assert [c.number_path for c in by_path["25"].children] == ["25(a)", "25(b)"]


def test_axis_labels_are_not_questions(qp_tree):
    """Q3 含行程图，坐标轴刻度不得被误判为题目。"""
    tree, _doc = qp_tree
    assert len(tree.roots) == 25
    # 坐标轴刻度若被误判成题目，会留下"无正文且无小问"的空题目
    empty = [q.number_path for q in tree.roots if not q.text.strip() and not q.children]
    assert empty == [], f"出现空题目（疑似误判）: {empty}"


def test_cross_page_question_is_merged(qp_tree):
    """Q25 跨页（p10 -> p12），必须合并为一个题目而非按页切开。"""
    tree, _doc = qp_tree
    q25 = next(q for q in tree.roots if q.label == "25")
    assert q25.page_from == 10
    assert q25.page_to is not None and q25.page_to >= 11


def test_front_matter_is_excluded(qp_tree):
    tree, _doc = qp_tree
    assert 1 in tree.front_matter_pages
    # 封面上的 "1 hour" 不得成为题目 1
    q1 = next(q for q in tree.roots if q.label == "1")
    assert "hour" not in (q1.text or "").lower()


def test_bold_signal_detected(qp_tree):
    tree, _doc = qp_tree
    assert tree.bold_signal_available is True


# --------------------------------------------------------------------------
# Mark Scheme
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def ms_draft():
    doc = load_pdf(MS)
    return CambridgeMarkSchemeParser().parse(doc)


def test_mark_scheme_entries(ms_draft):
    assert len(ms_draft.entries) == 34
    assert ms_draft.metadata["distinct_numbers"] == 34


def test_mark_scheme_marks_reconcile_with_paper(ms_draft, qp_tree):
    """Mark Scheme 分值合计必须等于试卷总分 —— 两份独立文件的交叉校验。"""
    tree, _doc = qp_tree
    assert ms_draft.metadata["total_marks"] == 56
    assert ms_draft.metadata["total_marks"] == tree.total_marks


def test_multi_mark_entries_resolved(ms_draft):
    """多分行分值必须跨续行累加（Q14 = M1 + A1 = 2，Q22 = M1+A1+A1 = 3）。"""
    by_path = {e.number_path: e for e in ms_draft.entries}
    assert by_path["14"].marks == 2
    assert by_path["22"].marks == 3
    assert by_path["8"].marks == 2
    assert by_path["10"].marks == 4
    assert by_path["25(b)"].marks == 4
    assert by_path["25(a)"].marks == 3


def test_mark_scheme_entries_have_confidence(ms_draft):
    assert all(e.parse_confidence >= 0.6 for e in ms_draft.entries)
    high = [e for e in ms_draft.entries if e.parse_confidence >= 0.95]
    assert len(high) >= 30


def test_link_entries_to_questions(ms_draft, qp_tree):
    """评分条目必须能挂到具体题目/小问。"""
    tree, _doc = qp_tree

    class Q:
        def __init__(self, node, qid):
            self.id = qid
            self.number_path = node.number_path

    questions = [Q(n, i + 1) for i, n in enumerate(tree.walk())]
    linked, unmatched, without = link_entries_to_questions(ms_draft.entries, questions)
    assert len(linked) == len(ms_draft.entries)
    assert unmatched == []


def test_link_fuzzy_fallback():
    """MS 给出更深层级时应回退到最近的祖先题。"""
    from examdata.markscheme.base import MarkSchemeEntryDraft

    class Q:
        def __init__(self, qid, path):
            self.id = qid
            self.number_path = path

    questions = [Q(1, "3"), Q(2, "3(a)")]
    entries = [MarkSchemeEntryDraft(number_label="3(a)(ii)", number_path="3(a)(ii)")]
    linked, unmatched, _without = link_entries_to_questions(entries, questions)
    assert len(linked) == 1
    assert linked[0][1] == 2  # 回退到 3(a)
    assert unmatched == []


# --------------------------------------------------------------------------
# 工具函数
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [("1 (a)", "1(a)"), ("3(b)", "3(b)"), ("2", "2"), ("25 (b)", "25(b)")],
)
def test_normalize_number_path(raw, expected):
    assert normalize_number_path(raw) == expected


def test_normalize_chars_fixes_symbol_font():
    # Cambridge 符号字体把减号放在私有区
    assert normalize_chars("12\uf02d") == "12-"
