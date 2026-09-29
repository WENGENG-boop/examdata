"""解析回归测试：锁定本轮修复的行为。

覆盖四类此前会静默出错、且已被真实数据验证的缺陷：

1. **Mark Scheme 横排版式**（2025 specimen）：表头在行、题号在列。
   旧实现会把 "Question" 当成题号，整页只产出 1 条条目。
2. **矢量图形抽取**：Cambridge 试卷内嵌位图为 0，图形全由绘图指令构成，
   必须聚类 + 渲染，否则题目拆分后丢失完成该题所需的图。
3. **小问标签歧义**：(i)/(v)/(x) 既是字母也是罗马数字，必须按同级序列消歧，
   否则题号路径会重复、层级错乱。
4. **独立分值行**：分值常单独占一行（"[2]"），必须补挂到当前题目，
   否则总分系统性偏低。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from examdata.markscheme.cambridge import CambridgeMarkSchemeParser
from examdata.parsing.numbering import (
    int_to_roman,
    is_ambiguous_sub_label,
    roman_to_int,
)
from examdata.parsing.pdfdoc import _cluster_rects, _vector_figures
from examdata.parsing.segment import (
    _AMBIGUOUS_PREDECESSOR,
    _is_preceding_letter,
    _looks_roman,
    build_question_tree,
)
from examdata.parsing.tables import TableCell, detect_grid, fill_cells

FIXTURES = Path(__file__).parent / "fixtures"


# --------------------------------------------------------------------------
# 1. 横排 Mark Scheme 表格
# --------------------------------------------------------------------------


def _cell(text: str, row: int, col: int) -> TableCell:
    return TableCell(column=col, row=row, text=text, bbox=(0.0, 0.0, 0.0, 0.0))


def _transposed_matrix() -> list[list[TableCell]]:
    """复刻 2025 specimen Mark Scheme 的真实版式：题号在列、表头在行。"""
    rows = [
        ["Partial Marks", "", "", ""],
        ["Marks", "1", "1", "2"],
        ["Answer", "2125", "17 900", "36"],
        ["Question", "1(a)", "1(b)", "3"],
    ]
    return [[_cell(t, r, c) for c, t in enumerate(row)] for r, row in enumerate(rows)]


def test_transposed_header_is_detected():
    matrix = _transposed_matrix()
    assert CambridgeMarkSchemeParser._is_transposed(matrix) is True


def test_transposed_matrix_is_flipped_to_normal_layout():
    matrix = _transposed_matrix()
    flipped = CambridgeMarkSchemeParser._maybe_transpose(matrix)
    header = CambridgeMarkSchemeParser._find_header(flipped)
    assert header is not None, "转置后必须能定位到表头"
    q_col, a_col, m_col, g_col = header
    assert q_col == 0
    labels = [row[q_col].text for row in flipped]
    assert "Question" in labels
    assert labels[labels.index("Question") + 1] == "1(a)"


def test_normal_matrix_is_not_transposed():
    """常规竖排表不得被误判为横排。"""
    rows = [
        ["Question", "Answer", "Marks", "Partial Marks"],
        ["1(a)", "2125", "1", ""],
    ]
    matrix = [[_cell(t, r, c) for c, t in enumerate(row)] for r, row in enumerate(rows)]
    assert CambridgeMarkSchemeParser._is_transposed(matrix) is False
    assert CambridgeMarkSchemeParser._maybe_transpose(matrix) is matrix


def test_specimen_mark_scheme_entries_are_extracted():
    """真实 2025 specimen Mark Scheme：必须解析出全部题目条目。

    旧实现下这份文件产出 0 条条目（表头被判成题号后整页只有 1 条）。
    """
    from examdata.parsing.pdfdoc import load_pdf

    specimen = FIXTURES / "0580_ms_01_specimen.pdf"
    if not specimen.exists():
        pytest.skip("需要 2025 specimen Mark Scheme 样本")

    draft = CambridgeMarkSchemeParser().parse(load_pdf(specimen))
    assert len(draft.entries) >= 40
    paths = [e.number_path for e in draft.entries]
    assert paths[0] == "1(a)"
    assert "1(c)" in paths
    # 分值合计应等于封面声明的 80 分
    assert draft.metadata["total_marks"] == 80


# --------------------------------------------------------------------------
# 2. 矢量图形抽取
# --------------------------------------------------------------------------


def test_rect_clustering_merges_adjacent_segments():
    """一条曲线被拆成多段时，必须聚成一个包围盒。"""
    rects = [[0, 0, 10, 10], [10, 0, 20, 10], [20, 0, 30, 10]]
    boxes = _cluster_rects(rects, gap=1.0)
    assert len(boxes) == 1
    assert boxes[0] == [0, 0, 30, 10]


def test_rect_clustering_keeps_distant_shapes_separate():
    rects = [[0, 0, 10, 10], [200, 300, 210, 310]]
    boxes = _cluster_rects(rects, gap=8.0)
    assert len(boxes) == 2


def test_vector_figure_thresholds_reject_rules_and_decorations():
    """贯穿页面的表格线必须被排除；图形本身必须被保留。"""
    pymupdf = pytest.importorskip("pymupdf")

    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)

    # 一条贯穿整页的竖线 + 一条横线：表格/分栏线，不是图形
    shape = page.new_shape()
    shape.draw_line((300, 0), (300, 840))
    shape.finish()
    shape.draw_line((0, 400), (595, 400))
    shape.finish()
    # 一个 200x120 的矩形：真正的图形
    shape.draw_rect(pymupdf.Rect(150, 100, 350, 220))
    shape.finish()
    shape.commit()

    figures = _vector_figures(page, 0)
    assert len(figures) == 1, f"应只保留 1 个图形，实际 {len(figures)}"
    fig = figures[0]
    assert fig.source == "vector"
    assert fig.ext == "png"
    assert fig.width >= 200
    assert len(fig.data) > 0
    doc.close()


# --------------------------------------------------------------------------
# 3. 小问标签歧义
# --------------------------------------------------------------------------


@pytest.mark.parametrize("label", ["(i)", "(v)", "(x)"])
def test_ambiguous_labels_detected(label):
    assert is_ambiguous_sub_label(label) is True


@pytest.mark.parametrize("label", ["(a)", "(h)", "(ii)", "(iv)", "1"])
def test_unambiguous_labels(label):
    assert is_ambiguous_sub_label(label) is False


def test_ambiguous_predecessor_mapping():
    assert _AMBIGUOUS_PREDECESSOR == {"i": "h", "v": "u", "x": "w"}


def test_preceding_letter_disambiguates_alpha_subquestion():
    """(h) 之后的 (i) 是字母小问；(a) 之后的 (i) 是罗马数字子小问。"""
    assert _is_preceding_letter("(h)", "(i)") is True
    assert _is_preceding_letter("(a)", "(i)") is False
    assert _is_preceding_letter("(u)", "(v)") is True
    assert _is_preceding_letter("(b)", "(v)") is False


def test_roman_detection():
    assert _looks_roman("(i)") is True
    assert _looks_roman("(iv)") is True
    assert _looks_roman("(h)") is False
    assert roman_to_int("iv") == 4
    assert int_to_roman(4) == "iv"
    assert int_to_roman(99) is None


# --------------------------------------------------------------------------
# 4. 题号路径唯一性与分值完整性（真实试卷）
# --------------------------------------------------------------------------

QP = FIXTURES / "0580_qp_11.pdf"

pytestmark_qp = pytest.mark.skipif(not QP.exists(), reason="需要真实试卷样本")


@pytestmark_qp
def test_question_paths_are_unique():
    """题号路径是题目级检索与 MS 关联的键，必须唯一。"""
    from examdata.parsing.metadata import extract_paper_metadata
    from examdata.parsing.pdfdoc import load_pdf

    doc = load_pdf(QP)
    md = extract_paper_metadata(doc)
    tree = build_question_tree(doc, expected_total_marks=md.total_marks)
    paths = [n.number_path for n in tree.walk()]
    assert len(paths) == len(set(paths)), f"出现重复题号路径: {paths}"


@pytestmark_qp
def test_standalone_mark_line_is_attributed():
    """分值单独成行时也必须计入题目分值，总分要对得上封面声明。"""
    from examdata.parsing.metadata import extract_paper_metadata
    from examdata.parsing.pdfdoc import load_pdf

    doc = load_pdf(QP)
    md = extract_paper_metadata(doc)
    tree = build_question_tree(doc, expected_total_marks=md.total_marks)
    assert tree.total_marks == md.total_marks
    assert not [f for f in tree.findings if f["rule"] == "marks_total_mismatch"]
