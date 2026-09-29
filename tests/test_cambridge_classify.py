"""Cambridge 锚文本分类器测试。

样本全部来自 research/cambridge.md 的真实实测锚文本。
"""

from __future__ import annotations

import pytest

from examdata.adapters.cambridge.classify import (
    DOC_CONFIDENTIAL_INSTRUCTIONS,
    DOC_EXAMINER_REPORT,
    DOC_INSERT,
    DOC_MARK_SCHEME,
    DOC_QUESTION_PAPER,
    DOC_SPECIMEN_MARK_SCHEME,
    DOC_SPECIMEN_PAPER,
    cross_check,
    normalize_label,
    parse_label,
    parse_slug,
    split_paper_code,
)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("June 2024 Question Paper 11 (PDF, 1MB)", "June 2024 Question Paper 11"),
        ("-->June 2024 Mark Scheme Paper 21 (PDF, 265KB)", "June 2024 Mark Scheme Paper 21"),
        ("June 2024 Examiner Report (PDF, 1MB)", "June 2024 Examiner Report"),
        ("2025 Specimen Paper 1 (PDF, 1MB)", "2025 Specimen Paper 1"),
    ],
)
def test_normalize_label(raw, expected):
    assert normalize_label(raw) == expected


@pytest.mark.parametrize(
    "label,doc_type,year,series,paper",
    [
        ("June 2024 Question Paper 11", DOC_QUESTION_PAPER, 2024, "june", "11"),
        ("June 2024 Mark Scheme Paper 21", DOC_MARK_SCHEME, 2024, "june", "21"),
        ("June 2024 Examiner Report", DOC_EXAMINER_REPORT, 2024, "june", None),
        ("2025 Specimen Paper 1", DOC_SPECIMEN_PAPER, 2025, None, "01"),
        ("2025 Specimen Paper 1 Mark Scheme", DOC_SPECIMEN_MARK_SCHEME, 2025, None, "01"),
        # 词序相反的实测样本（9709）
        ("2020 Specimen Mark Scheme Paper 1", DOC_SPECIMEN_MARK_SCHEME, 2020, None, "01"),
        ("2020 Specimen Paper 2 Mark Scheme", DOC_SPECIMEN_MARK_SCHEME, 2020, None, "02"),
        # 实测样本（0500 / 0610）
        ("2020 Specimen Paper 1 Insert", DOC_INSERT, 2020, None, "01"),
        (
            "June 2024 Confidential Instructions Paper 51",
            DOC_CONFIDENTIAL_INSTRUCTIONS,
            2024,
            "june",
            "51",
        ),
        ("June 2023 Mark Scheme Paper 31", DOC_MARK_SCHEME, 2023, "june", "31"),
    ],
)
def test_parse_label(label, doc_type, year, series, paper):
    p = parse_label(label)
    assert p.doc_type == doc_type
    assert p.year == year
    assert p.series == series
    assert p.paper_code == paper
    assert p.confidence >= 0.8


@pytest.mark.parametrize(
    "url,doc_type,year,paper",
    [
        (
            "/Images/569923-june-2024-question-paper-11.pdf",
            DOC_QUESTION_PAPER,
            2024,
            "11",
        ),
        (
            "/Images/569919-june-2024-mark-scheme-paper-11.pdf",
            DOC_MARK_SCHEME,
            2024,
            "11",
        ),
        ("/Images/569918-june-2024-examiner-report.pdf", DOC_EXAMINER_REPORT, 2024, None),
        ("/Images/663662-2025-specimen-paper-1.pdf", DOC_SPECIMEN_PAPER, 2025, "01"),
        (
            "/Images/663670-2025-specimen-paper-1-mark-scheme.pdf",
            DOC_SPECIMEN_MARK_SCHEME,
            2025,
            "01",
        ),
        ("/Images/414805-2020-specimen-paper-1-insert.pdf", DOC_INSERT, 2020, "01"),
        (
            "/Images/520423-june-2024-confidential-instructions-paper-51.pdf",
            DOC_CONFIDENTIAL_INSTRUCTIONS,
            2024,
            "51",
        ),
    ],
)
def test_parse_slug(url, doc_type, year, paper):
    p = parse_slug(url)
    assert p is not None
    assert p.doc_type == doc_type
    assert p.year == year
    assert p.paper_code == paper


def test_cross_check_agrees_on_real_sample():
    label = parse_label("June 2024 Question Paper 11")
    slug = parse_slug("/Images/569923-june-2024-question-paper-11.pdf")
    result = cross_check(label, slug)
    assert result["agree"] is True
    assert result["mismatches"] == []


def test_cross_check_detects_mismatch():
    label = parse_label("June 2024 Question Paper 11")
    slug = parse_slug("/Images/569923-june-2024-mark-scheme-paper-21.pdf")
    result = cross_check(label, slug)
    assert result["agree"] is False
    assert result["mismatches"]


def test_cross_check_missing_slug_is_not_a_pass():
    label = parse_label("June 2024 Question Paper 11")
    result = cross_check(label, None)
    assert result["agree"] is None


@pytest.mark.parametrize(
    "paper,component,variant",
    [("11", "1", "1"), ("21", "2", "1"), ("61", "6", "1"), (None, None, None)],
)
def test_split_paper_code(paper, component, variant):
    assert split_paper_code(paper) == (component, variant)
