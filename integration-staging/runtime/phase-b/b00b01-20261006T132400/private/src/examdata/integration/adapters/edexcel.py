"""Edexcel read adapter (plan A07).

Reads one *synthetic* raw Edexcel subject/unit index and maps it onto the frozen
A04 contracts, preserving native identity, aliases, unit/paper codes, session
labels, document hashes and region metadata. This fixture is index-only (no
questions), so the adapter produces courses, containers, assets and regions and
reports a missing mark scheme per unit that does not list one.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from ..contracts.canonical import public_id
from ..contracts.enums import (
    ContainerKind,
    ContentClass,
    EntityKind,
    ExamSystem,
    GapScope,
)
from ..contracts.models import Asset, Container, Course, Lineage, SourceRef
from .bundle import AdapterBundle
from .documents import DocumentTable, document_problems
from .problems import ProblemCode, problem
from .reader import read_index
from .regions import build_regions, page_rotation_table

SOURCE_ID = "synthetic-edexcel-raw-index"


class EdexcelIndexAdapter:
    """Map a synthetic raw Edexcel index onto the frozen contracts."""

    provider_id = "edexcel_index_adapter"
    system = ExamSystem.EDEXCEL

    def __init__(self, fixture_path: str | Path) -> None:
        self._path = Path(fixture_path)

    def bundle(self) -> AdapterBundle:
        data, problems = read_index(self._path)
        if data is None:
            return AdapterBundle(system=self.system,
                                 source={"fixture": self._path.name, "read": "failed"},
                                 problems=problems)

        problems = list(problems)
        rotation_table = page_rotation_table(data.get("pages"))
        rotations_declared = bool(data.get("pages"))
        coordinate_system = data.get("coordinate_system")

        courses: list[Course] = []
        containers: list[Container] = []
        assets: list[Asset] = []
        regions = []

        for subject in data.get("subjects", []):
            courses.append(self._course(subject))
            for unit in subject.get("units", []):
                doc_table = DocumentTable(unit.get("documents"))
                problems.extend(document_problems(doc_table, required_roles=("qp", "ms")))
                container_native = {
                    "qualification_level": subject.get("qualification_level"),
                    "unit_code": unit.get("unit_code"),
                    "paper_code": unit.get("paper_code"),
                }
                sessions = [s.get("session") for s in unit.get("sessions", [])]
                container_pid = public_id(EntityKind.CONTAINER, {
                    "system": "edexcel", "kind": "paper", "native_identity": container_native})
                containers.append(Container(
                    public_id=container_pid, kind=ContainerKind.PAPER,
                    native_identity=container_native,
                    sections=[{"unit": unit.get("native_id"), "sessions": sessions}],
                    resources=[{"role": row["role"], "sha256": row["sha256"]}
                               for row in doc_table.rows()],
                    question_refs=[], revision=None, coverage=None,
                    content_class=ContentClass.SYNTHETIC,
                    lineage=Lineage(operation="adapter_container_map",
                                    parent_refs=[str(subject.get("native_id"))],
                                    note="unit mapped from a synthetic raw Edexcel index")))
                for row in doc_table.rows():
                    assets.append(self._document_asset(row))
                for session in unit.get("sessions", []):
                    if session.get("date") is None:
                        problems.append(problem(
                            ProblemCode.UNKNOWN_DATE, GapScope.CONTAINER,
                            session.get("date_unknown_reason")
                            or "session date unknown; the date is never invented"))
                unit_regions, region_problems = build_regions(
                    unit.get("regions"), doc_table=doc_table,
                    coordinate_system=coordinate_system, rotations=rotation_table,
                    system="edexcel", container_native=container_native,
                    provider_id=self.provider_id, fixture_name=self._path.name,
                    native_ref=str(unit.get("native_id")),
                    rotations_declared=rotations_declared)
                regions.extend(unit_regions)
                problems.extend(region_problems)

        return AdapterBundle(
            system=self.system,
            source={"fixture": self._path.name, "board": data.get("board"),
                    "schema_version": data.get("schema_version"),
                    "coordinate_system": coordinate_system},
            courses=courses, containers=containers, assets=assets, regions=regions,
            problems=problems)

    # -- construction -------------------------------------------------------- #
    def _course(self, subject: Mapping[str, Any]) -> Course:
        native_code = str(subject.get("native_id"))
        fields = {"system": "edexcel", "qualification": subject.get("qualification_level"),
                  "native_code": native_code,
                  "specification_version": subject.get("specification_code")}
        return Course(
            public_id=public_id(EntityKind.COURSE, fields), system=ExamSystem.EDEXCEL,
            qualification=subject.get("qualification_level"), native_code=native_code,
            names=[subject.get("title") or native_code],
            aliases=list(subject.get("alias_ids", [])),
            specification_version=subject.get("specification_code"), applicable_years=[],
            source_refs=[SourceRef(source_id=SOURCE_ID, provider_id=self.provider_id,
                                   locator={"fixture": self._path.name},
                                   content_class=ContentClass.SYNTHETIC)])

    def _document_asset(self, row: Mapping[str, Any]) -> Asset:
        return Asset(
            public_id=public_id(EntityKind.ASSET, {
                "system": "edexcel", "media_type": row.get("media_type") or "application/pdf",
                "sha256": row.get("sha256"), "storage_mode": "external_only"}),
            media_type=row.get("media_type") or "application/pdf", byte_size=None,
            sha256=row.get("sha256"), storage_mode="external_only", availability="unknown",
            content_link=None, range_capable=None, revision=None)


__all__ = ["EdexcelIndexAdapter", "SOURCE_ID"]
