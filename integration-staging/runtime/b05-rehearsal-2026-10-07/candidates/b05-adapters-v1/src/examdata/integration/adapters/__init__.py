"""Read adapters (plan A07).

The adapters turn a raw, board-shaped index document into the frozen A04
contract entities, keeping every irregularity visible as an
:class:`~.problems.AdapterProblem`. They read only synthetic fixtures handed to
them by path; nothing here touches a database, the network, a service or any
protected original file.

Public surface:

* :class:`CIEIndexAdapter`, :class:`EdexcelIndexAdapter` - one board each;
* :class:`AdapterBundle` - the mapped entities plus every problem;
* :func:`read_index` / :func:`validate_index` - the read step on its own;
* :class:`DocumentTable` - the role -> hash map with conflict detection;
* :func:`resolve_answers` / :class:`AnswerMode` - exact / ancestor / descendants;
* :func:`build_regions` / :func:`page_rotation_table` - regions and rotation.
"""
from __future__ import annotations

from .answers import AnswerMode, ResolvedAnswers, resolve_answers
from .bundle import AdapterBundle
from .cie import CIEIndexAdapter
from .documents import DocumentTable, document_problems
from .edexcel import EdexcelIndexAdapter
from .problems import AdapterProblem, ProblemCode, problem
from .reader import SUPPORTED_SCHEMA_VERSIONS, read_index, validate_index
from .regions import build_regions, page_rotation_table

__all__ = [
    "AdapterBundle",
    "AdapterProblem",
    "ProblemCode",
    "problem",
    "read_index",
    "validate_index",
    "SUPPORTED_SCHEMA_VERSIONS",
    "DocumentTable",
    "document_problems",
    "AnswerMode",
    "ResolvedAnswers",
    "resolve_answers",
    "build_regions",
    "page_rotation_table",
    "CIEIndexAdapter",
    "EdexcelIndexAdapter",
]
