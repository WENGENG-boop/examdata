"""A07: document-hash mapping, missing roles and hash-conflict detection."""
from __future__ import annotations

import pytest

from examdata_integration.adapters import DocumentTable, document_problems
from examdata_integration.adapters.problems import ProblemCode

QP = "a" * 64
MS = "b" * 64
OTHER = "c" * 64


def _table(rows):
    return DocumentTable(rows)


def test_roles_and_hashes_are_read_in_order():
    table = _table([{"role": "qp", "sha256": QP}, {"role": "ms", "sha256": MS}])
    assert table.roles() == ["qp", "ms"]
    assert table.hash_for("qp") == QP
    assert table.hash_for("ms") == MS
    assert table.hash_for("in") is None
    assert table.has_role("ms") is True
    assert table.has_role("in") is False


def test_hashes_are_normalised_to_lower_case_hex():
    table = _table([{"role": "qp", "sha256": "A" * 64}])
    assert table.hash_for("qp") == "a" * 64


def test_rows_without_a_role_are_ignored():
    table = _table([{"sha256": QP}, {"role": "qp", "sha256": QP}])
    assert table.roles() == ["qp"]


def test_missing_hash_on_a_listed_role_is_none():
    table = _table([{"role": "qp"}])
    assert table.has_role("qp") is True
    assert table.hash_for("qp") is None


@pytest.mark.parametrize("role,sha256,expected", [
    ("qp", QP, False),           # agrees
    ("qp", OTHER, True),         # disagrees
    ("qp", None, False),         # nothing cited is not a conflict
    ("in", OTHER, False),        # a role the table does not list is not a conflict
])
def test_conflicts_with(role, sha256, expected):
    table = _table([{"role": "qp", "sha256": QP}])
    assert table.conflicts_with(role, sha256) is expected


def test_conflict_detection_is_case_insensitive():
    table = _table([{"role": "qp", "sha256": QP}])
    assert table.conflicts_with("qp", QP.upper()) is False


def test_missing_roles_lists_only_the_absent_ones():
    table = _table([{"role": "qp", "sha256": QP}])
    assert table.missing_roles(["qp", "ms", "in"]) == ["ms", "in"]


def test_missing_mark_scheme_gets_its_own_code():
    table = _table([{"role": "qp", "sha256": QP}])
    problems = document_problems(table, required_roles=("qp", "ms"))
    assert [p.code for p in problems] == [ProblemCode.MISSING_MS.value]
    assert problems[0].scope == "container"


def test_missing_question_paper_is_a_missing_document_role():
    table = _table([{"role": "ms", "sha256": MS}])
    problems = document_problems(table, required_roles=("qp", "ms"))
    assert [p.code for p in problems] == [ProblemCode.MISSING_DOCUMENT_ROLE.value]


def test_absent_mark_scheme_without_answer_data_is_not_the_ms_code():
    table = _table([{"role": "qp", "sha256": QP}])
    problems = document_problems(table, required_roles=("qp", "ms"), has_ms_answer_data=False)
    assert [p.code for p in problems] == [ProblemCode.MISSING_DOCUMENT_ROLE.value]


def test_complete_table_produces_no_problem():
    table = _table([{"role": "qp", "sha256": QP}, {"role": "ms", "sha256": MS}])
    assert document_problems(table, required_roles=("qp", "ms")) == []
