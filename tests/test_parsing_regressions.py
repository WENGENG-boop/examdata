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
    match_numbers,
    roman_to_int,
)
from examdata.parsing.pdfdoc import (
    ImageBlock,
    PageInfo,
    PdfDocument,
    TextLine,
    _cluster_rects,
    _vector_figures,
)
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


def test_inline_numbering_chain_preserves_nested_parts():
    labels = match_numbers("6(a)(ii) Explain the method")
    assert [(item.label, item.depth) for item in labels] == [
        ("6", 0),
        ("(a)", 1),
        ("(ii)", 2),
    ]
    assert labels[-1].rest == "Explain the method"
    assert [(item.label, item.depth) for item in match_numbers("6 (ii) Find")] == [
        ("6", 0),
        ("(ii)", 2),
    ]


def test_cross_page_continuation_claims_page_and_image_once():
    image = ImageBlock(
        page=2,
        bbox=(40.0, 160.0, 160.0, 260.0),
        width=120,
        height=100,
        ext="png",
        data=b"synthetic-image",
    )
    pages = [
        PageInfo(
            number=1,
            width=600,
            height=800,
            text="1 Work out [1]",
            text_coverage=0.1,
            lines=[TextLine(1, (40, 100, 180, 115), "1 Work out [1]", 0, 0, size=12)],
        ),
        PageInfo(
            number=2,
            width=600,
            height=800,
            text="continued",
            text_coverage=0.1,
            lines=[TextLine(2, (40, 100, 180, 115), "continued", 0, 0, size=12)],
            images=[image],
        ),
    ]
    doc = PdfDocument(Path("synthetic.pdf"), page_count=2, pages=pages)
    tree = build_question_tree(doc)
    node = tree.roots[0]
    assert node.page_from == 1 and node.page_to == 2
    assert node.assets and node.assets[0].page == 2
    assert not any(f["rule"] == "pages_uncovered" for f in tree.findings)

    from examdata.parsing.segment import attach_assets

    stats = attach_assets(tree, doc)
    assert stats["images_assigned"] == 1
    assert len(node.assets) == 1


def _matrix(rows):
    return [[_cell(text, r, c) for c, text in enumerate(row)] for r, row in enumerate(rows)]


def _page(number, texts=(), *, images=()):
    return PageInfo(
        number=number,
        width=600,
        height=800,
        text="\n".join(texts),
        text_coverage=0.1,
        lines=[
            TextLine(number, (40, 100 + i * 40, 500, 115 + i * 40), text, i, 0, size=12)
            for i, text in enumerate(texts)
        ],
        images=list(images),
    )


def _document(*pages):
    return PdfDocument(Path("synthetic.pdf"), page_count=len(pages), pages=list(pages))


def _image(page, *, y=100, block_no=0):
    return ImageBlock(
        page, (50, y, 200, y + 50), width=150, height=50,
        ext="png", data=b"synthetic", block_no=block_no,
    )


@pytest.mark.parametrize(
    "text,paths,depths",
    [
        ("1(ii) Find the value [2]", ["1", "1(ii)"], [0, 2]),
        ("1 (ii) Find the value [2]", ["1", "1(ii)"], [0, 2]),
        ("1(a)(ii) Find the value [2]", ["1", "1(a)", "1(a)(ii)"], [0, 1, 2]),
        ("1 (a) (ii) Find the value [2]", ["1", "1(a)", "1(a)(ii)"], [0, 1, 2]),
        ("1(i)(ii) Find the value [2]", ["1", "1(i)", "1(i)(ii)"], [0, 1, 2]),
    ],
)
def test_inline_chain_builds_question_hierarchy(text, paths, depths):
    tree = build_question_tree(_document(_page(1, [text])))
    assert [node.number_path for node in tree.walk()] == paths
    assert [node.depth for node in tree.walk()] == depths
    assert tree.flat()[-1].marks == 2
    assert tree.total_marks == 2


def test_numbering_chain_supports_roman_nine_and_ten():
    assert roman_to_int("ix") == 9
    assert roman_to_int("x") == 10
    assert [item.label for item in match_numbers("1(a)(ix) Find")] == ["1", "(a)", "(ix)"]


@pytest.mark.parametrize(
    "rows,expected",
    [
        ([{"marks": "1\n2"}], None),
        ([{"marks": "1"}, {"marks": "2"}], None),
        ([{"marks": "2"}, {"marks": "2"}], None),
        ([{"marks": "M1\nA1"}], 2),
        ([{"marks": "M1"}, {"marks": "A1"}], 2),
        ([{"marks": "M1"}, {"partial": "A1 If 0 scored, SC1 for rounding"}], 2),
        ([{"marks": "M1"}, {"partial": "60 60"}], 1),
        ([{"partial": "2 B1 for a correct line or B1 for coordinates"}], 2),
        ([{"partial": "M1 for working or M1 for another method"}], None),
        ([{"partial": "M1 for working\nA1 for answer"}], 2),
        ([{"partial": "explanation"}, {"partial": "60 60"}], None),
        ([{"marks": "M1 or A1"}], None),
    ],
)
def test_marks_resolution_is_not_first_integer_or_all_token_sum(rows, expected):
    assert CambridgeMarkSchemeParser._resolve_marks(rows) == expected


