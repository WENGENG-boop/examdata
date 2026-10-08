"""TOEFL read adapters (plan A08).

Three read-only adapters over staged TOEFL sources:

* :class:`TOEFLReadingIndexAdapter` reads the *copied snapshot* of the TOEFL
  reading index. Each passage keeps its native id, its KMF link and its KMF hash;
  a passage whose KMF hash or title repeats another passage is an unresolved
  identity, never merged. The index's own ``counts.total`` is recorded but is
  **not** treated as a completeness claim.
* :class:`TOEFLQuestionSetAdapter` reads a *synthetic* question-set fixture and
  keeps Official / TPO / jj identities distinct, a restricted ``jj`` entry
  metadata-only, table rows/columns, multiple-selection information, unknown exam
  dates, missing options/tables and a strict KMF URL check.
* :class:`TOEFLCacheAdapter` reparses a *synthetic* cache document and reports a
  malformed or duplicate entry instead of dropping it.

A URL is validated and never requested. Nothing here promotes synthetic content to
verified, and no exam date, option, table cell or answer is ever invented.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from ..contracts.canonical import UNKNOWN, public_id
from ..contracts.enums import (
    AnswerMatchingMethod,
    ContainerKind,
    ContentClass,
    EntityKind,
    ExamSystem,
    GapScope,
    QuestionType,
)
from ..contracts.models import (
    Answer,
    Asset,
    Container,
    Course,
    Lineage,
    Option,
    OptionsPayload,
    Question,
    RequiredAsset,
    SourceRef,
    TableCell,
    TablePayload,
    TextPayload,
    UnknownPayload,
)
from .bundle import AdapterBundle
from .source_reader import (
    CacheEntry,
    SourceKind,
    SourceProblem,
    SourceProblemCode,
    SUPPORTED_SCHEMA_VERSIONS,
    iter_cache_entries,
    read_source,
    source_problem,
    validate_kmf_url,
)

COPIED_READING_INDEX_SOURCE = "copied-toefl-reading-index"
SYNTHETIC_QUESTION_SET_SOURCE = "synthetic-toefl-question-set"
SYNTHETIC_CACHE_SOURCE = "synthetic-toefl-cache"

# The three identity classes the plan keeps distinct.
TOEFL_SOURCE_KINDS = ("official", "tpo", "jj")


# --------------------------------------------------------------------------- #
# copied reading index
# --------------------------------------------------------------------------- #
class TOEFLReadingIndexAdapter:
    """Map the copied TOEFL reading index onto containers, one per passage."""

    provider_id = "toefl_reading_index_adapter"
    system = ExamSystem.TOEFL

    def __init__(self, index_path: str | Path) -> None:
        self._path = Path(index_path)

    def bundle(self) -> AdapterBundle:
        data, kind, problems = read_source(self._path,
                                           allowed_kinds=(SourceKind.COPIED_SNAPSHOT,))
        if data is None:
            return AdapterBundle(
                system=self.system,
                source={"fixture": self._path.name, "kind": kind.value, "read": "failed"},
                problems=problems)
        problems = list(problems)
        items = data.get("items") or []

        containers: list[Container] = []
        seen_hash: dict[str, str] = {}
        seen_title: dict[str, str] = {}
        for raw in items:
            native_id = str(raw.get("id") or raw.get("kmf_hash") or "")
            kmf_hash = raw.get("kmf_hash")
            title = raw.get("title")
            if kmf_hash and kmf_hash in seen_hash:
                problems.append(source_problem(
                    SourceProblemCode.UNRESOLVED_IDENTITY, GapScope.CONTAINER,
                    f"passage {native_id!r} repeats KMF hash {kmf_hash!r} already used by "
                    f"{seen_hash[kmf_hash]!r}; the two identities are unresolved and are "
                    f"never merged", native_ref=native_id))
            elif kmf_hash:
                seen_hash[kmf_hash] = native_id
            if title and title in seen_title:
                problems.append(source_problem(
                    SourceProblemCode.UNRESOLVED_IDENTITY, GapScope.CONTAINER,
                    f"passage {native_id!r} repeats the title {title!r} already used by "
                    f"{seen_title[title]!r}; a title is not an identity and the passages "
                    f"are never merged", native_ref=native_id))
            elif title:
                seen_title[title] = native_id

            ok, reason = validate_kmf_url(raw.get("link"))
            if not ok:
                problems.append(source_problem(
                    SourceProblemCode.INVALID_KMF_URL, GapScope.CONTAINER,
                    f"passage {native_id!r} link is not a valid KMF detail URL ({reason}); "
                    f"the URL is never requested", native_ref=native_id))

            native = {"collection": "toefl-reading-index", "passage": native_id,
                      "kmf_hash": kmf_hash}
            containers.append(Container(
                public_id=public_id(EntityKind.CONTAINER, {
                    "system": "toefl", "kind": "set", "native_identity": native}),
                kind=ContainerKind.SET, native_identity=native,
                sections=[{"title": title, "file": raw.get("file"),
                           "paragraphs": raw.get("paragraphs"), "chars": raw.get("chars")}],
                resources=[{"role": "source_link", "url": raw.get("link")}],
                question_refs=[], revision=data.get("checked_at"), coverage=None,
                content_class=ContentClass.OFFICIAL,
                lineage=Lineage(operation="adapter_container_map",
                                parent_refs=[native_id],
                                note="passage mapped from the copied TOEFL reading index"),
            ))

        declared_total = (data.get("counts") or {}).get("total")
        return AdapterBundle(
            system=self.system,
            source={"fixture": self._path.name, "kind": kind.value,
                    "source": data.get("source"), "checked_at": data.get("checked_at"),
                    "declared_total": declared_total,
                    "items_read": len(items),
                    # the index's own count is not a completeness claim: coverage is
                    # never asserted for a copied snapshot (plan 4.6)
                    "coverage_claimed": False},
            containers=containers, problems=problems)


# --------------------------------------------------------------------------- #
# synthetic question set
# --------------------------------------------------------------------------- #
class TOEFLQuestionSetAdapter:
    """Map a synthetic TOEFL question-set fixture onto the frozen contracts."""

    provider_id = "toefl_question_set_adapter"
    system = ExamSystem.TOEFL

    def __init__(self, fixture_path: str | Path) -> None:
        self._path = Path(fixture_path)

    def bundle(self) -> AdapterBundle:
        data, kind, problems = read_source(self._path,
                                           allowed_kinds=(SourceKind.SYNTHETIC,))
        if data is None:
            return AdapterBundle(
                system=self.system,
                source={"fixture": self._path.name, "kind": kind.value, "read": "failed"},
                problems=problems)
        problems = list(problems)
        problems.extend(self._schema_problems(data))

        sets = data.get("sets") or []
        containers: list[Container] = []
        questions: list[Question] = []
        assets: list[Asset] = []

        for raw in sets:
            set_native = str(raw.get("native_id"))
            source_kind = str(raw.get("source_kind") or "unknown")
            container_pid = self._container_public_id(set_native, source_kind)

            ok, reason = validate_kmf_url(raw.get("kmf_url"))
            if not ok:
                problems.append(source_problem(
                    SourceProblemCode.INVALID_KMF_URL, GapScope.CONTAINER,
                    f"set {set_native!r} kmf_url is not a valid KMF detail URL ({reason}); "
                    f"the URL is never requested", native_ref=set_native))

            if raw.get("restricted"):
                problems.append(source_problem(
                    SourceProblemCode.RESTRICTED_SOURCE, GapScope.CONTAINER,
                    f"set {set_native!r} is restricted ({raw.get('restricted_reason') or 'no reason given'}); "
                    f"it is kept as metadata only and its content is never read",
                    native_ref=set_native))

            if raw.get("exam_date") is None:
                problems.append(source_problem(
                    SourceProblemCode.UNKNOWN_DATE, GapScope.CONTAINER,
                    f"set {set_native!r} records no exam date "
                    f"({raw.get('exam_date_unknown_reason') or 'no reason given'}); the "
                    f"date stays unknown and is never inferred", native_ref=set_native))

            set_questions: list[Question] = []
            if not raw.get("restricted"):
                for question in raw.get("questions") or []:
                    built = self._build_question(question, set_native, source_kind,
                                                 container_pid, problems)
                    set_questions.append(built)
                    assets.extend(self._assets_for(built, problems))
            questions.extend(set_questions)

            native = {"set": set_native, "source_kind": source_kind}
            containers.append(Container(
                public_id=container_pid, kind=ContainerKind.SET, native_identity=native,
                sections=[{"questions": [q.public_id for q in set_questions],
                           "restricted": bool(raw.get("restricted")),
                           "exam_date": raw.get("exam_date")}],
                resources=[{"role": "source_link", "url": raw.get("kmf_url")}],
                question_refs=[q.public_id for q in set_questions],
                revision=data.get("dataset_revision"), coverage=None,
                content_class=ContentClass.SYNTHETIC,
                lineage=Lineage(operation="adapter_container_map",
                                parent_refs=[set_native],
                                note=f"question set mapped from a synthetic TOEFL fixture "
                                     f"(source_kind={source_kind})"),
            ))

        return AdapterBundle(
            system=self.system,
            source={"fixture": self._path.name, "kind": kind.value,
                    "board": data.get("board"),
                    "dataset_revision": data.get("dataset_revision"),
                    "sets": len(sets)},
            courses=self._courses(sets), containers=containers, questions=questions,
            answers=[a for q in questions for a in q.answers], assets=assets,
            problems=problems)

    # -- construction -------------------------------------------------------- #
    @staticmethod
    def _schema_problems(data: Mapping[str, Any]) -> list[SourceProblem]:
        version = data.get("schema_version")
        if version is None:
            return []
        if str(version) not in SUPPORTED_SCHEMA_VERSIONS:
            return [source_problem(
                SourceProblemCode.UNSUPPORTED_SCHEMA_VERSION, GapScope.SYSTEM,
                f"question set declares schema_version {version!r}; supported: "
                f"{sorted(SUPPORTED_SCHEMA_VERSIONS)}")]
        return []

    @staticmethod
    def _container_public_id(set_native: str, source_kind: str) -> str:
        return public_id(EntityKind.CONTAINER, {
            "system": "toefl", "kind": "set",
            "native_identity": {"set": set_native, "source_kind": source_kind}})

    def _courses(self, sets: list[Mapping[str, Any]]) -> list[Course]:
        kinds = sorted({str(s.get("source_kind") or "unknown") for s in sets})
        courses: list[Course] = []
        for source_kind in kinds:
            fields = {"system": "toefl", "qualification": UNKNOWN,
                      "native_code": source_kind, "specification_version": None}
            courses.append(Course(
                public_id=public_id(EntityKind.COURSE, fields), system=ExamSystem.TOEFL,
                qualification=None, native_code=source_kind, names=[source_kind],
                aliases=[], specification_version=None, applicable_years=[],
                source_refs=[SourceRef(source_id=SYNTHETIC_QUESTION_SET_SOURCE,
                                       provider_id=self.provider_id,
                                       locator={"fixture": self._path.name},
                                       content_class=ContentClass.SYNTHETIC)]))
        return courses

    def _build_question(self, raw: Mapping[str, Any], set_native: str, source_kind: str,
                        container_pid: str, problems: list[SourceProblem]) -> Question:
        number = str(raw.get("native_id"))
        path = [number]
        qtype, payload, payload_problem = self._payload(raw, number)
        if payload_problem is not None:
            problems.append(payload_problem)
        return Question(
            public_id=public_id(EntityKind.QUESTION, {
                "system": "toefl",
                "container_native_identity": {"set": set_native,
                                              "source_kind": source_kind},
                "native_id": number, "number_path": path, "parent_native_id": None}),
            native_id=number, container_ref=container_pid, number_path=path,
            parent_ref=None, group_ref=None, question_type=qtype, stem=raw.get("prompt"),
            payload=payload, marks=raw.get("marks"),
            required_assets=[RequiredAsset(role=i.get("role", ""), sha256=i.get("sha256"),
                                           required=True)
                             for i in (raw.get("required_images") or [])],
            answers=self._answers_from(raw, number), quality=None,
            content_class=ContentClass.SYNTHETIC,
            lineage=Lineage(operation="adapter_question_map", parent_refs=[number],
                            note=f"question mapped from a synthetic TOEFL set "
                                 f"(source_kind={source_kind})"),
            children=[])

    def _payload(self, raw: Mapping[str, Any], number: str):
        kind = raw.get("kind")
        if kind == "table_choice":
            table = raw.get("table") or {}
            columns = list(table.get("columns") or [])
            rows = [list(r) for r in (table.get("rows") or [])]
            cell = table.get("answer_cell")
            if not columns or not rows:
                return (QuestionType.TABLE_CHOICE,
                        TablePayload(columns=columns, rows=rows, answer_cells=[]),
                        source_problem(
                            SourceProblemCode.MISSING_TABLE, GapScope.QUESTION,
                            f"question {number} declares a table choice but records no table "
                            f"structure; no row or column is invented", native_ref=number))
            cells = ([TableCell(row=int(cell["row"]), column=int(cell["column"]),
                                value=cell.get("value"))] if cell else [])
            return (QuestionType.TABLE_CHOICE,
                    TablePayload(columns=columns, rows=rows, answer_cells=cells), None)
        if kind in ("multiple_choice", "single_choice", "multiple_selection"):
            options = list(raw.get("options") or [])
            qtype = (QuestionType.SINGLE_CHOICE if kind == "single_choice"
                     else QuestionType.MULTIPLE_CHOICE)
            if not options:
                return (qtype, OptionsPayload(options=[]), source_problem(
                    SourceProblemCode.MISSING_OPTIONS, GapScope.QUESTION,
                    f"question {number} declares a choice question but records no options; "
                    f"no option is invented", native_ref=number))
            return qtype, OptionsPayload(options=[Option(key=str(k)) for k in options]), None
        return QuestionType.FILL_BLANK, TextPayload(stem=raw.get("prompt")), None

    def _answers_from(self, raw: Mapping[str, Any], number: str) -> list[Answer]:
        if raw.get("answer") is None:
            return []
        selected = list(raw.get("selected") or [])
        answer = raw.get("answer")
        selection_count = raw.get("selection_count")
        if selection_count is None:
            selection_count = len(selected) or 1
        alternatives = [v for v in selected if v != answer]
        multi = int(selection_count) > 1
        note = f"answer stated on the synthetic TOEFL question (selection_count={selection_count})"
        return [Answer(
            public_id=public_id(EntityKind.ANSWER, {
                "system": "toefl", "question_native_id": number,
                "source": SYNTHETIC_QUESTION_SET_SOURCE, "native_answer_key": number}),
            question_ref=number, original_value=answer, normalized_value=None,
            alternatives=alternatives, ordering_rule=None,
            matching_method=(AnswerMatchingMethod.IN_ANY_ORDER if multi
                             else AnswerMatchingMethod.EXACT),
            verification="unverified",
            source=SourceRef(source_id=SYNTHETIC_QUESTION_SET_SOURCE,
                             provider_id=self.provider_id,
                             locator={"fixture": self._path.name},
                             content_class=ContentClass.SYNTHETIC),
            conflicts=[], manual_decision=None, content_class=ContentClass.SYNTHETIC,
            lineage=Lineage(operation="adapter_answer_map", parent_refs=[number], note=note))]

    def _assets_for(self, question: Question,
                    problems: list[SourceProblem]) -> list[Asset]:
        assets: list[Asset] = []
        for required in question.required_assets:
            if not required.sha256:
                problems.append(source_problem(
                    SourceProblemCode.MISSING_ASSET, GapScope.ASSET,
                    f"question {question.native_id} requires an image role="
                    f"{required.role!r} with no hash; the asset stays unresolved",
                    native_ref=question.native_id))
            assets.append(Asset(
                public_id=public_id(EntityKind.ASSET, {
                    "system": "toefl", "media_type": None, "sha256": required.sha256,
                    "storage_mode": "external_only"}),
                media_type=None, byte_size=None, sha256=required.sha256,
                storage_mode="external_only", availability="unknown",
                content_link=None, range_capable=None, revision=None))
        return assets


# --------------------------------------------------------------------------- #
# synthetic cache reparse
# --------------------------------------------------------------------------- #
@dataclass
class CacheReport:
    """Usable cache entries plus the problems for the rejected ones."""

    entries: list[CacheEntry]
    problems: list[SourceProblem]

    @property
    def usable(self) -> list[CacheEntry]:
        return [e for e in self.entries if e.problem is None]


class TOEFLCacheAdapter:
    """Reparse a synthetic cache document and report every rejected entry."""

    provider_id = "toefl_cache_adapter"
    system = ExamSystem.TOEFL

    def __init__(self, fixture_path: str | Path) -> None:
        self._path = Path(fixture_path)

    def report(self) -> CacheReport:
        data, kind, problems = read_source(self._path,
                                           allowed_kinds=(SourceKind.SYNTHETIC,))
        if data is None:
            return CacheReport(entries=[], problems=list(problems))
        problems = list(problems)
        entries = iter_cache_entries(data.get("cache"), source_name=self._path.name)
        for entry in entries:
            if entry.problem is not None:
                problems.append(entry.problem)
        return CacheReport(entries=entries, problems=problems)

    def bundle(self) -> AdapterBundle:
        report = self.report()
        return AdapterBundle(
            system=self.system,
            source={"fixture": self._path.name, "entries": len(report.entries),
                    "usable": len(report.usable)},
            problems=report.problems)


__all__ = [
    "COPIED_READING_INDEX_SOURCE",
    "SYNTHETIC_QUESTION_SET_SOURCE",
    "SYNTHETIC_CACHE_SOURCE",
    "TOEFL_SOURCE_KINDS",
    "TOEFLReadingIndexAdapter",
    "TOEFLQuestionSetAdapter",
    "TOEFLCacheAdapter",
    "CacheReport",
]
