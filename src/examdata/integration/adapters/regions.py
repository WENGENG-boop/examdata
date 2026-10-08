"""Region mapping for the read adapters (plan A07).

A question may reference several regions on a document, and a scanned page may
be rotated. The adapter preserves both facts and adds nothing:

* every raw region becomes its own :class:`Region`; a question with two regions
  yields two regions (never one merged box);
* a region's cited document hash is kept exactly as cited. If it disagrees with
  the index document table, a ``hash_conflict`` problem is recorded and the
  region stays ``unverified`` - the adapter never rewrites the hash;
* page rotation metadata is carried through when the page is listed; a region on
  a page the index does not describe is reported as ``unknown_rotation`` and
  keeps no transform rather than a guessed one;
* a region without four bounding numbers is a ``missing_region_bbox`` problem,
  not a silently empty region.

Regions are always ``evidence_status = "unverified"``: a page reference proves
where content is expected, not that it was verified.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping

from ..contracts.canonical import normalize_hash, public_id
from ..contracts.enums import EntityKind, GapScope
from ..contracts.models import Lineage, Region
from .documents import DocumentTable, hash_conflict_problem
from .problems import AdapterProblem, ProblemCode, problem


def page_rotation_table(pages: Iterable[Mapping[str, Any]] | None) -> dict[int, dict[str, Any]]:
    """Build ``page -> {rotation_degrees, rotation_transform}`` from a raw index."""
    table: dict[int, dict[str, Any]] = {}
    for raw in pages or []:
        try:
            page = int(raw["page"])
        except (KeyError, TypeError, ValueError):
            continue
        transform = raw.get("rotation_transform")
        table[page] = {
            "rotation_degrees": raw.get("rotation_degrees"),
            "rotation_transform": list(transform) if transform else None,
        }
    return table


def build_regions(regions: Iterable[Mapping[str, Any]] | None, *, doc_table: DocumentTable,
                  coordinate_system: str | None, rotations: Mapping[int, dict[str, Any]],
                  system: str, container_native: Mapping[str, Any],
                  provider_id: str, fixture_name: str, native_ref: str,
                  default_role: str = "qp",
                  rotations_declared: bool = True) -> tuple[list[Region], list[AdapterProblem]]:
    """Map raw region records to contract regions plus any problems.

    ``rotations_declared`` is False when the index carries no page table at all:
    the absence of page metadata is not an error, so no ``unknown_rotation``
    problem is raised for it - the region simply keeps no transform.
    """
    out: list[Region] = []
    problems: list[AdapterProblem] = []
    for index, raw in enumerate(regions or []):
        role = str(raw.get("document_role") or default_role)
        cited = raw.get("document_sha256")
        known = doc_table.hash_for(role)
        if cited is not None and doc_table.conflicts_with(role, cited):
            problems.append(hash_conflict_problem(
                role=role, cited=str(cited), known=known, native_ref=native_ref))
        effective_hash = normalize_hash(cited) if cited else known
        if effective_hash is None:
            problems.append(problem(
                ProblemCode.MISSING_DOCUMENT_ROLE, GapScope.REGION,
                f"{native_ref}: region {index} cites role {role!r} but the index has no hash "
                f"for it", native_ref=native_ref))

        try:
            page = int(raw["page"]) if raw.get("page") is not None else None
        except (TypeError, ValueError):
            page = None

        bbox = _bbox(raw.get("bbox"))
        if len(bbox) != 4:
            problems.append(problem(
                ProblemCode.MISSING_REGION_BBOX, GapScope.REGION,
                f"{native_ref}: region {index} has no usable bounding box "
                f"(expected four numbers)", native_ref=native_ref))

        transform = None
        if page is not None:
            if page in rotations:
                transform = rotations[page].get("rotation_transform")
            elif rotations_declared:
                problems.append(problem(
                    ProblemCode.UNKNOWN_ROTATION, GapScope.REGION,
                    f"{native_ref}: region {index} is on page {page}, which the index does "
                    f"not describe; no rotation transform is assumed", native_ref=native_ref))

        fields = {"system": system, "document_role": role, "document_sha256": effective_hash,
                  "page": page, "bbox": bbox, "coordinate_system": coordinate_system}
        out.append(Region(
            public_id=public_id(EntityKind.REGION, fields),
            document_role=role, document_sha256=effective_hash, page=page, bbox=bbox,
            coordinate_system=coordinate_system, rotation_transform=transform,
            evidence_status="unverified",
            lineage=Lineage(operation="adapter_region_map",
                            parent_refs=[native_ref],
                            note="region read from a raw index; geometry stays unverified"),
        ))
    return out, problems


def _bbox(value: Any) -> list[float]:
    if not isinstance(value, (list, tuple)):
        return []
    out: list[float] = []
    for item in value:
        try:
            out.append(float(item))
        except (TypeError, ValueError):
            return []
    return out


__all__ = ["page_rotation_table", "build_regions"]
