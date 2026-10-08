"""Fixture-backed providers (plan A05, 8.1-8.3).

Each provider reads exactly one A03 *synthetic* fixture and maps it onto the
frozen A04 contracts. The rules this module enforces:

* only synthetic fixtures are accepted - a provider refuses anything that is not
  labelled `fixture_kind == "synthetic"`, so real examination material can never
  enter the staged provider layer;
* every emitted model is `content_class = synthetic` and every answer stays
  `verification = "unverified"` - nothing is promoted to verified;
* an unsupported capability is a typed unsupported result, and a filter the
  provider cannot interpret is a typed filter_rejected result (never ignored);
* gaps the fixture actually shows (unknown date, answer conflict, missing answer
  slot, missing region geometry, required asset without bytes) are carried as
  explicit `Gap` records on the result.

The three real fixture providers cover CIE, Edexcel and IELTS. Tag, material and
timetable content is deferred to the active owner and is intentionally not
implemented here; requesting those capabilities yields typed unsupported
results.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Mapping

from ..contracts.base import Gap
from ..contracts.canonical import UNKNOWN, public_id
from ..contracts.enums import (
    AnswerMatchingMethod,
    ContainerKind,
    ContentClass,
    EntityKind,
    ExamSystem,
    GapCode,
    GapScope,
    QuestionType,
)
from ..contracts.models import (
    Answer,
    Asset,
    Conflict,
    Container,
    Course,
    Coverage,
    Lineage,
    ManualDecision,
    Option,
    OptionsPayload,
    Question,
    Region,
    RequiredAsset,
    SourceRef,
    TableCell,
    TablePayload,
    TextPayload,
    UnknownPayload,
)
from .capabilities import Availability, Capability
from .protocol import ProviderDescriptor
from .results import ProviderResult

_CIE = Capability  # readability alias for the descriptor tables below


def _gap(code: GapCode, scope: GapScope, detail: str) -> Gap:
    return Gap(code=code.value, scope=scope.value, detail=detail)


def _lineage(note: str, *parents: str) -> Lineage:
    return Lineage(operation="synthetic_fixture_map", parent_refs=list(parents), note=note)


def _passes(filters: Mapping[str, Any], **available: Any) -> bool:
    """True when every supplied filter matches one of its available candidates."""
    for key, wanted in filters.items():
        if key not in available:
            return False
        candidates = available[key]
        if candidates is None:
            return False
        if isinstance(candidates, (list, tuple, set, frozenset)):
            if str(wanted) not in {str(c) for c in candidates if c is not None}:
                return False
        elif str(wanted) != str(candidates):
            return False
    return True


class FixtureProvider:
    """Base class: load one synthetic fixture, dispatch by capability."""

    provider_id: str = ""
    exam_system: ExamSystem = ExamSystem.CIE
    display_name: str = ""
    capabilities: frozenset[Capability] = frozenset()
    supported_filters: dict[Capability, frozenset[str]] = {}
    limitations: tuple[str, ...] = ()
    availability: Availability = Availability.AVAILABLE

    def __init__(self, fixture_path: str | Path) -> None:
        self._path = Path(fixture_path)
        data = json.loads(self._path.read_text(encoding="utf-8"))
        if data.get("fixture_kind") != "synthetic":
            raise ValueError(
                f"{type(self).__name__} only accepts synthetic fixtures; "
                f"{self._path.name} is not labelled synthetic")
        self._data = data
        self.descriptor = ProviderDescriptor(
            provider_id=self.provider_id,
            exam_system=self.exam_system,
            display_name=self.display_name,
            capabilities=frozenset(self.capabilities),
            supported_filters={c: frozenset(f) for c, f in self.supported_filters.items()},
            availability=self.availability,
            limitations=tuple(self.limitations),
        )

    # -- dispatch ------------------------------------------------------------ #
    def query(self, capability: Capability, *, filters: Mapping[str, Any] | None = None,
              target: str | None = None) -> ProviderResult:
        cap = Capability.coerce(capability)
        if not self.descriptor.supports(cap):
            return ProviderResult.unsupported(
                self.provider_id, cap.value,
                detail=f"{self.provider_id} does not implement {cap.value}")
        unsupported = sorted(k for k in (filters or {}) if k not in self.descriptor.filters_for(cap))
        if unsupported:
            return ProviderResult.filter_rejected(
                self.provider_id, cap.value, filter_key=unsupported[0],
                detail=f"{self.provider_id} cannot interpret filter(s) {unsupported} for {cap.value}")
        handler = self._handlers().get(cap)
        if handler is None:
            return ProviderResult.unsupported(
                self.provider_id, cap.value,
                detail=f"{self.provider_id} declares {cap.value} but has no handler")
        return handler(dict(filters or {}), target)

    def _handlers(self) -> dict[Capability, Callable[[Mapping[str, Any], str | None], ProviderResult]]:
        raise NotImplementedError


# --------------------------------------------------------------------------- #
# CIE
# --------------------------------------------------------------------------- #
class CIEIndexProvider(FixtureProvider):
    """Maps `fixtures/synthetic/cie/cie-index-synthetic.json`."""

    provider_id = "cie_index_fixture"
    exam_system = ExamSystem.CIE
    display_name = "CIE synthetic index (Phase A fixture)"
    capabilities = frozenset({
        _CIE.DISCOVERY, _CIE.COURSES, _CIE.CONTAINERS, _CIE.QUESTIONS, _CIE.ANSWERS,
        _CIE.RESOURCES, _CIE.ASSETS, _CIE.REGIONS, _CIE.COVERAGE,
    })
    supported_filters = {
        _CIE.COURSES: frozenset({"subject"}),
        _CIE.CONTAINERS: frozenset({"subject", "year", "season", "paper"}),
        _CIE.QUESTIONS: frozenset({"subject", "year", "season", "paper", "question"}),
        _CIE.ANSWERS: frozenset(),
        _CIE.RESOURCES: frozenset({"subject", "year", "season", "paper"}),
        _CIE.ASSETS: frozenset(),
        _CIE.REGIONS: frozenset({"document_role"}),
        _CIE.COVERAGE: frozenset(),
    }
    limitations = (
        "synthetic shape fixture: no real CIE content and no real document hashes",
        "region bounding boxes are absent, so geometry is reported as a gap",
    )

    # -- helpers ------------------------------------------------------------- #
    def _identity(self) -> Mapping[str, Any]:
        return self._data["identity"]

    def _container_native(self) -> dict[str, Any]:
        ident = self._identity()
        return {k: ident.get(k) for k in ("subject", "year", "season", "paper", "date")}

    def _container_public_id(self) -> str:
        return public_id(EntityKind.CONTAINER, {
            "system": "cie", "kind": "paper", "native_identity": self._container_native()})

    def _handlers(self):
        return {
            _CIE.DISCOVERY: self._discovery,
            _CIE.COURSES: self._courses,
            _CIE.CONTAINERS: self._containers,
            _CIE.QUESTIONS: self._questions,
            _CIE.ANSWERS: self._answers,
            _CIE.RESOURCES: self._resources,
            _CIE.ASSETS: self._assets,
            _CIE.REGIONS: self._regions,
            _CIE.COVERAGE: self._coverage,
        }

    # -- operations ---------------------------------------------------------- #
    def _discovery(self, filters, target) -> ProviderResult:
        return ProviderResult.success(self.provider_id, Capability.DISCOVERY.value,
                                      items=[self.descriptor.to_dict()])

    def _courses(self, filters, target) -> ProviderResult:
        ident = self._identity()
        native_code = str(ident["subject"])
        if not _passes(filters, subject=[native_code, ident.get("subject_alias")]):
            return ProviderResult.success(self.provider_id, Capability.COURSES.value)
        fields = {"system": "cie", "qualification": UNKNOWN, "native_code": native_code,
                  "specification_version": None}
        course = Course(
            public_id=public_id(EntityKind.COURSE, fields), system=ExamSystem.CIE,
            qualification=None, native_code=native_code,
            names=[ident.get("subject_alias") or native_code],
            aliases=[ident["subject_alias"]] if ident.get("subject_alias") else [],
            specification_version=None,
            applicable_years=[ident["year"]] if ident.get("year") else [],
            source_refs=[SourceRef(source_id="synthetic-cie-index", provider_id=self.provider_id,
                                   locator={"fixture": self._path.name},
                                   content_class=ContentClass.SYNTHETIC)],
        )
        return ProviderResult.success(self.provider_id, Capability.COURSES.value, items=[course])

    def _containers(self, filters, target) -> ProviderResult:
        ident = self._identity()
        if not _passes(filters, subject=[str(ident["subject"]), ident.get("subject_alias")],
                       year=[ident.get("year")], season=[ident.get("season")],
                       paper=[ident.get("paper")]):
            return ProviderResult.success(self.provider_id, Capability.CONTAINERS.value)
        questions = self._flatten_questions()
        gaps = []
        if ident.get("date") is None:
            gaps.append(_gap(GapCode.UNKNOWN_DATE, GapScope.CONTAINER,
                             ident.get("date_unknown_reason") or "session date unknown"))
        container = Container(
            public_id=self._container_public_id(), kind=ContainerKind.PAPER,
            native_identity=self._container_native(),
            sections=[{"questions": [q.public_id for q in questions]}],
            resources=[{"role": d["role"], "sha256": d["sha256"]} for d in self._data["documents"]],
            question_refs=[q.public_id for q in questions],
            revision=None, coverage=None, content_class=ContentClass.SYNTHETIC,
            lineage=_lineage("mapped from the synthetic CIE index", "synthetic-cie-index"),
        )
        return ProviderResult.success(self.provider_id, Capability.CONTAINERS.value,
                                      items=[container], gaps=gaps)

    def _questions(self, filters, target) -> ProviderResult:
        ident = self._identity()
        if not _passes(filters, subject=[str(ident["subject"]), ident.get("subject_alias")],
                       year=[ident.get("year")], season=[ident.get("season")],
                       paper=[ident.get("paper")],
                       question=[q["question"] for q in self._data["questions"]]):
            return ProviderResult.success(self.provider_id, Capability.QUESTIONS.value)
        if target is not None:
            questions = [q for q in self._flatten_questions() if q.native_id == target]
            if not questions:
                return ProviderResult.not_found(
                    self.provider_id, Capability.QUESTIONS.value,
                    detail=f"question {target!r} is not in the synthetic CIE index")
        else:
            questions = self._flatten_questions()
        gaps = [g for q in questions for g in self._question_gaps(q)]
        return ProviderResult.success(self.provider_id, Capability.QUESTIONS.value,
                                      items=questions, gaps=gaps)

    def _answers(self, filters, target) -> ProviderResult:
        if target is None:
            return ProviderResult.failed(
                self.provider_id, Capability.ANSWERS.value, error_code="target_required",
                detail="answers requires a target question native id")
        questions = {q.native_id: q for q in self._flatten_questions()}
        if target not in questions:
            return ProviderResult.not_found(self.provider_id, Capability.ANSWERS.value,
                                            detail=f"question {target!r} not found")
        answers = questions[target].answers
        gaps = [_gap(GapCode.ANSWER_CONFLICT, GapScope.ANSWER,
                     "two candidate answers disagree and no manual decision is recorded")
                for a in answers if len(a.conflicts) > 1 and a.manual_decision is None]
        return ProviderResult.success(self.provider_id, Capability.ANSWERS.value,
                                      items=answers, gaps=gaps)

    def _resources(self, filters, target) -> ProviderResult:
        ident = self._identity()
        if not _passes(filters, subject=[str(ident["subject"])], year=[ident.get("year")],
                       season=[ident.get("season")], paper=[ident.get("paper")]):
            return ProviderResult.success(self.provider_id, Capability.RESOURCES.value)
        items = [self._document_asset(d) for d in self._data["documents"]]
        return ProviderResult.success(self.provider_id, Capability.RESOURCES.value, items=items)

    def _assets(self, filters, target) -> ProviderResult:
        items, gaps = [], []
        for q in self._flatten_questions():
            for raw in q.required_assets:
                items.append(Asset(
                    public_id=public_id(EntityKind.ASSET, {
                        "system": "cie", "media_type": None, "sha256": raw.sha256,
                        "storage_mode": "external_only"}),
                    media_type=None, byte_size=None, sha256=raw.sha256,
                    storage_mode="external_only", availability="unknown",
                    content_link=None, range_capable=None, revision=None))
                gaps.append(_gap(GapCode.MISSING_REQUIRED_IMAGE, GapScope.ASSET,
                                 f"required asset role={raw.role!r} is referenced by hash but "
                                 f"its bytes are not present in the synthetic fixture"))
        return ProviderResult.success(self.provider_id, Capability.ASSETS.value,
                                      items=items, gaps=gaps)

    def _regions(self, filters, target) -> ProviderResult:
        def iter_raw(items, path=()):
            for item in items:
                here = path + (str(item["question"]),)
                yield item, here
                yield from iter_raw(item.get("parts", []), here)

        qp_hash = next((d["sha256"] for d in self._data["documents"] if d["role"] == "qp"), None)
        role = "qp"
        if filters.get("document_role") and filters["document_role"] != role:
            return ProviderResult.success(self.provider_id, Capability.REGIONS.value)
        items, gaps = [], []
        for raw, _path in iter_raw(self._data["questions"]):
            number = str(raw["question"])
            if target is not None and number != target:
                continue
            page = raw.get("page")
            items.append(Region(
                public_id=public_id(EntityKind.REGION, {
                    "system": "cie", "document_role": role, "document_sha256": qp_hash,
                    "page": page, "bbox": None,
                    "coordinate_system": self._data["coordinate_system"]}),
                document_role=role, document_sha256=qp_hash, page=page, bbox=[],
                coordinate_system=self._data["coordinate_system"], rotation_transform=None,
                evidence_status="unverified",
                lineage=_lineage("mapped from the synthetic CIE index", number)))
            gaps.append(_gap(GapCode.MISSING_REGION, GapScope.REGION,
                             f"question {number} has a page reference but no bounding box"))
        return ProviderResult.success(self.provider_id, Capability.REGIONS.value,
                                      items=items, gaps=gaps)

    def _coverage(self, filters, target) -> ProviderResult:
        count = len(self._flatten_questions())
        native = self._container_native()
        cov = Coverage(
            public_id=public_id(EntityKind.COVERAGE, {
                "scope_kind": "container", "scope_native_identity": native,
                "denominator_kind": "synthetic_expected"}),
            scope=f"container:{self._container_public_id()}", denominator="synthetic_expected",
            denominator_known=False, observed=count, excluded=0, unknown=count,
            missing=0, partial=0, verified=0, computed_at=None,
            evidence=["synthetic fixture: not a real coverage measurement"],
            derived_status="unknown", percentage=None,
        )
        return ProviderResult.success(self.provider_id, Capability.COVERAGE.value, items=[cov])

    # -- construction -------------------------------------------------------- #
    def _document_asset(self, doc: Mapping[str, Any]) -> Asset:
        return Asset(
            public_id=public_id(EntityKind.ASSET, {
                "system": "cie", "media_type": "application/pdf",
                "sha256": doc["sha256"], "storage_mode": "external_only"}),
            media_type="application/pdf", byte_size=None, sha256=doc["sha256"],
            storage_mode="external_only", availability="unknown",
            content_link=None, range_capable=None, revision=None)

    def _flatten_questions(self) -> list[Question]:
        out: list[Question] = []
        for raw in self._data["questions"]:
            out.extend(self._build_question(raw, None, []).walk())
        return out

    def _question_gaps(self, q: Question) -> list[Gap]:
        gaps = []
        for problem in q.validate():
            if "no answer recorded" in problem:
                gaps.append(_gap(GapCode.MISSING_ANSWER, GapScope.QUESTION,
                                 f"question {q.native_id}: {problem}"))
            elif "required asset" in problem:
                gaps.append(_gap(GapCode.MISSING_REQUIRED_IMAGE, GapScope.QUESTION,
                                 f"question {q.native_id}: {problem}"))
        for a in q.answers:
            if len(a.conflicts) > 1 and a.manual_decision is None:
                gaps.append(_gap(GapCode.ANSWER_CONFLICT, GapScope.QUESTION,
                                 f"question {q.native_id}: conflicting answers without a decision"))
        return gaps

    def _build_question(self, raw: Mapping[str, Any], parent: str | None,
                        parent_path: list[str]) -> Question:
        number = str(raw["question"])
        path = parent_path + [number]
        qtype = QuestionType.TABLE_CHOICE if raw.get("table") else QuestionType.SHORT_ANSWER
        fields = {"system": "cie", "container_native_identity": self._container_native(),
                  "native_id": number, "number_path": path, "parent_native_id": parent}
        return Question(
            public_id=public_id(EntityKind.QUESTION, fields), native_id=number,
            container_ref=self._container_public_id(), number_path=path, parent_ref=parent,
            question_type=qtype, stem=raw.get("text"), payload=self._payload(raw, qtype),
            marks=raw.get("marks"),
            required_assets=[RequiredAsset(role=i["role"], sha256=i.get("sha256"), required=True)
                             for i in raw.get("required_images", [])],
            answers=self._answers_from(raw, number),
            quality=None, content_class=ContentClass.SYNTHETIC,
            lineage=_lineage("mapped from the synthetic CIE index", number),
            children=[self._build_question(p, number, path) for p in raw.get("parts", [])],
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

    def _answers_from(self, raw: Mapping[str, Any], number: str) -> list[Answer]:
        if "answer" not in raw and not raw.get("answer_conflicts"):
            return []
        conflicts = [Conflict.from_dict(c) for c in raw.get("answer_conflicts", [])]
        decision = (ManualDecision.from_dict(raw["manual_decision"])
                    if raw.get("manual_decision") else None)
        answer = Answer(
            public_id=public_id(EntityKind.ANSWER, {
                "system": "cie", "question_native_id": number,
                "source": "synthetic-ms", "native_answer_key": number}),
            question_ref=number, original_value=raw.get("answer"), normalized_value=None,
            alternatives=[], ordering_rule=None,
            matching_method=AnswerMatchingMethod.UNRESOLVED, verification="unverified",
            source=SourceRef(source_id="synthetic-ms", provider_id=self.provider_id,
                             locator={"fixture": self._path.name},
                             content_class=ContentClass.SYNTHETIC),
            conflicts=conflicts, manual_decision=decision,
            content_class=ContentClass.SYNTHETIC, lineage=_lineage("synthetic mark scheme", number),
        )
        return [answer]


# --------------------------------------------------------------------------- #
# Edexcel
# --------------------------------------------------------------------------- #
class EdexcelIndexProvider(FixtureProvider):
    """Maps `fixtures/synthetic/edexcel/index-synthetic.json`."""

    provider_id = "edexcel_index_fixture"
    exam_system = ExamSystem.EDEXCEL
    display_name = "Edexcel synthetic subject index (Phase A fixture)"
    capabilities = frozenset({_CIE.DISCOVERY, _CIE.COURSES, _CIE.CONTAINERS,
                              _CIE.RESOURCES, _CIE.COVERAGE})
    supported_filters = {
        _CIE.COURSES: frozenset({"qualification"}),
        _CIE.CONTAINERS: frozenset({"qualification", "session", "unit_code"}),
        _CIE.RESOURCES: frozenset({"session", "unit_code"}),
        _CIE.COVERAGE: frozenset(),
    }
    limitations = (
        "synthetic shape fixture: no real Edexcel content",
        "no question, answer, region or asset data in this fixture",
    )

    def _handlers(self):
        return {
            _CIE.DISCOVERY: self._discovery,
            _CIE.COURSES: self._courses,
            _CIE.CONTAINERS: self._containers,
            _CIE.RESOURCES: self._resources,
            _CIE.COVERAGE: self._coverage,
        }

    def _discovery(self, filters, target) -> ProviderResult:
        return ProviderResult.success(self.provider_id, Capability.DISCOVERY.value,
                                      items=[self.descriptor.to_dict()])

    def _subjects(self):
        return self._data["subjects"]

    def _courses(self, filters, target) -> ProviderResult:
        items = []
        for subject in self._subjects():
            if not _passes(filters, qualification=[subject.get("qualification_level")]):
                continue
            native_code = str(subject["native_id"])
            fields = {"system": "edexcel", "qualification": subject.get("qualification_level"),
                      "native_code": native_code,
                      "specification_version": subject.get("specification_code")}
            items.append(Course(
                public_id=public_id(EntityKind.COURSE, fields), system=ExamSystem.EDEXCEL,
                qualification=subject.get("qualification_level"), native_code=native_code,
                names=[subject.get("title") or native_code],
                aliases=list(subject.get("alias_ids", [])),
                specification_version=subject.get("specification_code"),
                applicable_years=[],
                source_refs=[SourceRef(source_id="synthetic-edexcel-index",
                                       provider_id=self.provider_id,
                                       locator={"fixture": self._path.name},
                                       content_class=ContentClass.SYNTHETIC)]))
        return ProviderResult.success(self.provider_id, Capability.COURSES.value, items=items)

    def _units(self):
        for subject in self._subjects():
            for unit in subject.get("units", []):
                yield subject, unit

    def _containers(self, filters, target) -> ProviderResult:
        items, gaps = [], []
        for subject, unit in self._units():
            sessions = [s.get("session") for s in unit.get("sessions", [])]
            if not _passes(filters, qualification=[subject.get("qualification_level")],
                           session=sessions, unit_code=[unit.get("unit_code")]):
                continue
            native = {"qualification_level": subject.get("qualification_level"),
                      "unit_code": unit.get("unit_code"), "paper_code": unit.get("paper_code")}
            fields = {"system": "edexcel", "kind": "paper", "native_identity": native}
            items.append(Container(
                public_id=public_id(EntityKind.CONTAINER, fields), kind=ContainerKind.PAPER,
                native_identity=native,
                sections=[{"unit": unit.get("native_id"), "sessions": sessions}],
                resources=[{"role": d["role"], "sha256": d["sha256"]}
                           for d in unit.get("documents", [])],
                question_refs=[], revision=None, coverage=None,
                content_class=ContentClass.SYNTHETIC,
                lineage=_lineage("mapped from the synthetic Edexcel index",
                                 str(subject.get("native_id")))))
            for session in unit.get("sessions", []):
                if session.get("date") is None:
                    gaps.append(_gap(GapCode.UNKNOWN_DATE, GapScope.CONTAINER,
                                     session.get("date_unknown_reason") or "session date unknown"))
        return ProviderResult.success(self.provider_id, Capability.CONTAINERS.value,
                                      items=items, gaps=gaps)

    def _resources(self, filters, target) -> ProviderResult:
        items = []
        for subject, unit in self._units():
            sessions = [s.get("session") for s in unit.get("sessions", [])]
            if not _passes(filters, session=sessions, unit_code=[unit.get("unit_code")]):
                continue
            for doc in unit.get("documents", []):
                items.append(Asset(
                    public_id=public_id(EntityKind.ASSET, {
                        "system": "edexcel", "media_type": "application/pdf",
                        "sha256": doc["sha256"], "storage_mode": "external_only"}),
                    media_type="application/pdf", byte_size=None, sha256=doc["sha256"],
                    storage_mode="external_only", availability="unknown",
                    content_link=None, range_capable=None, revision=None))
        return ProviderResult.success(self.provider_id, Capability.RESOURCES.value, items=items)

    def _coverage(self, filters, target) -> ProviderResult:
        subjects = self._subjects()
        units = list(self._units())
        native = {"board": "edexcel"}
        cov = Coverage(
            public_id=public_id(EntityKind.COVERAGE, {
                "scope_kind": "system", "scope_native_identity": native,
                "denominator_kind": "synthetic_expected"}),
            scope="system:edexcel", denominator="synthetic_expected", denominator_known=False,
            observed=len(units), excluded=0, unknown=len(units), missing=0, partial=0,
            verified=0, evidence=[f"synthetic fixture with {len(subjects)} subject(s)"],
            derived_status="unknown", percentage=None,
        )
        return ProviderResult.success(self.provider_id, Capability.COVERAGE.value, items=[cov])


# --------------------------------------------------------------------------- #
# IELTS
# --------------------------------------------------------------------------- #
class IELTSQuestionsProvider(FixtureProvider):
    """Maps `fixtures/synthetic/ielts/questions-synthetic.json`."""

    provider_id = "ielts_questions_fixture"
    exam_system = ExamSystem.IELTS
    display_name = "IELTS synthetic question book (Phase A fixture)"
    capabilities = frozenset({_CIE.DISCOVERY, _CIE.COURSES, _CIE.CONTAINERS, _CIE.QUESTIONS,
                              _CIE.ANSWERS, _CIE.ASSETS, _CIE.COVERAGE})
    supported_filters = {
        _CIE.COURSES: frozenset({"book"}),
        _CIE.CONTAINERS: frozenset({"book"}),
        _CIE.QUESTIONS: frozenset({"book"}),
        _CIE.ANSWERS: frozenset(),
        _CIE.ASSETS: frozenset(),
        _CIE.COVERAGE: frozenset(),
    }
    limitations = (
        "synthetic shape fixture: no real IELTS content",
        "a book number must never be read as an examination date, so no year filter is accepted",
        "no region data in this fixture",
    )

    def _book(self) -> Mapping[str, Any]:
        return self._data["book"]

    def _container_native(self) -> dict[str, Any]:
        return {"book": self._book()["native_id"],
                "revision": self._data.get("dataset_revision")}

    def _container_public_id(self) -> str:
        return public_id(EntityKind.CONTAINER, {
            "system": "ielts", "kind": "book", "native_identity": self._container_native()})

    def _handlers(self):
        return {
            _CIE.DISCOVERY: self._discovery,
            _CIE.COURSES: self._courses,
            _CIE.CONTAINERS: self._containers,
            _CIE.QUESTIONS: self._questions,
            _CIE.ANSWERS: self._answers,
            _CIE.ASSETS: self._assets,
            _CIE.COVERAGE: self._coverage,
        }

    def _discovery(self, filters, target) -> ProviderResult:
        return ProviderResult.success(self.provider_id, Capability.DISCOVERY.value,
                                      items=[self.descriptor.to_dict()])

    def _courses(self, filters, target) -> ProviderResult:
        book = self._book()
        if not _passes(filters, book=[book["native_id"], *book.get("alias_ids", [])]):
            return ProviderResult.success(self.provider_id, Capability.COURSES.value)
        native_code = str(book["native_id"])
        fields = {"system": "ielts", "qualification": UNKNOWN, "native_code": native_code,
                  "specification_version": None}
        course = Course(
            public_id=public_id(EntityKind.COURSE, fields), system=ExamSystem.IELTS,
            qualification=None, native_code=native_code,
            names=[book.get("title") or native_code], aliases=list(book.get("alias_ids", [])),
            specification_version=None, applicable_years=[],
            source_refs=[SourceRef(source_id="synthetic-ielts-questions",
                                   provider_id=self.provider_id,
                                   locator={"fixture": self._path.name},
                                   content_class=ContentClass.SYNTHETIC)])
        return ProviderResult.success(self.provider_id, Capability.COURSES.value, items=[course])

    def _containers(self, filters, target) -> ProviderResult:
        book = self._book()
        if not _passes(filters, book=[book["native_id"], *book.get("alias_ids", [])]):
            return ProviderResult.success(self.provider_id, Capability.CONTAINERS.value)
        questions = self._flatten_questions()
        container = Container(
            public_id=self._container_public_id(), kind=ContainerKind.BOOK,
            native_identity=self._container_native(),
            sections=[{"questions": [q.public_id for q in questions]}],
            resources=[{"role": d["role"], "sha256": d["sha256"]} for d in self._data["documents"]],
            question_refs=[q.public_id for q in questions],
            revision=self._data.get("dataset_revision"), coverage=None,
            content_class=ContentClass.SYNTHETIC,
            lineage=_lineage("mapped from the synthetic IELTS book", book["native_id"]),
        )
        return ProviderResult.success(self.provider_id, Capability.CONTAINERS.value,
                                      items=[container])

    def _questions(self, filters, target) -> ProviderResult:
        book = self._book()
        if not _passes(filters, book=[book["native_id"], *book.get("alias_ids", [])]):
            return ProviderResult.success(self.provider_id, Capability.QUESTIONS.value)
        if target is not None:
            questions = [q for q in self._flatten_questions() if q.native_id == target]
            if not questions:
                return ProviderResult.not_found(
                    self.provider_id, Capability.QUESTIONS.value,
                    detail=f"question {target!r} is not in the synthetic IELTS book")
        else:
            questions = self._flatten_questions()
        gaps = [g for q in questions for g in self._question_gaps(q)]
        return ProviderResult.success(self.provider_id, Capability.QUESTIONS.value,
                                      items=questions, gaps=gaps)

    def _answers(self, filters, target) -> ProviderResult:
        if target is None:
            return ProviderResult.failed(
                self.provider_id, Capability.ANSWERS.value, error_code="target_required",
                detail="answers requires a target question native id")
        questions = {q.native_id: q for q in self._flatten_questions()}
        if target not in questions:
            return ProviderResult.not_found(self.provider_id, Capability.ANSWERS.value,
                                            detail=f"question {target!r} not found")
        question = questions[target]
        if not question.answers:
            return ProviderResult.success(
                self.provider_id, Capability.ANSWERS.value, items=[],
                gaps=[_gap(GapCode.MISSING_ANSWER_SLOT, GapScope.ANSWER,
                           f"question {target} has no answer slot; the gap is preserved "
                           f"and is never fabricated")])
        gaps = [_gap(GapCode.ANSWER_CONFLICT, GapScope.ANSWER,
                     "two candidate answers disagree and no manual decision is recorded")
                for a in question.answers if len(a.conflicts) > 1 and a.manual_decision is None]
        return ProviderResult.success(self.provider_id, Capability.ANSWERS.value,
                                      items=question.answers, gaps=gaps)

    def _assets(self, filters, target) -> ProviderResult:
        items, gaps = [], []
        for q in self._flatten_questions():
            for raw in q.required_assets:
                items.append(Asset(
                    public_id=public_id(EntityKind.ASSET, {
                        "system": "ielts", "media_type": None, "sha256": raw.sha256,
                        "storage_mode": "external_only"}),
                    media_type=None, byte_size=None, sha256=raw.sha256,
                    storage_mode="external_only", availability="unknown",
                    content_link=None, range_capable=None, revision=None))
                gaps.append(_gap(GapCode.MISSING_REQUIRED_IMAGE, GapScope.ASSET,
                                 f"required asset role={raw.role!r} is referenced by hash but "
                                 f"its bytes are not present in the synthetic fixture"))
        return ProviderResult.success(self.provider_id, Capability.ASSETS.value,
                                      items=items, gaps=gaps)

    def _coverage(self, filters, target) -> ProviderResult:
        slots = self._data["answer_slots"]
        present, missing = list(slots["present"]), list(slots["missing"])
        native = self._container_native()
        cov = Coverage(
            public_id=public_id(EntityKind.COVERAGE, {
                "scope_kind": "container", "scope_native_identity": native,
                "denominator_kind": "answer_slots"}),
            scope=f"container:{self._container_public_id()}", denominator="answer_slots",
            denominator_known=True, observed=len(present) + len(missing), excluded=0,
            unknown=len(present), missing=len(missing), partial=0, verified=0,
            evidence=["synthetic fixture: present slots are unverified, missing slots are gaps"],
            derived_status="unknown", percentage=None,
        )
        return ProviderResult.success(self.provider_id, Capability.COVERAGE.value, items=[cov])

    # -- construction -------------------------------------------------------- #
    def _flatten_questions(self) -> list[Question]:
        out: list[Question] = []
        for raw in self._data["questions"]:
            out.extend(self._build_question(raw, None, []).walk())
        return out

    def _question_gaps(self, q: Question) -> list[Gap]:
        gaps = []
        if q.question_type is QuestionType.UNKNOWN and not q.answers and q.stem is None:
            gaps.append(_gap(GapCode.MISSING_ANSWER_SLOT, GapScope.QUESTION,
                             f"question {q.native_id} is an absent answer slot"))
        for problem in q.validate():
            if "no answer recorded" in problem and q.stem is not None and q.parent_ref is None:
                gaps.append(_gap(GapCode.MISSING_ANSWER, GapScope.QUESTION,
                                 f"question {q.native_id}: {problem}"))
        for a in q.answers:
            if len(a.conflicts) > 1 and a.manual_decision is None:
                gaps.append(_gap(GapCode.ANSWER_CONFLICT, GapScope.QUESTION,
                                 f"question {q.native_id}: conflicting answers without a decision"))
        return gaps

    def _build_question(self, raw: Mapping[str, Any], parent: str | None,
                        parent_path: list[str]) -> Question:
        number = str(raw["native_id"])
        path = parent_path + [number]
        qtype, payload = self._payload(raw)
        fields = {"system": "ielts", "container_native_identity": self._container_native(),
                  "native_id": number, "number_path": path, "parent_native_id": parent}
        return Question(
            public_id=public_id(EntityKind.QUESTION, fields), native_id=number,
            container_ref=self._container_public_id(), number_path=path, parent_ref=parent,
            question_type=qtype, stem=raw.get("prompt"), payload=payload, marks=None,
            required_assets=[RequiredAsset(role=i["role"], sha256=i.get("sha256"), required=True)
                             for i in raw.get("required_images", [])],
            answers=self._answers_from(raw, number),
            quality=None, content_class=ContentClass.SYNTHETIC,
            lineage=_lineage("mapped from the synthetic IELTS book", number),
            children=[self._build_question(c, number, path) for c in raw.get("children", [])],
        )

    @staticmethod
    def _payload(raw: Mapping[str, Any]):
        kind = raw.get("kind")
        if kind == "table_choice":
            table = raw["table"]
            cell = table.get("answer_cell")
            cells = ([TableCell(row=int(cell["row"]), column=int(cell["column"]),
                                value=cell.get("value"))] if cell else [])
            return QuestionType.TABLE_CHOICE, TablePayload(
                columns=list(table["columns"]), rows=[list(r) for r in table["rows"]],
                answer_cells=cells)
        if kind == "grouped_alternatives":
            keys = [raw.get("answer")] + list(raw.get("alternative_answers", []))
            options = [Option(key=str(k)) for k in keys if k is not None]
            return QuestionType.SINGLE_CHOICE, OptionsPayload(options=options)
        if kind == "missing_answer_slot":
            return QuestionType.UNKNOWN, UnknownPayload(native_shape="missing_answer_slot",
                                                        raw={"answer_slot": raw.get("answer_slot")})
        return QuestionType.SHORT_ANSWER, TextPayload(stem=raw.get("prompt"))

    def _answers_from(self, raw: Mapping[str, Any], number: str) -> list[Answer]:
        if raw.get("missing_answer") or (raw.get("answer") is None and not raw.get("answer_conflicts")):
            return []
        conflicts = [Conflict.from_dict(c) for c in raw.get("answer_conflicts", [])]
        decision = (ManualDecision.from_dict(raw["manual_decision"])
                    if raw.get("manual_decision") else None)
        answer = Answer(
            public_id=public_id(EntityKind.ANSWER, {
                "system": "ielts", "question_native_id": number,
                "source": "synthetic-ielts-answer", "native_answer_key": number}),
            question_ref=number, original_value=raw.get("answer"), normalized_value=None,
            alternatives=list(raw.get("alternative_answers", [])), ordering_rule=None,
            matching_method=(AnswerMatchingMethod.GROUPED if raw.get("alternative_answers")
                             else AnswerMatchingMethod.UNRESOLVED),
            verification="unverified",
            source=SourceRef(source_id="synthetic-ielts-answer", provider_id=self.provider_id,
                             locator={"fixture": self._path.name},
                             content_class=ContentClass.SYNTHETIC),
            conflicts=conflicts, manual_decision=decision,
            content_class=ContentClass.SYNTHETIC,
            lineage=_lineage("synthetic IELTS answer key", number),
        )
        return [answer]


# --------------------------------------------------------------------------- #
# explicit edge providers (used by dispatch tests and the probe tool)
# --------------------------------------------------------------------------- #
class NullProvider:
    """A provider that always succeeds with no items (proves empty != unsupported)."""

    def __init__(self, provider_id: str = "null_fixture", *,
                 capabilities: frozenset[Capability] = frozenset({Capability.DISCOVERY}),
                 availability: Availability = Availability.AVAILABLE) -> None:
        self.descriptor = ProviderDescriptor(
            provider_id=provider_id, exam_system=ExamSystem.CIE,
            display_name="null fixture provider", capabilities=frozenset(capabilities),
            availability=availability, limitations=("returns genuine empty successes",))

    def query(self, capability, *, filters=None, target=None) -> ProviderResult:
        cap = Capability.coerce(capability)
        if not self.descriptor.supports(cap):
            return ProviderResult.unsupported(self.descriptor.provider_id, cap.value)
        return ProviderResult.success(self.descriptor.provider_id, cap.value)


class UnavailableProvider(NullProvider):
    """Registered but not currently available (plan A05: unavailable optional provider)."""

    def __init__(self, provider_id: str = "optional_unavailable") -> None:
        super().__init__(provider_id, capabilities=frozenset({Capability.COURSES}),
                         availability=Availability.UNAVAILABLE)


class FailingProvider(NullProvider):
    """Raises inside `query`, to prove dispatch sanitizes an unexpected failure."""

    def __init__(self, provider_id: str = "failing_fixture") -> None:
        super().__init__(provider_id, capabilities=frozenset({Capability.COURSES}))

    def query(self, capability, *, filters=None, target=None) -> ProviderResult:
        raise RuntimeError("synthetic provider failure with C:\\private\\path\\secret.db")


__all__ = [
    "FixtureProvider",
    "CIEIndexProvider",
    "EdexcelIndexProvider",
    "IELTSQuestionsProvider",
    "NullProvider",
    "UnavailableProvider",
    "FailingProvider",
]