def test_mark_scheme_duplicate_detection_counts_actual_entries():
    from examdata.markscheme.base import MarkSchemeDraft

    draft = MarkSchemeDraft()
    parser = CambridgeMarkSchemeParser()
    parser._consume_matrix(
        _matrix([
            ["Question", "Answer", "Marks", "Partial Marks"],
            ["1 (a)", "first", "2", ""],
            ["1(a)", "second", "2", ""],
        ]), draft, page_number=1,
    )
    parser._finalize(draft)
    assert draft.metadata["entry_count"] == 2
    assert draft.metadata["distinct_numbers"] == 1
    assert draft.metadata["total_marks"] is None
    finding = next(f for f in draft.findings if f["rule"] == "ms_duplicate_numbers")
    assert finding["evidence"]["counts"] == {"1(a)": 2}


@pytest.mark.parametrize("with_header", [True, False])
def test_mark_scheme_pending_entry_continues_across_page(with_header):
    from examdata.markscheme.base import MarkSchemeDraft

    draft = MarkSchemeDraft()
    parser = CambridgeMarkSchemeParser()
    header = ["Question", "Answer", "Marks", "Partial Marks"]
    parser._consume_matrix(
        _matrix([header, ["1(a)(ii)", "working", "M1", ""]]), draft, page_number=1,
    )
    rows = [["", "answer", "A1", ""], ["2", "next", "1", ""]]
    if with_header:
        rows.insert(0, header)
    parser._consume_matrix(_matrix(rows), draft, page_number=2)
    parser._finalize(draft)
    assert len(draft.entries) == 2
    assert draft.entries[0].number_path == "1(a)(ii)"
    assert draft.entries[0].marks == 2
    assert draft.entries[0].answer_text == "working answer"
    assert draft.entries[0].raw["pages"] == [1, 2]
    assert draft.metadata["total_marks"] == 3


def test_mark_scheme_pending_is_not_reused_after_page_gap_or_between_documents():
    from examdata.markscheme.base import MarkSchemeDraft

    parser = CambridgeMarkSchemeParser()
    draft = MarkSchemeDraft()
    header = ["Question", "Answer", "Marks", "Partial Marks"]
    parser._consume_matrix(_matrix([header, ["1", "working", "M1", ""]]), draft, page_number=1)
    parser._consume_matrix(_matrix([header, ["", "answer", "A1", ""]]), draft, page_number=3)
    assert draft.entries[0].marks == 1
    assert any(f["rule"] == "ms_orphan_continuation" for f in draft.findings)
    other = MarkSchemeDraft()
    parser._consume_matrix(_matrix([header, ["", "answer", "A1", ""]]), other, page_number=2)
    assert not other.entries
    assert any(f["rule"] == "ms_orphan_continuation" for f in other.findings)


def test_mark_scheme_ambiguous_marks_retains_evidence_and_unknown_total():
    from examdata.markscheme.base import MarkSchemeDraft

    draft = MarkSchemeDraft()
    parser = CambridgeMarkSchemeParser()
    parser._consume_matrix(
        _matrix([
            ["Question", "Answer", "Marks", "Partial Marks"],
            ["1", "answer", "1\n2", ""],
        ]), draft, page_number=1,
    )
    parser._finalize(draft)
    assert draft.entries[0].marks is None
    assert draft.metadata["total_marks"] is None
    finding = next(f for f in draft.findings if f["rule"] == "ms_marks_ambiguous")
    assert finding["evidence"]["rows"] == [{"marks": "1\n2", "partial": ""}]


def test_mark_scheme_parent_and_child_marks_are_not_blindly_summed():
    from examdata.markscheme.base import MarkSchemeDraft

    draft = MarkSchemeDraft()
    parser = CambridgeMarkSchemeParser()
    parser._consume_matrix(
        _matrix([
            ["Question", "Answer", "Marks", "Partial Marks"],
            ["1", "parent", "5", ""],
            ["1(a)", "child", "2", ""],
        ]), draft, page_number=1,
    )
    parser._finalize(draft)
    assert [entry.marks for entry in draft.entries] == [5, 2]
    assert draft.metadata["total_marks"] is None
    assert any(f["rule"] == "ms_parent_child_marks_ambiguous" for f in draft.findings)


def test_question_duplicate_path_is_diagnosed_without_discarding_evidence():
    tree = build_question_tree(_document(_page(1, [
        "1 Find the value", "(a) first answer [2]", "(a) second answer [2]",
    ])))
    assert [node.number_path for node in tree.walk()] == ["1", "1(a)", "1(a)"]
    assert tree.total_marks is None
    finding = next(f for f in tree.findings if f["rule"] == "duplicate_number_paths")
    assert finding["evidence"]["counts"] == {"1(a)": 2}


