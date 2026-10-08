"""Document-hash mapping and conflict detection for the read adapters (A07).

A raw index lists its documents (question paper, mark scheme, insert, ...) by
role and hash. The adapter's job is to keep that mapping honest:

* a hash is never invented - a role the index does not list is reported missing;
* when a question or region cites a hash that disagrees with the document table,
  the conflict is recorded and the region stays ``unverified`` - the adapter
  never rewrites the cited hash to make the two agree;
* the mark scheme is treated specially: its absence is its own problem code so a
  missing mark scheme is not confused with a missing question paper.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping

from ..contracts.canonical import normalize_hash
from ..contracts.enums import GapScope
from .problems import AdapterProblem, ProblemCode, problem


class DocumentTable:
    """The role -> hash mapping declared by one raw index document."""

    def __init__(self, documents: Iterable[Mapping[str, Any]] | None) -> None:
        self._rows: list[dict[str, Any]] = []
        for raw in documents or []:
            role = raw.get("role")
            if role is None:
                continue
            self._rows.append({
                "role": str(role),
                "sha256": normalize_hash(raw["sha256"]) if raw.get("sha256") else None,
                "media_type": raw.get("media_type"),
                "pages": raw.get("pages"),
            })

    def roles(self) -> list[str]:
        return [row["role"] for row in self._rows]

    def rows(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self._rows]

    def hash_for(self, role: str) -> str | None:
        for row in self._rows:
            if row["role"] == role:
                return row["sha256"]
        return None

    def has_role(self, role: str) -> bool:
        return any(row["role"] == role for row in self._rows)

    def conflicts_with(self, role: str, sha256: str | None) -> bool:
        """True when `sha256` disagrees with the table's hash for `role`.

        A role the table does not list, or a hash the caller did not supply, is
        *not* a conflict - it is a different problem (missing role / no hash).
        """
        known = self.hash_for(role)
        if known is None or sha256 is None:
            return False
        return normalize_hash(sha256) != known

    def missing_roles(self, required: Iterable[str]) -> list[str]:
        return [role for role in required if not self.has_role(role)]


def document_problems(table: DocumentTable, *, required_roles: Iterable[str] = ("qp", "ms"),
                      has_ms_answer_data: bool = True) -> list[AdapterProblem]:
    """Report missing required document roles, with the mark scheme called out."""
    problems: list[AdapterProblem] = []
    for role in table.missing_roles(required_roles):
        if role == "ms" and has_ms_answer_data:
            problems.append(problem(ProblemCode.MISSING_MS, GapScope.CONTAINER,
                                    "the index lists no mark scheme (role 'ms'); answers "
                                    "from a mark scheme cannot be sourced and are never fabricated"))
        else:
            problems.append(problem(ProblemCode.MISSING_DOCUMENT_ROLE, GapScope.CONTAINER,
                                    f"the index lists no document with role {role!r}"))
    return problems


def hash_conflict_problem(*, role: str, cited: str, known: str | None,
                          native_ref: str) -> AdapterProblem:
    return problem(ProblemCode.HASH_CONFLICT, GapScope.REGION,
                   f"{native_ref}: cited document hash for role {role!r} disagrees with the "
                   f"index document table; the cited hash is preserved and the region stays "
                   f"unverified", native_ref=native_ref)


__all__ = ["DocumentTable", "document_problems", "hash_conflict_problem"]
