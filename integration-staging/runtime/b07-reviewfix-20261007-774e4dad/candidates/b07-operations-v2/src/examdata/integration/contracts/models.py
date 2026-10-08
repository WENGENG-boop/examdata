"""Entity models for the staged integration contracts (plan 4.4, 4.5).

Design rules frozen here:

* every model is a plain stdlib dataclass with explicit required and optional
  fields; unknown/absent data is ``None`` or the explicit ``UNKNOWN`` sentinel,
  never a plausible default;
* ``validate()`` returns a list of human-readable problems instead of raising,
  so a provider that reports a data gap keeps working and the gap stays visible;
* ``from_dict`` raises ``ContractError`` for structurally missing fields (a
  broken payload is a programming error, not a data gap);
* ``to_dict`` is round-trip safe: ``from_dict(to_dict(x)) == x`` for every model
  in this module (asserted by the A04 tests).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from .base import UNKNOWN, ContractError, ContractModel, Gap, UnknownType, req as _req
from .enums import (
    AnswerMatchingMethod,
    ContainerKind,
    ContentClass,
    ExamSystem,
    QuestionType,
)
from .quality import Quality


# --------------------------------------------------------------------------- #
# small shared pieces
# --------------------------------------------------------------------------- #
@dataclass
class Lineage(ContractModel):
    """Where a value came from and how it was produced (plan 4.2 rule 7)."""

    SCHEMA = "lineage/1"

    operation: str | None = None
    source_refs: list[str] = field(default_factory=list)
    parent_refs: list[str] = field(default_factory=list)
    note: str | None = None

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "Lineage":
        return cls(
            operation=payload.get("operation"),
            source_refs=list(payload.get("source_refs", [])),
            parent_refs=list(payload.get("parent_refs", [])),
            note=payload.get("note"),
        )


@dataclass
class SourceRef(ContractModel):
    """A reference to an upstream source, with its own provenance class."""

    SCHEMA = "source-ref/1"

    source_id: str | None = None
    provider_id: str | None = None
    locator: dict[str, Any] = field(default_factory=dict)
    content_class: ContentClass = ContentClass.UNKNOWN
    retrieved_at: str | None = None

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "SourceRef":
        return cls(
            source_id=payload.get("source_id"),
            provider_id=payload.get("provider_id"),
            locator=dict(payload.get("locator", {})),
            content_class=ContentClass.coerce(payload.get("content_class", "unknown")),
            retrieved_at=payload.get("retrieved_at"),
        )


@dataclass
class Conflict(ContractModel):
    """One candidate answer value with its evidence (plan 4.5)."""

    SCHEMA = "answer-conflict/1"

    value: str | None = None
    source: str | None = None
    evidence: str | None = None
    decision: str | None = None

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "Conflict":
        return cls(value=payload.get("value"), source=payload.get("source"),
                   evidence=payload.get("evidence"), decision=payload.get("decision"))


@dataclass
class ManualDecision(ContractModel):
    """A human adjudication that selects a preferred answer without deleting any."""

    SCHEMA = "manual-decision/1"

    decided_by: str | None = None
    decided_at: str | None = None
    selected_value: str | None = None
    rationale: str | None = None

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ManualDecision":
        return cls(decided_by=payload.get("decided_by"), decided_at=payload.get("decided_at"),
                   selected_value=payload.get("selected_value"), rationale=payload.get("rationale"))


# --------------------------------------------------------------------------- #
# type-specific question payloads (plan 4.5: never flatten a structure)
# --------------------------------------------------------------------------- #
@dataclass
class Option(ContractModel):
    SCHEMA = "option/1"

    key: str = ""
    label: str | None = None

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "Option":
        return cls(key=_req(payload, "key", "option"), label=payload.get("label"))


@dataclass
class OptionsPayload(ContractModel):
    SCHEMA = "payload/options/1"

    options: list[Option] = field(default_factory=list)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "OptionsPayload":
        return cls(options=[Option.from_dict(o) for o in payload.get("options", [])])

    def validate(self) -> list[str]:
        problems = []
        if not self.options:
            problems.append("payload/options: options list is empty")
        keys = [o.key for o in self.options]
        if len(set(keys)) != len(keys):
            problems.append("payload/options: duplicate option keys")
        return problems


@dataclass
class TableCell(ContractModel):
    SCHEMA = "table-cell/1"

    row: int = 0
    column: int = 0
    value: str | None = None

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "TableCell":
        return cls(row=int(_req(payload, "row", "table-cell")),
                   column=int(_req(payload, "column", "table-cell")),
                   value=payload.get("value"))


@dataclass
class TablePayload(ContractModel):
    """Table structure kept whole: columns, rows and the answer cells."""

    SCHEMA = "payload/table/1"

    columns: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)
    answer_cells: list[TableCell] = field(default_factory=list)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "TablePayload":
        return cls(
            columns=list(payload.get("columns", [])),
            rows=[list(r) for r in payload.get("rows", [])],
            answer_cells=[TableCell.from_dict(c) for c in payload.get("answer_cells", [])],
        )

    def validate(self) -> list[str]:
        problems = []
        if not self.columns:
            problems.append("payload/table: columns missing")
        if not self.rows:
            problems.append("payload/table: rows missing")
        for i, row in enumerate(self.rows):
            if len(row) != len(self.columns):
                problems.append(
                    f"payload/table: row {i + 1} has {len(row)} cells, {len(self.columns)} columns"
                )
        for cell in self.answer_cells:
            if not (1 <= cell.row <= len(self.rows)) or not (1 <= cell.column <= len(self.columns)):
                problems.append(
                    f"payload/table: answer cell ({cell.row},{cell.column}) outside the table"
                )
        return problems


@dataclass
class MatchingPayload(ContractModel):
    SCHEMA = "payload/matching/1"

    left: list[str] = field(default_factory=list)
    right: list[str] = field(default_factory=list)
    mapping: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "MatchingPayload":
        return cls(left=list(payload.get("left", [])), right=list(payload.get("right", [])),
                   mapping={str(k): str(v) for k, v in payload.get("mapping", {}).items()})

    def validate(self) -> list[str]:
        problems = []
        if not self.left or not self.right:
            problems.append("payload/matching: left and right lists are both required")
        for key in self.mapping:
            if key not in self.left:
                problems.append(f"payload/matching: mapping key {key!r} not in left list")
        return problems


@dataclass
class LabelsPayload(ContractModel):
    """Diagram labels: the referenced asset is part of the structure."""

    SCHEMA = "payload/labels/1"

    asset_ref: str | None = None
    labels: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "LabelsPayload":
        return cls(asset_ref=payload.get("asset_ref"), labels=list(payload.get("labels", [])))

    def validate(self) -> list[str]:
        problems = []
        if not self.asset_ref:
            problems.append("payload/labels: asset_ref is required for a diagram-label question")
        if not self.labels:
            problems.append("payload/labels: labels list is empty")
        return problems


@dataclass
class TextPayload(ContractModel):
    SCHEMA = "payload/text/1"

    stem: str | None = None
    word_limit: int | None = None

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "TextPayload":
        return cls(stem=payload.get("stem"), word_limit=payload.get("word_limit"))


@dataclass
class UnknownPayload(ContractModel):
    """An unknown native shape: recorded verbatim instead of being guessed."""

    SCHEMA = "payload/unknown/1"

    native_shape: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "UnknownPayload":
        return cls(native_shape=payload.get("native_shape"), raw=dict(payload.get("raw", {})))


PAYLOAD_BY_TYPE: dict[QuestionType, type[ContractModel]] = {
    QuestionType.SINGLE_CHOICE: OptionsPayload,
    QuestionType.MULTIPLE_CHOICE: OptionsPayload,
    QuestionType.TABLE_CHOICE: TablePayload,
    QuestionType.MATCHING: MatchingPayload,
    QuestionType.FILL_BLANK: TextPayload,
    QuestionType.SHORT_ANSWER: TextPayload,
    QuestionType.ESSAY: TextPayload,
    QuestionType.SPEAKING: TextPayload,
    QuestionType.DIAGRAM_LABELS: LabelsPayload,
    QuestionType.UNKNOWN: UnknownPayload,
}


def payload_from_dict(question_type: QuestionType, payload: Mapping[str, Any]) -> ContractModel:
    cls = PAYLOAD_BY_TYPE[QuestionType.coerce(question_type)]
    return cls.from_dict(payload)


# --------------------------------------------------------------------------- #
# entities (plan 4.4)
# --------------------------------------------------------------------------- #
@dataclass
class Answer(ContractModel):
    """One answer with its provenance; conflicts never overwrite each other."""

    SCHEMA = "answer/1"

    public_id: str | None = None
    question_ref: str | None = None
    original_value: Any = None
    normalized_value: Any = None
    alternatives: list[Any] = field(default_factory=list)
    ordering_rule: str | None = None
    matching_method: AnswerMatchingMethod = AnswerMatchingMethod.UNRESOLVED
    verification: str = "unverified"
    source: SourceRef | None = None
    conflicts: list[Conflict] = field(default_factory=list)
    manual_decision: ManualDecision | None = None
    content_class: ContentClass = ContentClass.UNKNOWN
    lineage: Lineage | None = None

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "Answer":
        return cls(
            public_id=payload.get("public_id"),
            question_ref=payload.get("question_ref"),
            original_value=payload.get("original_value"),
            normalized_value=payload.get("normalized_value"),
            alternatives=list(payload.get("alternatives", [])),
            ordering_rule=payload.get("ordering_rule"),
            matching_method=AnswerMatchingMethod.coerce(
                payload.get("matching_method", "unresolved")),
            verification=payload.get("verification", "unverified"),
            source=SourceRef.from_dict(payload["source"]) if payload.get("source") else None,
            conflicts=[Conflict.from_dict(c) for c in payload.get("conflicts", [])],
            manual_decision=(ManualDecision.from_dict(payload["manual_decision"])
                             if payload.get("manual_decision") else None),
            content_class=ContentClass.coerce(payload.get("content_class", "unknown")),
            lineage=Lineage.from_dict(payload["lineage"]) if payload.get("lineage") else None,
        )

    def validate(self) -> list[str]:
        problems = []
        if self.original_value is None and self.normalized_value is None and not self.conflicts:
            problems.append("answer: no value, no normalised value and no conflict candidates")
        if self.manual_decision is not None and self.manual_decision.selected_value is None:
            problems.append("answer: manual decision without a selected value")
        if len(self.conflicts) > 1 and self.manual_decision is None:
            problems.append("answer: conflicting candidates recorded without a manual decision")
        return problems


@dataclass
class RequiredAsset(ContractModel):
    """An asset a question needs; a missing required asset is a gap, not a pass."""

    SCHEMA = "required-asset/1"

    role: str = ""
    sha256: str | None = None
    asset_ref: str | None = None
    required: bool = True

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "RequiredAsset":
        return cls(role=payload.get("role", ""), sha256=payload.get("sha256"),
                   asset_ref=payload.get("asset_ref"), required=bool(payload.get("required", True)))


@dataclass
class Question(ContractModel):
    SCHEMA = "question/1"

    public_id: str | None = None
    native_id: str | None = None
    container_ref: str | None = None
    number_path: list[str] = field(default_factory=list)
    parent_ref: str | None = None
    group_ref: str | None = None
    question_type: QuestionType = QuestionType.UNKNOWN
    stem: str | None = None
    payload: ContractModel | None = None
    marks: int | None = None
    required_assets: list[RequiredAsset] = field(default_factory=list)
    answers: list[Answer] = field(default_factory=list)
    quality: Quality | None = None
    content_class: ContentClass = ContentClass.UNKNOWN
    lineage: Lineage | None = None
    children: list["Question"] = field(default_factory=list)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "Question":
        qtype = QuestionType.coerce(payload.get("question_type", "unknown"))
        raw_payload = payload.get("payload")
        return cls(
            public_id=payload.get("public_id"),
            native_id=payload.get("native_id"),
            container_ref=payload.get("container_ref"),
            number_path=list(payload.get("number_path", [])),
            parent_ref=payload.get("parent_ref"),
            group_ref=payload.get("group_ref"),
            question_type=qtype,
            stem=payload.get("stem"),
            payload=(payload_from_dict(qtype, raw_payload) if raw_payload else None),
            marks=payload.get("marks"),
            required_assets=[RequiredAsset.from_dict(a) for a in payload.get("required_assets", [])],
            answers=[Answer.from_dict(a) for a in payload.get("answers", [])],
            quality=Quality.from_dict(payload["quality"]) if payload.get("quality") else None,
            content_class=ContentClass.coerce(payload.get("content_class", "unknown")),
            lineage=Lineage.from_dict(payload["lineage"]) if payload.get("lineage") else None,
            children=[Question.from_dict(c) for c in payload.get("children", [])],
        )

    def validate(self) -> list[str]:
        problems = []
        if not self.native_id and not self.public_id:
            problems.append("question: neither native_id nor public_id present")
        if self.question_type is not QuestionType.UNKNOWN and self.payload is None:
            problems.append(f"question: type {self.question_type.value} without a typed payload")
        if self.payload is not None:
            problems.extend(f"question[{self.native_id or self.public_id}]: {p}"
                            for p in self.payload.validate())
        if self.question_type in (QuestionType.SINGLE_CHOICE, QuestionType.MULTIPLE_CHOICE) \
                and isinstance(self.payload, OptionsPayload) and not self.payload.options:
            problems.append("question: choice question without options")
        for asset in self.required_assets:
            if asset.required and not asset.sha256 and not asset.asset_ref:
                problems.append(
                    f"question: required asset {asset.role!r} has neither hash nor asset reference")
        if not self.answers and self.question_type is not QuestionType.UNKNOWN:
            problems.append("question: no answer recorded (keep the slot, report the gap)")
        return problems

    def walk(self) -> list["Question"]:
        """Depth-first walk including self, so hierarchy is never flattened."""
        out = [self]
        for child in self.children:
            out.extend(child.walk())
        return out


@dataclass
class Container(ContractModel):
    SCHEMA = "container/1"

    public_id: str | None = None
    kind: ContainerKind = ContainerKind.PAPER
    native_identity: dict[str, Any] = field(default_factory=dict)
    sections: list[dict[str, Any]] = field(default_factory=list)
    resources: list[dict[str, Any]] = field(default_factory=list)
    question_refs: list[str] = field(default_factory=list)
    revision: str | None = None
    coverage: str | None = None
    content_class: ContentClass = ContentClass.UNKNOWN
    lineage: Lineage | None = None

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "Container":
        return cls(
            public_id=payload.get("public_id"),
            kind=ContainerKind.coerce(payload.get("kind", "paper")),
            native_identity=dict(payload.get("native_identity", {})),
            sections=list(payload.get("sections", [])),
            resources=list(payload.get("resources", [])),
            question_refs=list(payload.get("question_refs", [])),
            revision=payload.get("revision"),
            coverage=payload.get("coverage"),
            content_class=ContentClass.coerce(payload.get("content_class", "unknown")),
            lineage=Lineage.from_dict(payload["lineage"]) if payload.get("lineage") else None,
        )

    def validate(self) -> list[str]:
        problems = []
        if not self.native_identity:
            problems.append("container: native identity is empty")
        return problems


@dataclass
class Region(ContractModel):
    SCHEMA = "region/1"

    public_id: str | None = None
    document_role: str | None = None
    document_sha256: str | None = None
    page: int | None = None
    bbox: list[float] = field(default_factory=list)
    coordinate_system: str | None = None
    rotation_transform: list[float] | None = None
    evidence_status: str = "unverified"
    lineage: Lineage | None = None

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "Region":
        return cls(
            public_id=payload.get("public_id"),
            document_role=payload.get("document_role"),
            document_sha256=payload.get("document_sha256"),
            page=payload.get("page"),
            bbox=list(payload.get("bbox", [])),
            coordinate_system=payload.get("coordinate_system"),
            rotation_transform=(list(payload["rotation_transform"])
                                if payload.get("rotation_transform") else None),
            evidence_status=payload.get("evidence_status", "unverified"),
            lineage=Lineage.from_dict(payload["lineage"]) if payload.get("lineage") else None,
        )

    def validate(self) -> list[str]:
        problems = []
        if not self.document_sha256:
            problems.append("region: document hash missing")
        if self.page is None:
            problems.append("region: page missing")
        if len(self.bbox) != 4:
            problems.append("region: bbox must have four numbers")
        return problems


@dataclass
class Asset(ContractModel):
    SCHEMA = "asset/1"

    public_id: str | None = None
    media_type: str | None = None
    byte_size: int | None = None
    sha256: str | None = None
    storage_mode: str | None = None
    availability: str = "unknown"
    content_link: str | None = None
    range_capable: bool | None = None
    revision: str | None = None

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "Asset":
        return cls(
            public_id=payload.get("public_id"),
            media_type=payload.get("media_type"),
            byte_size=payload.get("byte_size"),
            sha256=payload.get("sha256"),
            storage_mode=payload.get("storage_mode"),
            availability=payload.get("availability", "unknown"),
            content_link=payload.get("content_link"),
            range_capable=payload.get("range_capable"),
            revision=payload.get("revision"),
        )

    def validate(self) -> list[str]:
        problems = []
        if not self.sha256:
            problems.append("asset: hash missing")
        if self.byte_size is None:
            problems.append("asset: byte size missing")
        return problems


@dataclass
class Course(ContractModel):
    SCHEMA = "course/1"

    public_id: str | None = None
    system: ExamSystem = ExamSystem.CIE
    qualification: str | None = None
    native_code: str | None = None
    names: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)
    specification_version: str | None = None
    applicable_years: list[int] = field(default_factory=list)
    source_refs: list[SourceRef] = field(default_factory=list)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "Course":
        return cls(
            public_id=payload.get("public_id"),
            system=ExamSystem.coerce(_req(payload, "system", "course")),
            qualification=payload.get("qualification"),
            native_code=payload.get("native_code"),
            names=list(payload.get("names", [])),
            aliases=list(payload.get("aliases", [])),
            specification_version=payload.get("specification_version"),
            applicable_years=[int(y) for y in payload.get("applicable_years", [])],
            source_refs=[SourceRef.from_dict(s) for s in payload.get("source_refs", [])],
        )

    def validate(self) -> list[str]:
        problems = []
        if not self.native_code:
            problems.append("course: native code missing")
        if not self.names:
            problems.append("course: no name recorded")
        return problems


@dataclass
class ExaminationSystemModel(ContractModel):
    SCHEMA = "examination-system/1"

    public_id: str | None = None
    system: ExamSystem = ExamSystem.CIE
    names: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)
    qualifications: list[str] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)
    availability: str = "unknown"
    links: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ExaminationSystemModel":
        return cls(
            public_id=payload.get("public_id"),
            system=ExamSystem.coerce(_req(payload, "system", "examination_system")),
            names=list(payload.get("names", [])),
            aliases=list(payload.get("aliases", [])),
            qualifications=list(payload.get("qualifications", [])),
            capabilities=list(payload.get("capabilities", [])),
            availability=payload.get("availability", "unknown"),
            links={str(k): str(v) for k, v in payload.get("links", {}).items()},
        )


@dataclass
class Syllabus(ContractModel):
    SCHEMA = "syllabus/1"

    public_id: str | None = None
    course_ref: str | None = None
    title: str | None = None
    version: str | None = None
    applicability: str | None = None
    document_resources: list[dict[str, Any]] = field(default_factory=list)
    content_class: ContentClass = ContentClass.UNKNOWN

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "Syllabus":
        return cls(
            public_id=payload.get("public_id"),
            course_ref=payload.get("course_ref"),
            title=payload.get("title"),
            version=payload.get("version"),
            applicability=payload.get("applicability"),
            document_resources=list(payload.get("document_resources", [])),
            content_class=ContentClass.coerce(payload.get("content_class", "unknown")),
        )


@dataclass
class Tag(ContractModel):
    SCHEMA = "tag/1"

    public_id: str | None = None
    scheme: str | None = None
    version: str | None = None
    code: str | None = None
    parent: str | None = None
    label: str | None = None
    specification_ref: str | None = None
    assignment_method: str | None = None
    confidence: float | None = None
    review: str | None = None

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "Tag":
        return cls(
            public_id=payload.get("public_id"), scheme=payload.get("scheme"),
            version=payload.get("version"), code=payload.get("code"),
            parent=payload.get("parent"), label=payload.get("label"),
            specification_ref=payload.get("specification_ref"),
            assignment_method=payload.get("assignment_method"),
            confidence=payload.get("confidence"), review=payload.get("review"),
        )


@dataclass
class Material(ContractModel):
    SCHEMA = "material/1"

    public_id: str | None = None
    kind: str | None = None
    applicability: str | None = None
    candidate_facing: str | None = None
    access_mode: str | None = None
    resources: list[dict[str, Any]] = field(default_factory=list)
    owner: str | None = None
    content_class: ContentClass = ContentClass.UNKNOWN

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "Material":
        return cls(
            public_id=payload.get("public_id"), kind=payload.get("kind"),
            applicability=payload.get("applicability"),
            candidate_facing=payload.get("candidate_facing"),
            access_mode=payload.get("access_mode"),
            resources=list(payload.get("resources", [])),
            owner=payload.get("owner"),
            content_class=ContentClass.coerce(payload.get("content_class", "unknown")),
        )


@dataclass
class TimetableEvent(ContractModel):
    SCHEMA = "timetable-event/1"

    public_id: str | None = None
    system: ExamSystem = ExamSystem.CIE
    qualification: str | None = None
    zone: str | None = None
    course_ref: str | None = None
    component: str | None = None
    date: str | None = None
    session: str | None = None
    timezone: str | None = None
    duration_minutes: int | None = None
    source: SourceRef | None = None
    revision: str | None = None

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "TimetableEvent":
        return cls(
            public_id=payload.get("public_id"),
            system=ExamSystem.coerce(_req(payload, "system", "timetable_event")),
            qualification=payload.get("qualification"),
            zone=payload.get("zone"),
            course_ref=payload.get("course_ref"),
            component=payload.get("component"),
            date=payload.get("date"),
            session=payload.get("session"),
            timezone=payload.get("timezone"),
            duration_minutes=payload.get("duration_minutes"),
            source=SourceRef.from_dict(payload["source"]) if payload.get("source") else None,
            revision=payload.get("revision"),
        )

    def validate(self) -> list[str]:
        problems = []
        if self.date is None:
            problems.append("timetable_event: date unknown - keep it unknown, never invent one")
        if self.timezone is None and self.session:
            problems.append("timetable_event: session without timezone")
        return problems


@dataclass
class TimetableWindow(ContractModel):
    SCHEMA = "timetable-window/1"

    public_id: str | None = None
    original_text: str | None = None
    parsed_start: str | None = None
    parsed_end: str | None = None
    parsing_status: str = "unparsed"
    components: list[str] = field(default_factory=list)
    system: ExamSystem = ExamSystem.CIE
    qualification: str | None = None
    zone: str | None = None
    source: SourceRef | None = None
    revision: str | None = None

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "TimetableWindow":
        return cls(
            public_id=payload.get("public_id"),
            original_text=payload.get("original_text"),
            parsed_start=payload.get("parsed_start"),
            parsed_end=payload.get("parsed_end"),
            parsing_status=payload.get("parsing_status", "unparsed"),
            components=list(payload.get("components", [])),
            system=ExamSystem.coerce(payload.get("system", "cie")),
            qualification=payload.get("qualification"),
            zone=payload.get("zone"),
            source=SourceRef.from_dict(payload["source"]) if payload.get("source") else None,
            revision=payload.get("revision"),
        )

    def validate(self) -> list[str]:
        problems = []
        if self.parsing_status == "parsed" and (not self.parsed_start or not self.parsed_end):
            problems.append("timetable_window: marked parsed without start and end")
        if self.parsing_status != "parsed" and (self.parsed_start or self.parsed_end):
            problems.append("timetable_window: parsed bounds present but status is not parsed")
        return problems


@dataclass
class Coverage(ContractModel):
    SCHEMA = "coverage/1"

    public_id: str | None = None
    scope: str | None = None
    denominator: str | None = None
    denominator_known: bool = False
    observed: int = 0
    excluded: int = 0
    unknown: int = 0
    missing: int = 0
    partial: int = 0
    verified: int = 0
    exclusions: list[dict[str, Any]] = field(default_factory=list)
    computed_at: str | None = None
    evidence: list[str] = field(default_factory=list)
    derived_status: str = "unknown"
    percentage: float | None = None

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "Coverage":
        return cls(
            public_id=payload.get("public_id"),
            scope=payload.get("scope"),
            denominator=payload.get("denominator"),
            denominator_known=bool(payload.get("denominator_known", False)),
            observed=int(payload.get("observed", 0)),
            excluded=int(payload.get("excluded", 0)),
            unknown=int(payload.get("unknown", 0)),
            missing=int(payload.get("missing", 0)),
            partial=int(payload.get("partial", 0)),
            verified=int(payload.get("verified", 0)),
            exclusions=list(payload.get("exclusions", [])),
            computed_at=payload.get("computed_at"),
            evidence=list(payload.get("evidence", [])),
            derived_status=payload.get("derived_status", "unknown"),
            percentage=payload.get("percentage"),
        )

    def validate(self) -> list[str]:
        problems = []
        if not self.denominator_known and self.percentage is not None:
            problems.append("coverage: percentage computed with an unknown denominator")
        if self.excluded and not self.exclusions:
            problems.append("coverage: exclusions without reasons")
        if self.observed != self.excluded + self.unknown + self.missing + self.partial + self.verified:
            problems.append("coverage: observed count does not equal the sum of its buckets")
        return problems


@dataclass
class JobStatus(ContractModel):
    SCHEMA = "job-status/1"

    public_id: str | None = None
    scope: str | None = None
    input_revision: str | None = None
    stage: str = "unknown"
    counters: dict[str, int] = field(default_factory=dict)
    stop_reason: str | None = None
    resume_required: bool = False
    output_refs: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "JobStatus":
        return cls(
            public_id=payload.get("public_id"), scope=payload.get("scope"),
            input_revision=payload.get("input_revision"),
            stage=payload.get("stage", "unknown"),
            counters={str(k): int(v) for k, v in payload.get("counters", {}).items()},
            stop_reason=payload.get("stop_reason"),
            resume_required=bool(payload.get("resume_required", False)),
            output_refs=list(payload.get("output_refs", [])),
            evidence_refs=list(payload.get("evidence_refs", [])),
        )

    def validate(self) -> list[str]:
        problems = []
        if self.resume_required and not self.stop_reason:
            problems.append("job_status: resume required without a stop reason")
        return problems


# Fields ``from_dict`` refuses to do without: it raises ContractError when one is
# absent. Declared here so the generated JSON schemas and the loader cannot
# drift; every other field has a default and a payload may legitimately omit it.
REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "Option": ("key",),
    "TableCell": ("row", "column"),
    "Course": ("system",),
    "ExaminationSystemModel": ("system",),
    "TimetableEvent": ("system",),
}

MODELS: dict[str, type[ContractModel]] = {
    "answer": Answer,
    "asset": Asset,
    "container": Container,
    "coverage": Coverage,
    "course": Course,
    "examination_system": ExaminationSystemModel,
    "job_status": JobStatus,
    "material": Material,
    "question": Question,
    "region": Region,
    "syllabus": Syllabus,
    "tag": Tag,
    "timetable_event": TimetableEvent,
    "timetable_window": TimetableWindow,
}

__all__ = [
    "ContractError",
    "ContractModel",
    "Lineage",
    "SourceRef",
    "Gap",
    "Conflict",
    "ManualDecision",
    "Option",
    "OptionsPayload",
    "TableCell",
    "TablePayload",
    "MatchingPayload",
    "LabelsPayload",
    "TextPayload",
    "UnknownPayload",
    "PAYLOAD_BY_TYPE",
    "payload_from_dict",
    "Answer",
    "RequiredAsset",
    "Question",
    "Container",
    "Region",
    "Asset",
    "Course",
    "ExaminationSystemModel",
    "Syllabus",
    "Tag",
    "Material",
    "TimetableEvent",
    "TimetableWindow",
    "Coverage",
    "JobStatus",
    "MODELS",
    "REQUIRED_FIELDS",
    "UnknownType",
    "UNKNOWN",
]