@pytest.mark.parametrize(
    "texts,total,ambiguous",
    [
        (["1 Work out [5]", "(a) Explain", "(b) Draw"], 5, False),
        (["1 Work out", "(a) Explain [2]", "(b) Draw [3]"], 5, False),
        (["1 Work out [5]", "(a) Explain [2]", "(b) Draw [3]"], 5, False),
        (["1 Work out [5]", "(a) Explain [2]", "(b) Draw"], None, True),
        (["1 Work out [5]", "(a) Explain [2]", "(b) Draw [4]"], None, True),
    ],
)
def test_question_parent_marks_preserved_without_double_count(texts, total, ambiguous):
    tree = build_question_tree(_document(_page(1, texts)))
    assert tree.total_marks == total
    assert any(f["rule"] == "parent_child_marks_ambiguous" for f in tree.findings) is ambiguous
    assert tree.roots[0].marks == (5 if "[5]" in texts[0] else None)


def test_incomplete_question_marks_do_not_claim_complete_total():
    tree = build_question_tree(_document(_page(1, ["1 Explain [2]", "2 Draw the diagram"])))
    assert tree.total_marks is None
    assert any(f["rule"] == "marks_incomplete" for f in tree.findings)


def test_image_only_continuation_page_extends_last_open_node():
    doc = _document(
        _page(1, ["1 Work out", "(a) Explain [2]", "(b) Draw [3]"]),
        _page(2, images=[_image(2)]),
        _page(3, ["2 Finish [1]"]),
    )
    tree = build_question_tree(doc)
    owner = next(node for node in tree.walk() if node.number_path == "1(b)")
    assert owner.page_to == 2
    assert tree.roots[0].page_to == 2
    assert [asset.page for asset in owner.assets] == [2]
    assert tree.asset_stats["images_orphan"] == 0
    assert not any(f["rule"] == "pages_uncovered" for f in tree.findings)


def test_image_before_next_page_question_stays_with_previous_question():
    doc = _document(
        _page(1, ["1 Explain [2]"]),
        _page(2, ["2 Draw [3]"], images=[_image(2, y=70)]),
    )
    tree = build_question_tree(doc)
    assert len(tree.roots[0].assets) == 1
    assert not tree.roots[1].assets
    assert tree.roots[0].page_to == 2


def test_continuation_image_uses_last_node_not_older_deeper_part():
    tree = build_question_tree(_document(
        _page(1, ["1 Work out", "(a)(ii) Explain [2]", "(b) Draw [3]"]),
        _page(2, images=[_image(2)]),
    ))
    by_path = {node.number_path: node for node in tree.walk()}
    assert by_path["1(b)"].assets
    assert not by_path["1(a)(ii)"].assets


def test_attach_assets_is_idempotent_for_front_matter_and_orphans():
    from examdata.parsing.segment import attach_assets

    doc = _document(
        _page(1, ["Read these instructions", "You will need:"], images=[_image(1)]),
        _page(2, images=[_image(2)]),
        _page(3, ["1 Work out [2]"], images=[_image(3, y=200)]),
        _page(4),
    )
    tree = build_question_tree(doc)
    assert tree.asset_stats == {
        "images_total": 3, "images_assigned": 1, "images_front_matter": 1,
        "images_orphan": 1, "orphan_pages": [2],
    }
    initial_stats = tree.asset_stats
    assert attach_assets(tree, doc) == initial_stats
    assert len(tree.front_assets) == 1
    assert len(tree.roots[0].assets) == 1
    assert len([f for f in tree.findings if f["rule"] == "orphan_assets"]) == 1
    uncovered = next(f for f in tree.findings if f["rule"] == "pages_uncovered")
    assert uncovered["evidence"]["pages"] == [2, 4]


def test_mark_scheme_cross_page_pdf_pipeline(tmp_path):
    import pymupdf
    from examdata.parsing.pdfdoc import load_pdf

    path = tmp_path / "cross-page-ms.pdf"
    pdf = pymupdf.open()
    rows_by_page = [
        [["Question", "Answer", "Marks", "Partial Marks"], ["1(a)(ii)", "working", "M1", ""]],
        [["", "answer", "A1", ""], ["2", "next", "1", ""]],
    ]
    edges = [30, 110, 300, 365, 565]
    for rows in rows_by_page:
        page = pdf.new_page(width=600, height=800)
        ys = [80 + i * 60 for i in range(len(rows) + 1)]
        for x in edges:
            page.draw_line((x, ys[0]), (x, ys[-1]))
        for y in ys:
            page.draw_line((edges[0], y), (edges[-1], y))
        for r, row in enumerate(rows):
            for c, text in enumerate(row):
                if text:
                    page.insert_text((edges[c] + 4, ys[r] + 25), text, fontsize=10)
    pdf.save(path)
    pdf.close()
    draft = CambridgeMarkSchemeParser().parse(load_pdf(path))
    assert [(entry.number_path, entry.marks) for entry in draft.entries] == [("1(a)(ii)", 2), ("2", 1)]
    assert draft.entries[0].answer_text == "working answer"
    assert draft.entries[0].raw["pages"] == [1, 2]
    assert draft.metadata["total_marks"] == 3
