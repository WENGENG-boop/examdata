"""样本卷 9709_m26_qp_12.pdf 的端到端与单元测试。

样本卷不在本机时整模块跳过；数字（11 题 / 19 标记 / 15 图 / 尺寸）是设计文档
第 10 节的完成契约，全部来自实测，不用推断值。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import crop_questions as C

SAMPLE = Path("C:/Users/weo/Desktop/api/examdata/tmpwork/paperqa-live/python-0/9709_m26_qp_12.pdf")

pytestmark = pytest.mark.skipif(not SAMPLE.is_file(), reason="样本卷 9709_m26_qp_12.pdf 不在本机")


# ---------------------------------------------------------------- 单元测试（合成数据，不依赖样本）

def test_dot_row_classification():
    spans = [
        (94.0, 100.0, 300.0, 101.0, "." * 40),   # 缩进点线（题内答题区）
        (72.4, 200.0, 500.0, 201.0, "." * 40),   # 整栏点线（附加页）
        (94.0, 300.0, 300.0, 301.0, "abc"),      # 太短，不算
    ]
    assert C.dot_rows(spans) == [(100.0, 94.0), (200.0, 72.4)]
    assert C.page_signature(spans) == {"dot_rows": 2, "indented": 1, "fullwidth": 1}


def test_marker_pair_filter():
    spans = [
        (94.0, 100.0, 116.0, 110.0, "(@#"),  # 只出现 1 次 → 噪声被过滤
        (94.0, 200.0, 116.0, 210.0, "(x)"),
        (94.0, 300.0, 116.0, 310.0, "(x)"),
        (94.0, 400.0, 116.0, 410.0, "(y)"),
    ]
    kept, label_of, pairs = C.find_markers([spans])
    assert [c["core"] for c in kept] == ["(x)", "(x)", "(y)"]
    assert label_of == {"(x)": "a", "(y)": "b"}
    assert pairs[("(", "#")] == 1


def test_question_segments_same_page_cut():
    tokens = [{"page": 0, "y0": 60.0, "x0": 72.0, "x1": 80.0, "raw": "1"},
              {"page": 0, "y0": 400.0, "x0": 72.0, "x1": 80.0, "raw": "2"}]
    sigs = [{"dot_rows": 0, "indented": 0, "fullwidth": 0}]
    qs = C.question_segments(tokens, [], sigs, 1, 56.9, 735.2)
    assert qs[0]["segs"] == [(0, 56.9, 398.0)]
    assert qs[1]["segs"] == [(0, 56.9, 735.2)]


# ---------------------------------------------------------------- 样本卷集成测试

@pytest.fixture(scope="module")
def doc():
    import pymupdf
    d = pymupdf.open(SAMPLE)
    yield d
    d.close()


@pytest.fixture(scope="module")
def ana(doc):
    return C.analyze(doc)


def test_pages_tokens_questions(ana):
    assert ana["npages"] == 16
    assert ana["rotations"] == [0]
    assert len(ana["tokens"]) == 11
    pages = [(q["segs"][0][0] + 1, q["segs"][-1][0] + 1) for q in ana["questions"]]
    assert pages[0] == (3, 3)      # Q1 在 p3
    assert pages[9] == (12, 13)    # Q10 跨 p12-13
    assert pages[10] == (14, 15)   # Q11 跨 p14-15


def test_subpart_markers(ana):
    assert len(ana["markers"]) == 19
    counts = [len(q["subparts"]) for q in ana["questions"]]
    assert counts == [0, 2, 2, 2, 2, 2, 2, 2, 0, 2, 3]
    assert [s["label"] for s in ana["questions"][10]["subparts"]] == ["a", "b", "c"]


def test_crop_box(ana):
    left, top, right, bot = ana["box"]
    assert left == pytest.approx(62.4, abs=0.15)
    assert top == pytest.approx(56.9, abs=0.15)
    assert right == pytest.approx(550.8, abs=0.15)
    assert bot == pytest.approx(735.2, abs=0.15)


def test_additional_page_excluded(ana):
    sig16 = ana["sigs"][15]  # p16
    assert sig16["fullwidth"] >= C.DOT_ROWS_MIN and sig16["indented"] == 0
    assert ana["questions"][-1]["end"] == 14  # 末题结束于 p15


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    out = tmp_path_factory.mktemp("cie-crops-out")
    rc = C.build(SAMPLE, out, zoom=3.0, viewer=True, strict=True, label="9709_m26_qp_12")
    man = json.loads((out / "crops" / "manifest.json").read_text(encoding="utf-8"))
    return rc, out, man


def _px(path: Path) -> tuple[int, int]:
    import pymupdf
    pix = pymupdf.Pixmap(str(path))
    return pix.width, pix.height


def test_build_exit_and_checks(run):
    rc, _out, man = run
    assert rc == 0, f"strict 模式返回 {rc}，警告：{man['warnings']}"
    assert man["warnings"] == []
    assert [c["name"] for c in man["checks"]] == [
        "subparts_contiguous", "marker_pair_single", "edges_clean",
        "ink_sane", "drawings_within_box", "nothing_after_last"]
    assert all(c["ok"] for c in man["checks"]), man["checks"]
    assert man["stats"] == {"questions": 11, "subpart_markers": 19,
                            "images": 15, "checks_failed": 0}


def test_images_written(run):
    _rc, out, _man = run
    names = sorted(p.name for p in (out / "crops").glob("q*.png"))
    assert len(names) == 15
    assert sum(1 for n in names if "-p" not in n) == 11   # 合成图
    assert sum(1 for n in names if "-p" in n) == 4        # 分页图（Q10×2 + Q11×2）
    assert (out / "viewer.html").is_file()
    html = (out / "viewer.html").read_text(encoding="utf-8")
    assert "crops/q01.png" in html


def test_image_sizes(run):
    """尺寸口径（实测，与参考实现逐字节一致）：
    合成图 单页 1466×2035 / 双页 1466×4070；
    分页图 1466×2036（裁剪矩形像素吸附，比合成每页多 1px 白边）。"""
    _rc, out, man = run
    crops = out / "crops"
    for q in man["questions"]:
        w, h = _px(crops / q["composite"]["image"])
        assert w == 1466
        if len(q["segments"]) == 1:
            assert h == 2035
        else:
            assert h == 4070
            for s in q["segments"]:
                assert _px(crops / s["png"]) == (1466, 2036)


def test_edges_and_ink_from_manifest(run):
    _rc, _out, man = run
    for q in man["questions"]:
        comp = q["composite"]
        assert comp["edge_dark_px"] == 0
        assert 0.01 <= comp["ink_frac"] <= 0.035
