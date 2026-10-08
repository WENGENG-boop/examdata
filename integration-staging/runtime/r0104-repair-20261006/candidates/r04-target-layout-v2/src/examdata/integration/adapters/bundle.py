"""The result of one adapter read: contract entities plus visible problems.

An :class:`AdapterBundle` is deliberately plain: lists of frozen A04 contract
models, the provenance of the fixture they came from, and every adapter problem.
It never raises and never drops a problem, so a caller can render partial data
and still show exactly what was missing.

``gaps()`` translates the adapter problems that correspond to a frozen contract
gap; the rest stay adapter diagnostics (a missing index file is not a content
gap).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..contracts.base import Gap
from ..contracts.enums import ExamSystem
from ..contracts.models import Answer, Asset, Container, Course, Question, Region
from .problems import AdapterProblem


@dataclass
class AdapterBundle:
    """Everything one adapter read produced, problems included."""

    system: ExamSystem
    source: dict[str, Any] = field(default_factory=dict)
    courses: list[Course] = field(default_factory=list)
    containers: list[Container] = field(default_factory=list)
    questions: list[Question] = field(default_factory=list)
    answers: list[Answer] = field(default_factory=list)
    regions: list[Region] = field(default_factory=list)
    assets: list[Asset] = field(default_factory=list)
    problems: list[AdapterProblem] = field(default_factory=list)

    def walk_questions(self) -> list[Question]:
        out: list[Question] = []
        for question in self.questions:
            out.extend(question.walk())
        return out

    def problems_for(self, code: str) -> list[AdapterProblem]:
        return [p for p in self.problems if p.code == code]

    def gaps(self) -> list[Gap]:
        out: list[Gap] = []
        for problem in self.problems:
            gap = problem.to_gap()
            if gap is not None:
                out.append(gap)
        return out

    def to_dict(self) -> dict[str, Any]:
        return {
            "system": self.system.value,
            "source": dict(self.source),
            "counts": {
                "courses": len(self.courses), "containers": len(self.containers),
                "questions": len(self.questions), "answers": len(self.answers),
                "regions": len(self.regions), "assets": len(self.assets),
            },
            "problems": [p.to_dict() for p in self.problems],
        }


__all__ = ["AdapterBundle"]
