"""CIE read adapter (plan A07).

Reads one *synthetic* raw CIE index and maps it onto the frozen A04 contracts,
preserving native identity, question hierarchy, answer resolution, document
hashes, region geometry and page-rotation metadata. It never reads the original
database, never resumes the CIE batch and never promotes content to verified.

The adapter is a plain mapper: it returns an :class:`AdapterBundle` and reports
every irregularity (missing index, missing mark scheme, hash conflict, unknown
rotation, missing region box, unresolved answer) as an explicit problem instead
of raising.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from ..contracts.canonical import UNKNOWN, public_id
from ..contracts.enums import (
    ContainerKind,
    ContentClass,
    EntityKind,
    ExamSystem,
    GapScope,
    QuestionType,
)
from ..contracts.models import (
    Asset,
    Container,
    Course,
    Lineage,
    Question,
    RequiredAsset,
    SourceRef,
    TableCell,
    TablePayload,
    TextPayload,
)
from .answers import AnswerMode, resolve_answers
from .bundle import AdapterBundle
from .documents import DocumentTable, document_problems
from .problems import ProblemCode, problem
from .reader import read_index
from .regions import build_regions, page_rotation_table

SOURCE_ID = "synthetic-cie-raw-index"


class CIEIndexAdapter:
    """Map a synthetic raw CIE index onto the frozen contracts."""

    provider_id = "cie_index_adapter"
    system = ExamSystem.CIE

    def __init__(self, fixture_path: str | Path) -> None:
        self._path = Path(fixture_path)

    # -- public API ---------------------------------------------------------- #
    def bundle(self) -> AdapterBundle:
        data, problems = read_index(self._path)
        if data is None:
            return AdapterBundle(system=self.system,
                                 source={"fixture": self._path.name, "read": "failed"},
                                 problems=problems)

        doc_table = DocumentTable(data.get("documents"))
        problems = list(problems)
        problems.extend(document_problems(doc_table, required_roles=("qp", "ms")))

        identity = data.get("identity", {})
        container_native = {k: identity.get(k)
                            for k in ("subject", "year", "season", "paper", "date")}
        container_pid = public_id(EntityKind.CONTAINER, {
            "system": "cie", "kind": "paper", "native_identity": container_native})

        if identity.get("date") is None:
            problems.append(problem(
                ProblemCode.UNKNOWN_DATE, GapScope.CONTAINER,
                identity.get("date_unknown_reason")
                or "the raw index carries no session date; the date stays unknown"))

        rotation_table = page_rotation_table(data.get("pages"))
        resolved = resolve_answers(
            data.get("questions", []),
            default_mode=(data.get("answer_resolution") or {}).get("default_mode"),
            system="cie", container_native=container_native, source_id=SOURCE_ID,
            provider_id=self.provider_id, fixture_name=self._path.name)
        problems.extend(resolved.problems)

        questions: list[Question] = []
        regions = []
        for raw in data.get("questions", []):
            question = self._build_question(raw, None, [], container_pid, container_native,
                                            resolved)
            questions.append(question)
            region_items, region_problems = build_regions(
                raw.get("regions"), doc_table=doc_table,
                coordinate_system=data.get("coordinate_system"),
                rotations=rotation_table, system="cie", container_native=container_native,
                provider_id=self.provider_id, fixture_name=self._path.name,
                native_ref=str(raw.get("question")),
                rotations_declared=bool(data.get("pages")))
            regions.extend(region_items)
            problems.extend(region_problems)

        flat = [q for question in questions for q in question.walk()]
        container = Container(
            public_id=container_pid, kind=ContainerKind.PAPER,
            native_identity=container_native,
            sections=[{"questions": [q.public_id for q in flat]}],
            resources=[{"role": row["role"], "sha256": row["sha256"]}
                       for row in doc_table.rows()],
            question_refs=[q.public_id for q in flat], revision=None, coverage=None,
            content_class=ContentClass.SYNTHETIC,
            lineage=Lineage(operation="adapter_container_map", parent_refs=[SOURCE_ID],
                            note="container mapped from a synthetic raw CIE index"),
        )
        assets = [self._document_asset(row) for row in doc_table.rows()]
        courses = [self._course(identity)]
        answers = [a for q in flat for a in q.answers]

        return AdapterBundle(
            system=self.system,
            source={"fixture": self._path.name, "board": data.get("board"),
                    "schema_version": data.get("schema_version"),
                    "coordinate_system": data.get("coordinate_system")},
            courses=courses, containers=[container], questions=questions,
            answers=answers, regions=regions, assets=assets, problems=problems)

    # -- construction -------------------------------------------------------- #
    def _course(self, identity: Mapping[str, Any]) -> Course:
        native_code = str(identity.get("subject"))
        fields = {"system": "cie", "qualification": UNKNOWN, "native_code": native_code,
                  "specification_version": None}
        alias = identity.get("subject_alias")
        return Course(
            public_id=public_id(EntityKind.COURSE, fields), system=ExamSystem.CIE,
            qualification=None, native_code=native_code,
            names=[alias or native_code], aliases=[alias] if alias else [],
            specification_version=None,
            applicable_years=[identity["year"]] if identity.get("year") else [],
            source_refs=[SourceRef(source_id=SOURCE_ID, provider_id=self.provider_id,
                                   locator={"fixture": self._path.name},
                                   content_class=ContentClass.SYNTHETIC)])

    def _document_asset(self, row: Mapping[str, Any]) -> Asset:
        return Asset(
            public_id=public_id(EntityKind.ASSET, {
                "system": "cie", "media_type": row.get("media_type"),
                "sha256": row.get("sha256"), "storage_mode": "external_only"}),
            media_type=row.get("media_type"), byte_size=None, sha256=row.get("sha256"),
            storage_mode="external_only", availability="unknown", content_link=None,
            range_capable=None, revision=None)

    def _build_question(self, raw: Mapping[str, Any], parent: str | None,
                        parent_path: list[str], container_pid: str,
                        container_native: Mapping[str, Any], resolved) -> Question:
        number = str(raw["question"])
        path = parent_path + [number]
        qtype = QuestionType.TABLE_CHOICE if raw.get("table") else QuestionType.SHORT_ANSWER
        fields = {"system": "cie", "container_native_identity": container_native,
                  "native_id": number, "number_path": path, "parent_native_id": parent}
        return Question(
            public_id=public_id(EntityKind.QUESTION, fields), native_id=number,
            container_ref=container_pid, number_path=path, parent_ref=parent,
            question_type=qtype, stem=raw.get("text"), payload=self._payload(raw, qtype),
            marks=raw.get("marks"),
            required_assets=[RequiredAsset(role=i["role"], sha256=i.get("sha256"),
                                           required=True)
                             for i in raw.get("required_images", [])],
            answers=resolved.for_question(number),
            quality=None, content_class=ContentClass.SYNTHETIC,
            lineage=Lineage(operation="adapter_question_map", parent_refs=[number],
                            note="question mapped from a synthetic raw CIE index"),
            children=[self._build_question(child, number, path, container_pid,
                                           container_native, resolved)
                      for child in raw.get("parts", [])],
        )

    @staticmethod
    def _payload(raw: Mapping[str, Any], qtype: QuestionType):
        if qtype is QuestionType.TABLE_CHOICE:
            table = raw["table"]
            cells = [TableCell(row=int(c["row"]), column=int(c["column"]),
                               value=c.get("value")) for c in table.get("answer_cells", [])]
            return TablePayload(columns=list(table["columns"]),
                                rows=[list(r) for r in table["rows"]], answer_cells=cells)
        return TextPayload(stem=raw.get("text"))


__all__ = ["CIEIndexAdapter", "SOURCE_ID"]
