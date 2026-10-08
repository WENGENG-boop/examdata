"""A05 fixture-provider tests: mapping, hierarchy, gaps and provenance.

These tests pin the behaviour the plan requires of the staged provider layer
(A05, plan 8.1-8.3):

* a provider accepts only fixtures labelled synthetic, so real material can never
  enter the staged layer;
* native identities, question hierarchy, table structure and the missing answer
  slot survive the mapping intact;
* an unsupported capability or an uninterpretable filter is typed, never a
  silent empty success;
* every emitted answer stays `unverified` / `synthetic`, and every gap the
  fixture actually shows is carried on the result.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from examdata_integration.contracts.canonical import is_url_safe_public_id
from examdata_integration.contracts.enums import (
    AnswerMatchingMethod,
    ContainerKind,
    ContentClass,
    ExamSystem,
    QuestionType,
)
from examdata_integration.contracts.models import (
    Container,
    Course,
    Coverage,
    OptionsPayload,
    TablePayload,
    TextPayload,
    UnknownPayload,
)
from examdata_integration.providers import (
    CIEIndexProvider,
    Capability,
    EdexcelIndexProvider,
    IELTSQuestionsProvider,
)

STAGING = Path(__file__).resolve().parents[1]
FIXTURES = STAGING / "fixtures" / "synthetic"

CIE_PATH = FIXTURES / "cie" / "cie-index-synthetic.json"
EDEXCEL_PATH = FIXTURES / "edexcel" / "index-synthetic.json"
IELTS_PATH = FIXTURES / "ielts" / "questions-synthetic.json"


@pytest.fixture(scope="module")
def cie():
    return CIEIndexProvider(CIE_PATH)


@pytest.fixture(scope="module")
def edexcel():
    return EdexcelIndexProvider(EDEXCEL_PATH)


@pytest.fixture(scope="module")
def ielts():
    return IELTSQuestionsProvider(IELTS_PATH)


def _gap_codes(result):
    return [g.code for g in result.gaps]


# --------------------------------------------------------------------------- #
# fixture admission
# --------------------------------------------------------------------------- #
def test_non_synthetic_fixture_is_refused(tmp_path):
    path = tmp_path / "not-synthetic.json"
    path.write_text(json.dumps({"fixture_kind": "copied_snapshot", "board": "cie"}),
                    encoding="utf-8")
    with pytest.raises(ValueError):
        CIEIndexProvider(path)


def test_fixture_without_a_kind_is_refused(tmp_path):
    path = tmp_path / "no-kind.json"
    path.write_text(json.dumps({"board": "cie"}), encoding="utf-8")
    with pytest.raises(ValueError):
        CIEIndexProvider(path)


def test_synthetic_fixture_is_accepted(cie, edexcel, ielts):
    assert cie.descriptor.provider_id == "cie_index_fixture"
    assert edexcel.descriptor.provider_id == "edexcel_index_fixture"
    assert ielts.descriptor.provider_id == "ielts_questions_fixture"
    assert cie.descriptor.exam_system is ExamSystem.CIE
    assert ielts.descriptor.exam_system is ExamSystem.IELTS


def test_discovery_returns_the_descriptor(cie):
    result = cie.query(Capability.DISCOVERY)
    assert result.ok
    assert result.count == 1
    assert result.items[0]["provider_id"] == "cie_index_fixture"


# --------------------------------------------------------------------------- #
# CIE
# --------------------------------------------------------------------------- #
def test_cie_courses_preserve_the_native_subject(cie):
    result = cie.query(Capability.COURSES)
    assert result.ok and result.count == 1
    course = result.items[0]
    assert isinstance(course, Course)
    assert course.system is ExamSystem.CIE
    assert course.native_code == "9999"
    assert course.aliases == ["synthetic-subject"]
    assert course.applicable_years == [2024]
    assert is_url_safe_public_id(course.public_id)


def test_cie_courses_filter_matches_native_and_alias(cie):
    assert cie.query(Capability.COURSES, filters={"subject": "9999"}).count == 1
    assert cie.query(Capability.COURSES, filters={"subject": "synthetic-subject"}).count == 1
    empty = cie.query(Capability.COURSES, filters={"subject": "does-not-exist"})
    assert empty.ok and empty.count == 0


def test_cie_container_keeps_native_identity_and_reports_unknown_date(cie):
    result = cie.query(Capability.CONTAINERS)
    assert result.ok and result.count == 1
    container = result.items[0]
    assert isinstance(container, Container)
    assert container.kind is ContainerKind.PAPER
    assert container.native_identity == {"subject": "9999", "year": 2024,
                                         "season": "Jun", "paper": "11", "date": None}
    roles = sorted(r["role"] for r in container.resources)
    assert roles == ["ms", "qp"]
    assert len(container.question_refs) == 5
    assert "unknown_date" in _gap_codes(result)


def test_cie_container_filter_rejects_a_different_year(cie):
    result = cie.query(Capability.CONTAINERS, filters={"year": 2023})
    assert result.ok and result.count == 0


def test_cie_questions_preserve_hierarchy(cie):
    result = cie.query(Capability.QUESTIONS)
    assert result.ok and result.count == 5
    by_native = {q.native_id: q for q in result.items}
    assert set(by_native) == {"1", "1(a)", "1(b)", "2", "3"}
    parent = by_native["1"]
    assert [c.native_id for c in parent.children] == ["1(a)", "1(b)"]
    assert by_native["1(a)"].parent_ref == "1"
    assert by_native["1(a)"].number_path == ["1", "1(a)"]
    assert all(q.content_class is ContentClass.SYNTHETIC for q in result.items)


def test_cie_question_public_ids_are_stable_and_distinct(cie):
    first = {q.native_id: q.public_id for q in cie.query(Capability.QUESTIONS).items}
    again = {q.native_id: q.public_id for q in cie.query(Capability.QUESTIONS).items}
    assert first == again
    assert len(set(first.values())) == len(first)
    assert all(is_url_safe_public_id(pid) for pid in first.values())


def test_cie_table_question_maps_to_a_table_payload(cie):
    result = cie.query(Capability.QUESTIONS, target="2")
    assert result.ok and result.count == 1
    question = result.items[0]
    assert question.question_type is QuestionType.TABLE_CHOICE
    assert isinstance(question.payload, TablePayload)
    assert len(question.payload.columns) == 2
    assert len(question.payload.rows) == 2
    assert (question.payload.answer_cells[0].row, question.payload.answer_cells[0].column) == (2, 2)


def test_cie_questions_target_and_missing_target(cie):
    one = cie.query(Capability.QUESTIONS, target="1(b)")
    assert one.ok and one.count == 1
    assert one.items[0].native_id == "1(b)"
    missing = cie.query(Capability.QUESTIONS, target="9")
    assert missing.status.value == "not_found"


def test_cie_answers_conflict_stays_unverified(cie):
    result = cie.query(Capability.ANSWERS, target="3")
    assert result.ok and result.count == 1
    answer = result.items[0]
    assert answer.verification == "unverified"
    assert answer.content_class is ContentClass.SYNTHETIC
    assert len(answer.conflicts) == 2
    assert answer.manual_decision is None
    assert "answer_conflict" in _gap_codes(result)


def test_cie_answers_for_a_question_without_a_key_is_a_genuine_empty(cie):
    result = cie.query(Capability.ANSWERS, target="1")
    assert result.ok and result.count == 0


def test_cie_answers_require_a_target(cie):
    result = cie.query(Capability.ANSWERS)
    assert result.status.value == "failed"
    assert result.error_code == "target_required"


def test_cie_answers_unknown_target_is_not_found(cie):
    result = cie.query(Capability.ANSWERS, target="ghost")
    assert result.status.value == "not_found"


def test_cie_resources_are_hash_only_assets(cie):
    result = cie.query(Capability.RESOURCES)
    assert result.ok and result.count == 2
    assert {a.sha256[0] for a in result.items} == {"2", "3"}
    assert all(a.storage_mode == "external_only" for a in result.items)


def test_cie_assets_report_a_missing_required_image(cie):
    result = cie.query(Capability.ASSETS)
    assert result.ok and result.count == 1
    assert result.items[0].sha256.startswith("4444")
    assert "missing_required_image" in _gap_codes(result)


def test_cie_regions_have_page_but_no_bbox(cie):
    result = cie.query(Capability.REGIONS)
    assert result.ok and result.count == 5
    assert all(r.bbox == [] for r in result.items)
    assert all(r.document_sha256.startswith("2222") for r in result.items)
    assert all(r.evidence_status == "unverified" for r in result.items)
    assert _gap_codes(result).count("missing_region") == 5


def test_cie_regions_filter_rejects_another_document_role(cie):
    result = cie.query(Capability.REGIONS, filters={"document_role": "ms"})
    assert result.ok and result.count == 0


def test_cie_coverage_is_honestly_unknown(cie):
    result = cie.query(Capability.COVERAGE)
    assert result.ok and result.count == 1
    cov = result.items[0]
    assert isinstance(cov, Coverage)
    assert cov.denominator_known is False
    assert cov.verified == 0
    assert cov.observed == cov.excluded + cov.unknown + cov.missing + cov.partial + cov.verified


def test_cie_unsupported_filter_is_typed(cie):
    result = cie.query(Capability.QUESTIONS, filters={"book": "x"})
    assert result.status.value == "filter_rejected"
    assert result.filter_key == "book"


def test_cie_unsupported_capability_is_typed(cie):
    result = cie.query(Capability.TAGS)
    assert result.status.value == "unsupported"


# --------------------------------------------------------------------------- #
# Edexcel
# --------------------------------------------------------------------------- #
def test_edexcel_courses_preserve_aliases_and_qualification(edexcel):
    result = edexcel.query(Capability.COURSES)
    assert result.ok and result.count == 1
    course = result.items[0]
    assert course.system is ExamSystem.EDEXCEL
    assert course.native_code == "synthetic-ial-mathematics"
    assert sorted(course.aliases) == ["WMA", "synthetic-maths"]
    assert course.qualification == "IAL"


def test_edexcel_courses_filter_by_qualification(edexcel):
    assert edexcel.query(Capability.COURSES, filters={"qualification": "IAL"}).count == 1
    assert edexcel.query(Capability.COURSES, filters={"qualification": "GCSE"}).count == 0


def test_edexcel_container_keeps_unit_and_paper_codes(edexcel):
    result = edexcel.query(Capability.CONTAINERS)
    assert result.ok and result.count == 1
    container = result.items[0]
    assert container.kind is ContainerKind.PAPER
    assert container.native_identity["unit_code"] == "WMA11"
    assert container.native_identity["paper_code"] == "01"
    assert sorted(r["role"] for r in container.resources) == ["ms", "qp"]


def test_edexcel_container_reports_each_unknown_session_date(edexcel):
    result = edexcel.query(Capability.CONTAINERS)
    assert _gap_codes(result).count("unknown_date") == 2


def test_edexcel_container_filters(edexcel):
    assert edexcel.query(Capability.CONTAINERS, filters={"unit_code": "WMA11"}).count == 1
    assert edexcel.query(Capability.CONTAINERS, filters={"session": "2024-Jun"}).count == 1
    assert edexcel.query(Capability.CONTAINERS, filters={"session": "2025-Jan"}).count == 0


def test_edexcel_resources_are_documents(edexcel):
    result = edexcel.query(Capability.RESOURCES)
    assert result.ok and result.count == 2
    assert {a.sha256[0] for a in result.items} == {"5", "6"}


def test_edexcel_has_no_question_or_answer_data(edexcel):
    assert edexcel.query(Capability.QUESTIONS).status.value == "unsupported"
    assert edexcel.query(Capability.ANSWERS).status.value == "unsupported"


# --------------------------------------------------------------------------- #
# IELTS
# --------------------------------------------------------------------------- #
def test_ielts_courses_carry_book_aliases(ielts):
    result = ielts.query(Capability.COURSES)
    assert result.ok and result.count == 1
    course = result.items[0]
    assert course.native_code == "synthetic-book-1"
    assert sorted(course.aliases) == ["SB1", "synthetic/cambridge-1"]


def test_ielts_container_is_a_book_with_a_revision(ielts):
    result = ielts.query(Capability.CONTAINERS)
    assert result.ok and result.count == 1
    container = result.items[0]
    assert container.kind is ContainerKind.BOOK
    assert container.revision == "rev-synthetic-0001"
    assert len(container.question_refs) == 8


def test_ielts_questions_preserve_children_and_paths(ielts):
    result = ielts.query(Capability.QUESTIONS)
    assert result.ok and result.count == 8
    by_native = {q.native_id: q for q in result.items}
    assert set(by_native) == {"Q1", "Q2", "Q3", "Q3.i", "Q3.ii", "Q4", "Q41", "Q5"}
    assert by_native["Q3.i"].parent_ref == "Q3"
    assert by_native["Q3.i"].number_path == ["Q3", "Q3.i"]


def test_ielts_grouped_alternatives_become_options(ielts):
    question = ielts.query(Capability.QUESTIONS, target="Q2").items[0]
    assert question.question_type is QuestionType.SINGLE_CHOICE
    assert isinstance(question.payload, OptionsPayload)
    assert [o.key for o in question.payload.options] == ["B", "A", "C", "D"]
    answer = question.answers[0]
    assert answer.matching_method is AnswerMatchingMethod.GROUPED
    assert sorted(answer.alternatives) == ["A", "C", "D"]


def test_ielts_table_choice_becomes_a_table_payload(ielts):
    question = ielts.query(Capability.QUESTIONS, target="Q4").items[0]
    assert question.question_type is QuestionType.TABLE_CHOICE
    assert isinstance(question.payload, TablePayload)
    assert len(question.payload.columns) == 3
    assert (question.payload.answer_cells[0].row, question.payload.answer_cells[0].column) == (2, 3)


def test_ielts_fill_blank_is_a_text_payload(ielts):
    question = ielts.query(Capability.QUESTIONS, target="Q1").items[0]
    assert question.question_type is QuestionType.SHORT_ANSWER
    assert isinstance(question.payload, TextPayload)


def test_ielts_missing_answer_slot_is_preserved_never_fabricated(ielts):
    question = ielts.query(Capability.QUESTIONS, target="Q41").items[0]
    assert question.question_type is QuestionType.UNKNOWN
    assert isinstance(question.payload, UnknownPayload)
    assert question.stem is None
    assert question.answers == []

    result = ielts.query(Capability.ANSWERS, target="Q41")
    assert result.ok and result.count == 0
    assert "missing_answer_slot" in _gap_codes(result)


def test_ielts_answers_conflict_stays_unverified(ielts):
    result = ielts.query(Capability.ANSWERS, target="Q5")
    assert result.ok and result.count == 1
    answer = result.items[0]
    assert answer.verification == "unverified"
    assert len(answer.conflicts) == 2
    assert answer.manual_decision is None
    assert "answer_conflict" in _gap_codes(result)


def test_ielts_year_filter_is_rejected_a_book_number_is_not_a_year(ielts):
    result = ielts.query(Capability.QUESTIONS, filters={"year": 2024})
    assert result.status.value == "filter_rejected"
    assert result.filter_key == "year"


def test_ielts_book_alias_filter_reaches_the_provider(ielts):
    result = ielts.query(Capability.QUESTIONS, filters={"book": "SB1"})
    assert result.ok and result.count == 8


def test_ielts_assets_report_a_missing_required_image(ielts):
    result = ielts.query(Capability.ASSETS)
    assert result.ok and result.count == 1
    assert result.items[0].sha256.startswith("0000")
    assert "missing_required_image" in _gap_codes(result)


def test_ielts_coverage_counts_present_and_missing_slots(ielts):
    result = ielts.query(Capability.COVERAGE)
    assert result.ok and result.count == 1
    cov = result.items[0]
    assert cov.denominator_known is True
    assert cov.unknown == 5
    assert cov.missing == 1
    assert cov.observed == cov.excluded + cov.unknown + cov.missing + cov.partial + cov.verified


def test_ielts_has_no_region_data(ielts):
    assert ielts.query(Capability.REGIONS).status.value == "unsupported"


# --------------------------------------------------------------------------- #
# cross-provider invariants
# --------------------------------------------------------------------------- #
def test_no_emitted_content_is_ever_verified(cie, edexcel, ielts):
    for provider in (cie, edexcel, ielts):
        for capability in (Capability.QUESTIONS, Capability.ANSWERS, Capability.REGIONS):
            result = provider.query(capability)
            if not result.ok:
                continue
            for item in result.items:
                if hasattr(item, "verification"):
                    assert item.verification == "unverified"
                if hasattr(item, "content_class"):
                    assert item.content_class is ContentClass.SYNTHETIC
                for answer in getattr(item, "answers", []):
                    assert answer.verification == "unverified"


def test_coverage_arithmetic_is_self_consistent(cie, edexcel, ielts):
    for provider in (cie, edexcel, ielts):
        cov = provider.query(Capability.COVERAGE).items[0]
        assert cov.observed == (cov.excluded + cov.unknown + cov.missing
                                + cov.partial + cov.verified)


def test_same_native_number_across_systems_gets_distinct_ids(cie, ielts):
    cie_id = cie.query(Capability.QUESTIONS, target="1").items[0].public_id
    ielts_id = ielts.query(Capability.QUESTIONS, target="Q1").items[0].public_id
    assert cie_id != ielts_id
