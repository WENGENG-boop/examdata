"""内容级文件类型识别测试。

用仓库里的真实 Cambridge PDF 做断言——分类器的价值就在于对真实版面有效，
拿构造出来的文本测等于只测了正则能不能匹配。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from examdata.parsing.content_classify import (
    ContentEvidence,
    classify_content,
    reconcile,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _fixture(name: str) -> Path:
    p = FIXTURES / name
    if not p.exists():
        pytest.skip(f"缺少测试样本 {name}")
    return p


# --------------------------------------------------------------------------
# 对真实文件的判定
# --------------------------------------------------------------------------


def test_question_paper_recognised():
    ev = classify_content(_fixture("0580_qp_11.pdf"))
    assert ev.doc_type == "question_paper"
    assert ev.confidence > 0.3
    assert ev.pages_scanned >= 1
    assert "question_paper" in ev.scores


def test_mark_scheme_recognised():
    ev = classify_content(_fixture("0580_ms_11.pdf"))
    assert ev.doc_type == "mark_scheme"
    assert ev.confidence > 0.3


def test_specimen_mark_scheme_recognised():
    ev = classify_content(_fixture("0580_ms_01_specimen.pdf"))
    assert ev.doc_type == "specimen_mark_scheme"


def test_mark_scheme_and_question_paper_are_distinguishable():
    """两类文件的判定必须真正不同——否则分类器没有判别力。"""
    qp = classify_content(_fixture("0580_qp_11.pdf"))
    ms = classify_content(_fixture("0580_ms_11.pdf"))
    assert qp.doc_type != ms.doc_type


def test_evidence_is_auditable():
    """判定必须带可追溯证据，不能只给一个标签。"""
    ev = classify_content(_fixture("0580_ms_11.pdf"))
    assert ev.matched, "必须记录命中了哪些措辞"
    assert ev.scores
    d = ev.to_dict()
    assert set(d) >= {"doc_type", "confidence", "scores", "matched", "pages_scanned"}
    assert all(0.0 <= v for v in d["scores"].values())


def test_missing_file_is_reported_not_raised():
    ev = classify_content(FIXTURES / "does_not_exist.pdf")
    assert ev.doc_type is None
    assert ev.confidence == 0.0
    assert ev.error


# --------------------------------------------------------------------------
# 融合规则
# --------------------------------------------------------------------------


def _ev(doc_type: str | None, confidence: float = 0.9) -> ContentEvidence:
    return ContentEvidence(doc_type=doc_type, confidence=confidence)


def test_reconcile_agreement_is_high_confidence():
    doc_type, conf, method = reconcile("mark_scheme", _ev("mark_scheme", 0.95))
    assert doc_type == "mark_scheme"
    assert method == "label+content"
    assert conf >= 0.9


def test_reconcile_specialisation_is_not_a_conflict():
    """内容只能看出"这是试卷"，样卷身份来自官方页面标注——这是具体化，不是冲突。"""
    for specific, generic in (
        ("specimen_paper", "question_paper"),
        ("specimen_mark_scheme", "mark_scheme"),
    ):
        doc_type, conf, method = reconcile(specific, _ev(generic, 0.9))
        assert doc_type == specific, "应保留更具体的标签"
        assert method == "label+content"
        assert conf >= 0.9


def test_reconcile_real_conflict_is_flagged_low_confidence():
    doc_type, conf, method = reconcile("formula_booklet", _ev("examiner_report", 0.9))
    assert method == "conflict"
    assert doc_type == "formula_booklet", "冲突时保留页面判定（页面信息是权威来源）"
    assert conf < 0.4, "冲突必须低置信度，从而进入待检查"


def test_reconcile_content_only_is_discounted():
    doc_type, conf, method = reconcile(None, _ev("mark_scheme", 0.9))
    assert doc_type == "mark_scheme"
    assert method == "content"
    assert conf <= 0.75, "没有页面佐证时要打折"


def test_reconcile_label_only_keeps_label():
    doc_type, conf, method = reconcile("question_paper", _ev(None))
    assert doc_type == "question_paper"
    assert method == "label"
    assert 0 < conf < 1


def test_reconcile_nothing_falls_back_to_other():
    doc_type, conf, method = reconcile(None, _ev(None))
    assert doc_type == "other"
    assert method == "none"


def test_reconcile_never_returns_above_one():
    for label in ("mark_scheme", None):
        for content in (_ev("mark_scheme", 5.0), _ev(None)):
            _, conf, _ = reconcile(label, content)
            assert 0.0 <= conf <= 1.0
