"""A07: exact / ancestor / descendants answer resolution."""
from __future__ import annotations

from examdata_integration.adapters import AnswerMode, resolve_answers
from examdata_integration.adapters.problems import ProblemCode
from examdata_integration.contracts.enums import AnswerMatchingMethod


def _resolve(questions, *, default_mode="exact"):
    return resolve_answers(questions, default_mode=default_mode, system="cie",
                           container_native={"subject": "0000"}, source_id="synthetic-test",
                           provider_id="test_adapter", fixture_name="unit-test.json")


def _codes(result):
    return [p.code for p in result.problems]


def test_exact_answer_is_read_from_the_question():
    result = _resolve([{"question": "1", "answer": "value-1", "answer_mode": "exact"}])
    answers = result.for_question("1")
    assert len(answers) == 1
    assert answers[0].original_value == "value-1"
    assert answers[0].matching_method is AnswerMatchingMethod.EXACT
    assert result.modes["1"] == "exact"


def test_exact_answer_with_alternatives_is_grouped():
    result = _resolve([{"question": "1", "answer": "a", "alternative_answers": ["b", "c"]}])
    answer = result.for_question("1")[0]
    assert answer.matching_method is AnswerMatchingMethod.GROUPED
    assert answer.alternatives == ["b", "c"]


def test_default_mode_applies_when_a_question_does_not_override_it():
    result = _resolve([{"question": "1", "answer": "v"}], default_mode="exact")
    assert result.modes["1"] == "exact"


def test_ancestor_child_inherits_the_parent_answer():
    result = _resolve([{
        "question": "3", "answer": "parent", "answer_mode": "ancestor",
        "parts": [{"question": "3(a)", "answer_mode": "ancestor"}],
    }])
    assert result.for_question("3")[0].original_value == "parent"
    child = result.for_question("3(a)")[0]
    assert child.original_value == "parent"
    assert child.matching_method is AnswerMatchingMethod.ANCESTOR
    assert child.lineage.parent_refs == ["3"]


def test_ancestor_without_an_ancestor_answer_is_a_visible_gap():
    result = _resolve([{"question": "1", "answer_mode": "ancestor"}])
    assert result.for_question("1") == []
    assert _codes(result) == [ProblemCode.MISSING_ANSWER.value]


def test_descendants_parent_answer_is_derived_from_parts_in_order():
    result = _resolve([{
        "question": "1", "answer_mode": "descendants",
        "parts": [{"question": "1(a)", "answer": "a"}, {"question": "1(b)", "answer": "b"}],
    }])
    answer = result.for_question("1")[0]
    assert answer.original_value is None
    assert answer.alternatives == ["a", "b"]
    assert answer.matching_method is AnswerMatchingMethod.DESCENDANTS
    assert answer.lineage.parent_refs == ["1(a)", "1(b)"]


def test_descendants_without_child_answers_is_a_visible_gap():
    result = _resolve([{"question": "1", "answer_mode": "descendants",
                        "parts": [{"question": "1(a)"}]}])
    assert result.for_question("1") == []
    assert ProblemCode.MISSING_ANSWER.value in _codes(result)


def test_own_answer_wins_over_the_declared_mode():
    result = _resolve([{"question": "1", "answer": "own", "answer_mode": "descendants",
                        "parts": [{"question": "1(a)", "answer": "child"}]}])
    assert result.for_question("1")[0].original_value == "own"
    assert result.for_question("1")[0].matching_method is AnswerMatchingMethod.EXACT


def test_none_mode_keeps_only_a_stated_answer_and_resolves_nothing_else():
    result = _resolve([{"question": "1", "answer": "v", "answer_mode": "none"}])
    assert [a.original_value for a in result.for_question("1")] == ["v"]
    assert result.problems == []


def test_none_mode_does_not_inherit_from_an_ancestor():
    result = _resolve([{"question": "1", "answer": "v", "answer_mode": "none",
                        "parts": [{"question": "1(a)", "answer_mode": "none"}]}])
    assert result.for_question("1(a)") == []
    assert result.problems == []


def test_unknown_mode_is_reported_and_keeps_only_a_stated_answer():
    result = _resolve([{"question": "1", "answer": "v", "answer_mode": "telepathy"}])
    assert [a.original_value for a in result.for_question("1")] == ["v"]
    assert _codes(result) == [ProblemCode.UNRESOLVED_ANSWER_MODE.value]


def test_conflicting_candidates_are_preserved_not_resolved():
    result = _resolve([{
        "question": "1", "answer_mode": "exact",
        "answer_conflicts": [
            {"value": "candidate-1", "source": "ms", "decision": None},
            {"value": "candidate-2", "source": "report", "decision": None},
        ],
    }])
    answer = result.for_question("1")[0]
    assert len(answer.conflicts) == 2
    assert answer.manual_decision is None


def test_a_manual_decision_is_carried_through():
    result = _resolve([{
        "question": "1", "answer": "chosen", "answer_mode": "exact",
        "answer_conflicts": [{"value": "a", "source": "ms", "decision": None}],
        "manual_decision": {"decided_by": "human", "selected_value": "chosen"},
    }])
    decision = result.for_question("1")[0].manual_decision
    assert decision is not None
    assert decision.selected_value == "chosen"


def test_every_resolved_answer_stays_unverified_and_synthetic():
    result = _resolve([
        {"question": "1", "answer": "v"},
        {"question": "2", "answer_mode": "descendants",
         "parts": [{"question": "2(a)", "answer": "x"}]},
    ])
    answers = result.for_question("1") + result.for_question("2")
    assert answers
    for answer in answers:
        assert answer.verification == "unverified"
        assert answer.content_class.value == "synthetic"


def test_public_ids_are_deterministic_across_runs():
    questions = [{"question": "1", "answer": "v"}]
    first = _resolve(questions).for_question("1")[0].public_id
    second = _resolve(questions).for_question("1")[0].public_id
    assert first == second
    assert first.startswith("ans_")


def test_answer_mode_coercion_accepts_strings_and_members():
    assert AnswerMode.coerce("exact") is AnswerMode.EXACT
    assert AnswerMode.coerce(AnswerMode.DESCENDANTS) is AnswerMode.DESCENDANTS
    assert AnswerMode.coerce("nonsense") is None
    assert AnswerMode.coerce(None) is None
