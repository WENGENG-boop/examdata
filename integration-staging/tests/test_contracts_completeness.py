"""A04 - type-specific completeness rules (plan 4.7).

An essay is not incomplete for having no options; a diagram-label question is
incomplete without its image; a table-choice question needs its columns, rows
and answer cells; a preserved missing answer slot stays missing; an unknown type
yields no percentage; and unrelated systems are never averaged.
"""
from __future__ import annotations

import pytest

from examdata_integration.contracts.completeness import (
    CrossSystemAggregationError,
    evaluate_question,
    per_system_coverage,
    project_percentage,
)
from examdata_integration.contracts.enums import GapCode, QuestionType, QualityAnswerPresence
from examdata_integration.contracts.models import (
    LabelsPayload,
    Option,
    OptionsPayload,
    Question,
    RequiredAsset,
    TableCell,
    TablePayload,
    TextPayload,
)
from examdata_integration.contracts.quality import Quality


def _names(result) -> dict[str, bool]:
    return {r.name: r.satisfied for r in result.requirements}


def test_essay_requires_no_options():
    q = Question(native_id="E1", question_type=QuestionType.ESSAY, stem="Write a letter.",
                 payload=TextPayload(stem="Write a letter.", word_limit=250))
    result = evaluate_question(q)
    assert "options" not in _names(result)
    assert _names(result)["stem"] is True


def test_choice_requires_a_non_empty_option_list():
    good = Question(question_type=QuestionType.SINGLE_CHOICE,
                    payload=OptionsPayload(options=[Option(key="A"), Option(key="B")]))
    assert _names(evaluate_question(good))["options"] is True

    empty = Question(question_type=QuestionType.SINGLE_CHOICE,
                     payload=OptionsPayload(options=[]))
    assert _names(evaluate_question(empty))["options"] is False


def test_diagram_label_needs_its_image():
    no_asset = Question(question_type=QuestionType.DIAGRAM_LABELS,
                        payload=LabelsPayload(asset_ref=None, labels=["A", "B"]))
    names = _names(evaluate_question(no_asset))
    assert names["diagram_asset"] is False and names["diagram_labels"] is True

    with_ref = Question(question_type=QuestionType.DIAGRAM_LABELS,
                        payload=LabelsPayload(asset_ref="asset_x", labels=["A"]))
    assert _names(evaluate_question(with_ref))["diagram_asset"] is True

    missing_required = Question(
        question_type=QuestionType.DIAGRAM_LABELS,
        payload=LabelsPayload(asset_ref="asset_x", labels=["A"]),
        required_assets=[RequiredAsset(role="diagram", sha256=None, asset_ref=None, required=True)])
    result = evaluate_question(missing_required)
    assert any(g.code == GapCode.MISSING_REQUIRED_IMAGE.value for g in result.gaps)


def test_table_choice_needs_columns_rows_and_answer_cells():
    incomplete = Question(question_type=QuestionType.TABLE_CHOICE,
                          payload=TablePayload(columns=["A", "B"], rows=[["1", "2"]],
                                               answer_cells=[]))
    names = _names(evaluate_question(incomplete))
    assert names["table_columns"] is True and names["table_rows"] is True
    assert names["table_answer_structure"] is False

    complete = Question(question_type=QuestionType.TABLE_CHOICE,
                        payload=TablePayload(columns=["A", "B"], rows=[["1", "2"]],
                                             answer_cells=[TableCell(row=1, column=2)]))
    assert _names(evaluate_question(complete))["table_answer_structure"] is True


def test_preserved_missing_answer_slot_stays_missing():
    q41 = Question(native_id="Q41", question_type=QuestionType.UNKNOWN,
                   quality=Quality(answer_presence=QualityAnswerPresence.MISSING))
    result = evaluate_question(q41)
    assert any(g.code == GapCode.MISSING_ANSWER_SLOT.value for g in result.gaps)
    assert not q41.answers


def test_unknown_type_yields_no_percentage():
    unknown = Question(native_id="X", question_type=QuestionType.UNKNOWN)
    result = evaluate_question(unknown)
    assert result.denominator_known is False
    assert result.percentage is None
    assert result.derived_status == "unknown"
    assert any(g.code == GapCode.UNKNOWN_COVERAGE.value for g in result.gaps)


def test_project_percentage_is_always_refused():
    with pytest.raises(CrossSystemAggregationError):
        project_percentage({"ielts": 90, "cie": 10})


def test_per_system_coverage_keeps_systems_separate():
    a = evaluate_question(Question(question_type=QuestionType.SINGLE_CHOICE,
                                   payload=OptionsPayload(options=[Option(key="A")])))
    b = evaluate_question(Question(question_type=QuestionType.UNKNOWN))
    grouped = per_system_coverage({"ielts": a, "cie": b})
    assert set(grouped) == {"ielts", "cie"}
    assert grouped["ielts"]["percentage"] != grouped["cie"]["percentage"]


def test_to_coverage_buckets_partition_observed():
    result = evaluate_question(Question(
        question_type=QuestionType.SINGLE_CHOICE,
        payload=OptionsPayload(options=[Option(key="A")])))
    coverage = result.to_coverage(public_id="cov_test")
    assert coverage.validate() == []
    assert coverage.observed == (coverage.excluded + coverage.unknown + coverage.missing
                                 + coverage.partial + coverage.verified)
