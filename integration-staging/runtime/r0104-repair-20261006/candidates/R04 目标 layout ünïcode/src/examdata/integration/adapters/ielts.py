"""IELTS read adapters (plan A08).

Three read-only adapters over staged IELTS sources:

* :class:`IELTSQuestionsAdapter` reads a *synthetic* IELTS question set (the A03
  book fixture and the A08 book-2 variant fixture) and preserves question
  variants, edition uncertainty, raw source ids, special numbering, the question
  hierarchy, table structure, the missing answer slot (Q41) and an unresolved
  answer conflict.
* :class:`IELTSPagesAdapter` reads the *copied snapshots* of the printed-page map
  and the PDF-import provenance, reporting every page that could not be resolved
  and every document/asset whose hash is absent.
* :class:`IELTSRevisionAdapter` reads the copied revision pointers.
* :class:`IELTSAudioAdapter` reads a *synthetic* audio-alignment fixture and keeps
  a linked full recording, an unverified time window and a claimed-but-unsupported
  ``verified`` alignment distinct - a synthetic claim is capped and reported, never
  promoted.

Nothing here opens a file the caller did not name, fetches a URL, or invents a
missing value. Every irregularity is an explicit problem; a synthetic source can
never reach a ``verified`` quality value (plan 4.6).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from ..contracts.base import Gap
from ..contracts.canonical import UNKNOWN, public_id
from ..contracts.enums import (
    AnswerMatchingMethod,
    ContainerKind,
    ContentClass,
    EntityKind,
    EvidenceLabel,
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
    Lineage,
    ManualDecision,
    Option,
    OptionsPayload,
    Quality,
    Question,
    RequiredAsset,
    SourceRef,
    TableCell,
    TablePayload,
    TextPayload,
    UnknownPayload,
)
from ..contracts.quality import QualityTransitionError
from .bundle import AdapterBundle
from .source_reader import (
    SUPPORTED_SCHEMA_VERSIONS,
    SourceKind,
    SourceProblem,
    SourceProblemCode,
    read_source,
    source_problem,
)

SYNTHETIC_QUESTIONS_SOURCE = "synthetic-ielts-questions"
SYNTHETIC_AUDIO_SOURCE = "synthetic-ielts-audio"
COPIED_PRINTED_PAGES_SOURCE = "copied-ielts-printed-pages"
COPIED_PDF_PROVENANCE_SOURCE = "copied-ielts-pdf-provenance"


# --------------------------------------------------------------------------- #
# question set
# --------------------------------------------------------------------------- #
class IELTSQuestionsAdapter:
    """Map a synthetic IELTS question set onto the frozen contracts."""

    provider_id = "ielts_questions_adapter"
    system = ExamSystem.IELTS

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

        book = data.get("book") or {}
        native = {"book": book.get("native_id"),
                  "revision": data.get("dataset_revision")}
        container_pid = self._container_public_id(native)

        if book.get("edition_uncertain") or ("edition" in book
                                             and book.get("edition") is None):
            problems.append(source_problem(
                SourceProblemCode.UNRESOLVED_EDITION, GapScope.CONTAINER,
                f"book {book.get('native_id')!r} records no edition; the edition stays "
                f"unresolved and is never inferred",
                native_ref=str(book.get("native_id"))))

        questions = [self._build(raw, None, [], container_pid, native, problems)
                     for raw in (data.get("questions") or [])]
        flat = [q for question in questions for q in question.walk()]

        documents = data.get("documents") or []
        for doc in documents:
            if not doc.get("sha256"):
                problems.append(source_problem(
                    SourceProblemCode.MISSING_DOCUMENT_HASH, GapScope.CONTAINER,
                    f"document role {doc.get('role')!r} carries no sha256; the hash stays "
                    f"unknown", native_ref=str(doc.get("role"))))

        container = Container(
            public_id=container_pid, kind=ContainerKind.BOOK, native_identity=native,
            sections=[{
                "questions": [q.public_id for q in flat],
                "variant": book.get("variant"),
                "edition": (book.get("edition") if not book.get("edition_uncertain")
                            else UNKNOWN),
                "edition_uncertain": bool(book.get("edition_uncertain")),
            }],
            resources=[{"role": d.get("role"), "sha256": d.get("sha256")}
                       for d in documents],
            question_refs=[q.public_id for q in flat],
            revision=data.get("dataset_revision"), coverage=None,
            content_class=ContentClass.SYNTHETIC,
            lineage=Lineage(operation="adapter_container_map",
                            parent_refs=[str(book.get("native_id"))],
                            note="container mapped from a synthetic IELTS question set"),
        )

        assets: list[Asset] = []
        for question in flat:
            for required in question.required_assets:
                assets.append(Asset(
                    public_id=public_id(EntityKind.ASSET, {
                        "system": "ielts", "media_type": None, "sha256": required.sha256,
                        "storage_mode": "external_only"}),
                    media_type=None, byte_size=None, sha256=required.sha256,
                    storage_mode="external_only", availability="unknown",
                    content_link=None, range_capable=None, revision=None))
                problems.append(source_problem(
                    SourceProblemCode.MISSING_ASSET, GapScope.ASSET,
                    f"required asset role={required.role!r} is referenced by hash but its "
                    f"bytes are not present in the synthetic fixture",
                    native_ref=question.native_id))

        return AdapterBundle(
            system=self.system,
            source={"fixture": self._path.name, "kind": kind.value,
                    "board": data.get("board"), "schema_version": data.get("schema_version"),
                    "dataset_revision": data.get("dataset_revision"),
                    "variant": book.get("variant")},
            courses=[self._course(book, data)], containers=[container],
            questions=questions, answers=[a for q in flat for a in q.answers],
            assets=assets, problems=problems)

    # -- construction -------------------------------------------------------- #
    @staticmethod
    def _schema_problems(data: Mapping[str, Any]) -> list[SourceProblem]:
        version = data.get("schema_version")
        if version is None:
            return []  # a legacy synthetic fixture may predate the field
        if str(version) not in SUPPORTED_SCHEMA_VERSIONS:
            return [source_problem(
                SourceProblemCode.UNSUPPORTED_SCHEMA_VERSION, GapScope.SYSTEM,
                f"question set declares schema_version {version!r}; supported: "
                f"{sorted(SUPPORTED_SCHEMA_VERSIONS)}")]
        return []

    def _container_public_id(self, native: Mapping[str, Any]) -> str:
        return public_id(EntityKind.CONTAINER, {
            "system": "ielts", "kind": "book", "native_identity": dict(native)})

    def _course(self, book: Mapping[str, Any], data: Mapping[str, Any]) -> Course:
        native_code = str(book.get("native_id"))
        fields = {"system": "ielts", "qualification": UNKNOWN, "native_code": native_code,
                  "specification_version": None}
        return Course(
            public_id=public_id(EntityKind.COURSE, fields), system=ExamSystem.IELTS,
            qualification=None, native_code=native_code,
            names=[book.get("title") or native_code],
            aliases=list(book.get("alias_ids") or []),
            specification_version=None, applicable_years=[],
            source_refs=[SourceRef(source_id=SYNTHETIC_QUESTIONS_SOURCE,
                                   provider_id=self.provider_id,
                                   locator={"fixture": self._path.name},
                                   content_class=ContentClass.SYNTHETIC)])

    def _build(self, raw: Mapping[str, Any], parent: str | None, parent_path: list[str],
               container_pid: str, container_native: Mapping[str, Any],
               problems: list[SourceProblem]) -> Question:
        number = str(raw.get("native_id") or raw.get("question"))
        path = parent_path + [number]
        raw_parent = raw.get("parent_native_id")
        self_parent = (parent is None and raw_parent is not None
                       and str(raw_parent) == number)
        if self_parent:
            problems.append(source_problem(
                SourceProblemCode.UNRESOLVED_IDENTITY, GapScope.QUESTION,
                f"question {number!r} declares itself as its own parent; the raw value is "
                f"preserved in the lineage note and the question is treated as a root",
                native_ref=number))

        qtype, payload = self._payload(raw)
        answers = self._answers_from(raw, number)
        quality = self._question_quality(raw, number, answers, problems)

        note_bits = []
        if raw.get("numbering") is not None:
            note_bits.append(f"numbering={raw['numbering']}")
        if raw.get("raw_source_id") is not None:
            note_bits.append(f"raw_source_id={raw['raw_source_id']}")
        if raw.get("variant") is not None:
            note_bits.append(f"variant={raw['variant']}")
        if self_parent:
            note_bits.append(f"raw_parent_native_id={raw_parent} (self, normalised to root)")
        note = "question mapped from a synthetic IELTS question set"
        if note_bits:
            note += "; " + ", ".join(note_bits)

        return Question(
            public_id=public_id(EntityKind.QUESTION, {
                "system": "ielts", "container_native_identity": dict(container_native),
                "native_id": number, "number_path": path, "parent_native_id": parent}),
            native_id=number, container_ref=container_pid, number_path=path,
            parent_ref=parent, group_ref=None, question_type=qtype,
            stem=raw.get("prompt") or raw.get("text"), payload=payload,
            marks=raw.get("marks"),
            required_assets=[RequiredAsset(role=i.get("role", ""), sha256=i.get("sha256"),
                                           required=True)
                             for i in (raw.get("required_images") or [])],
            answers=answers, quality=quality, content_class=ContentClass.SYNTHETIC,
            lineage=Lineage(operation="adapter_question_map",
                            parent_refs=[str(raw.get("raw_source_id") or number)],
                            note=note),
            children=[self._build(child, number, path, container_pid, container_native,
                                  problems)
                      for child in (raw.get("children") or raw.get("parts") or [])],
        )

    @staticmethod
    def _payload(raw: Mapping[str, Any]):
        kind = raw.get("kind")
        if kind == "table_choice":
            table = raw.get("table") or {}
            cell = table.get("answer_cell")
            cells = ([TableCell(row=int(cell["row"]), column=int(cell["column"]),
                                value=cell.get("value"))] if cell else [])
            return QuestionType.TABLE_CHOICE, TablePayload(
                columns=list(table.get("columns") or []),
                rows=[list(r) for r in (table.get("rows") or [])], answer_cells=cells)
        if kind == "grouped_alternatives":
            keys = [raw.get("answer")] + list(raw.get("alternative_answers") or [])
            options = [Option(key=str(k)) for k in keys if k is not None]
            return QuestionType.SINGLE_CHOICE, OptionsPayload(options=options)
        if kind == "missing_answer_slot":
            return QuestionType.UNKNOWN, UnknownPayload(
                native_shape="missing_answer_slot",
                raw={"answer_slot": raw.get("answer_slot")})
        if kind in ("multiple_choice", "multiple_selection"):
            options = [Option(key=str(k)) for k in (raw.get("options") or [])]
            return QuestionType.MULTIPLE_CHOICE, OptionsPayload(options=options)
        return QuestionType.SHORT_ANSWER, TextPayload(
            stem=raw.get("prompt") or raw.get("text"))

    def _answers_from(self, raw: Mapping[str, Any], number: str) -> list[Answer]:
        if raw.get("missing_answer") or (raw.get("answer") is None
                                         and not raw.get("answer_conflicts")):
            return []
        conflicts = [Conflict.from_dict(c) for c in (raw.get("answer_conflicts") or [])]
        decision = (ManualDecision.from_dict(raw["manual_decision"])
                    if raw.get("manual_decision") else None)
        alternatives = list(raw.get("alternative_answers") or [])
        locator: dict[str, Any] = {"fixture": self._path.name}
        if raw.get("raw_source_id") is not None:
            locator["raw_source_id"] = raw["raw_source_id"]
        return [Answer(
            public_id=public_id(EntityKind.ANSWER, {
                "system": "ielts", "question_native_id": number,
                "source": SYNTHETIC_QUESTIONS_SOURCE, "native_answer_key": number}),
            question_ref=number, original_value=raw.get("answer"), normalized_value=None,
            alternatives=alternatives, ordering_rule=None,
            matching_method=(AnswerMatchingMethod.GROUPED if alternatives
                             else AnswerMatchingMethod.UNRESOLVED),
            verification="unverified",
            source=SourceRef(source_id=SYNTHETIC_QUESTIONS_SOURCE,
                             provider_id=self.provider_id, locator=locator,
                             content_class=ContentClass.SYNTHETIC),
            conflicts=conflicts, manual_decision=decision,
            content_class=ContentClass.SYNTHETIC,
            lineage=Lineage(operation="adapter_answer_map", parent_refs=[number],
                            note="answer stated on the synthetic question"))]

    def _question_quality(self, raw: Mapping[str, Any], number: str,
                          answers: list[Answer],
                          problems: list[SourceProblem]) -> Quality:
        quality = Quality()
        if raw.get("missing_answer"):
            detail = (f"question {number} has no answer slot; the slot is preserved as "
                      f"missing and is never fabricated")
            quality.apply("answer_presence", "missing", EvidenceLabel.SYNTHETIC_FIXTURE,
                          context={"missing_slot_marked": True},
                          gap=Gap(code=GapCode.MISSING_ANSWER_SLOT.value,
                                  scope=GapScope.QUESTION.value, detail=detail))
            problems.append(source_problem(
                SourceProblemCode.MISSING_ANSWER_SLOT, GapScope.QUESTION, detail,
                native_ref=number))
        elif answers:
            quality.apply("answer_presence", "present", EvidenceLabel.SYNTHETIC_FIXTURE,
                          context={"answer_value_present": True})
        for answer in answers:
            # a synthetic answer is never source-verified: it can only be recorded as
            # unverified, and a multi-candidate answer as conflicting
            quality.apply("answer_verification", "unverified",
                          EvidenceLabel.SYNTHETIC_FIXTURE)
            if len(answer.conflicts) > 1 and answer.manual_decision is None:
                detail = (f"question {number}: {len(answer.conflicts)} candidate answers "
                          f"disagree and no manual decision is recorded; both are preserved")
                quality.apply("answer_verification", "conflicting",
                              EvidenceLabel.SYNTHETIC_FIXTURE,
                              context={"conflict_candidates_present": True},
                              gap=Gap(code=GapCode.ANSWER_CONFLICT.value,
                                      scope=GapScope.ANSWER.value, detail=detail))
                problems.append(source_problem(
                    SourceProblemCode.ANSWER_CONFLICT, GapScope.ANSWER, detail,
                    native_ref=number))
        return quality


# --------------------------------------------------------------------------- #
# copied printed-page map + PDF-import provenance
# --------------------------------------------------------------------------- #
@dataclass
class PageResolution:
    """One printed-page resolution result from the copied snapshot."""

    book: str | None
    printed_page: str
    chosen: int | None
    resolved: bool


class IELTSPagesAdapter:
    """Read the copied printed-page map and the copied PDF-import provenance."""

    provider_id = "ielts_pages_adapter"
    system = ExamSystem.IELTS

    def __init__(self, printed_pages_path: str | Path,
                 provenance_path: str | Path | None = None) -> None:
        self._printed = Path(printed_pages_path)
        self._provenance = Path(provenance_path) if provenance_path is not None else None

    def page_resolutions(self) -> tuple[list[PageResolution], list[SourceProblem]]:
        data, kind, problems = read_source(self._printed,
                                           allowed_kinds=(SourceKind.COPIED_SNAPSHOT,))
        if data is None:
            return [], list(problems)
        problems = list(problems)
        out: list[PageResolution] = []
        for key, entry in (data.get("results") or {}).items():
            book, _, printed = str(key).partition(":")
            chosen = entry.get("chosen") if isinstance(entry, Mapping) else None
            if chosen is None:
                problems.append(source_problem(
                    SourceProblemCode.UNRESOLVED_PAGE, GapScope.REGION,
                    f"printed page {key!r} has no chosen page in the copied map; the page "
                    f"stays unresolved and is never guessed", native_ref=str(key)))
                out.append(PageResolution(book or None, printed or str(key), None, False))
            else:
                out.append(PageResolution(book or None, printed or str(key), chosen, True))
        return out, problems

    def provenance_documents(self) -> tuple[list[Asset], list[SourceProblem]]:
        if self._provenance is None:
            return [], []
        data, kind, problems = read_source(self._provenance,
                                           allowed_kinds=(SourceKind.COPIED_SNAPSHOT,))
        if data is None:
            return [], list(problems)
        problems = list(problems)
        assets: list[Asset] = []
        for entry in data.get("entries") or []:
            pdf = entry.get("pdf") or {}
            sha = pdf.get("sha256")
            if not sha:
                problems.append(source_problem(
                    SourceProblemCode.MISSING_DOCUMENT_HASH, GapScope.ASSET,
                    f"PDF import {entry.get('key')!r} records no sha256; the document hash "
                    f"stays unknown", native_ref=str(entry.get("key"))))
            assets.append(Asset(
                public_id=public_id(EntityKind.ASSET, {
                    "system": "ielts", "media_type": "application/pdf", "sha256": sha,
                    "storage_mode": "embedded" if entry.get("pdf_stored")
                                    else "external_only"}),
                media_type="application/pdf", byte_size=None, sha256=sha,
                storage_mode="embedded" if entry.get("pdf_stored") else "external_only",
                availability="unknown", content_link=pdf.get("path"),
                range_capable=None, revision=None))
            for imported in entry.get("assets") or []:
                assets.append(Asset(
                    public_id=public_id(EntityKind.ASSET, {
                        "system": "ielts", "media_type": imported.get("media_type"),
                        "sha256": imported.get("sha256"),
                        "storage_mode": "embedded" if imported.get("stored")
                                        else "external_only"}),
                    media_type=imported.get("media_type"), byte_size=None,
                    sha256=imported.get("sha256"),
                    storage_mode="embedded" if imported.get("stored") else "external_only",
                    availability="unknown", content_link=imported.get("name"),
                    range_capable=None, revision=None))
            problems.extend(self.entry_problems(entry))
        return assets, problems

    @staticmethod
    def entry_problems(entry: Mapping[str, Any]) -> list[SourceProblem]:
        """Problems for one PDF-import entry (kept separate so a test can feed a copy)."""
        problems: list[SourceProblem] = []
        key = str(entry.get("key"))
        for page in entry.get("missing_pages") or []:
            problems.append(source_problem(
                SourceProblemCode.UNRESOLVED_PAGE, GapScope.REGION,
                f"PDF import {key!r} is missing page {page}; the page stays unresolved",
                native_ref=key))
        for name in entry.get("missing_assets") or []:
            problems.append(source_problem(
                SourceProblemCode.MISSING_ASSET, GapScope.ASSET,
                f"PDF import {key!r} is missing asset {name!r}", native_ref=key))
        return problems

    def bundle(self) -> AdapterBundle:
        resolutions, page_problems = self.page_resolutions()
        assets, provenance_problems = self.provenance_documents()
        problems = page_problems + provenance_problems
        unresolved = [r for r in resolutions if not r.resolved]
        return AdapterBundle(
            system=self.system,
            source={"printed_pages": self._printed.name,
                    "provenance": self._provenance.name if self._provenance else None,
                    "printed_pages_total": len(resolutions),
                    "printed_pages_unresolved": len(unresolved)},
            assets=assets, problems=problems)


# --------------------------------------------------------------------------- #
# copied revision pointers
# --------------------------------------------------------------------------- #
class IELTSRevisionAdapter:
    """Read the copied IELTS revision pointers and report a mismatch."""

    provider_id = "ielts_revision_adapter"
    system = ExamSystem.IELTS

    def __init__(self, indexes_path: str | Path,
                 manifests_path: str | Path | None = None) -> None:
        self._indexes = Path(indexes_path)
        self._manifests = Path(manifests_path) if manifests_path is not None else None

    def bundle(self) -> AdapterBundle:
        problems: list[SourceProblem] = []
        revisions: dict[str, Any] = {}
        for label, path in (("indexes", self._indexes), ("manifests", self._manifests)):
            if path is None:
                continue
            data, kind, probs = read_source(path,
                                            allowed_kinds=(SourceKind.COPIED_SNAPSHOT,))
            problems.extend(probs)
            if data is None:
                continue
            revisions[label] = data.get("dataset_revision")
            if not data.get("dataset_revision"):
                problems.append(source_problem(
                    SourceProblemCode.MISSING_DOCUMENT_HASH, GapScope.SYSTEM,
                    f"{label} pointer {path.name!r} records no dataset_revision"))
        values = [v for v in revisions.values() if v]
        if len(set(values)) > 1:
            problems.append(source_problem(
                SourceProblemCode.UNRESOLVED_IDENTITY, GapScope.SYSTEM,
                f"the copied revision pointers disagree ({revisions}); a stale pointer is "
                f"never treated as current"))
        return AdapterBundle(
            system=self.system,
            source={"indexes": self._indexes.name,
                    "manifests": self._manifests.name if self._manifests else None,
                    "revisions": revisions},
            problems=problems)


# --------------------------------------------------------------------------- #
# synthetic audio alignment
# --------------------------------------------------------------------------- #
@dataclass
class AudioTrack:
    """One audio track: its asset, the alignment quality actually granted, and segments."""

    native_id: str
    asset: Asset
    quality: Quality
    alignment_declared: str | None
    alignment_effective: str
    segments: list[dict[str, Any]] = field(default_factory=list)
    problems: list[SourceProblem] = field(default_factory=list)


class IELTSAudioAdapter:
    """Read a synthetic IELTS audio-alignment fixture without touching any audio."""

    provider_id = "ielts_audio_adapter"
    system = ExamSystem.IELTS

    def __init__(self, fixture_path: str | Path) -> None:
        self._path = Path(fixture_path)

    def tracks(self) -> tuple[list[AudioTrack], list[SourceProblem]]:
        data, kind, problems = read_source(self._path,
                                           allowed_kinds=(SourceKind.SYNTHETIC,))
        if data is None:
            return [], list(problems)
        problems = list(problems)
        tracks: list[AudioTrack] = []
        for raw in data.get("audio") or []:
            track, track_problems = self._track(raw)
            tracks.append(track)
            problems.extend(track_problems)
        return tracks, problems

    def _track(self, raw: Mapping[str, Any]) -> tuple[AudioTrack, list[SourceProblem]]:
        native_id = str(raw.get("native_id"))
        problems: list[SourceProblem] = []
        asset = Asset(
            public_id=public_id(EntityKind.ASSET, {
                "system": "ielts", "media_type": raw.get("media_type"),
                "sha256": raw.get("sha256"),
                "storage_mode": raw.get("storage_mode") or "external_only"}),
            media_type=raw.get("media_type"), byte_size=raw.get("byte_size"),
            sha256=raw.get("sha256"),
            storage_mode=raw.get("storage_mode") or "external_only",
            availability="unknown", content_link=None, range_capable=None,
            revision=None)

        quality = Quality()
        alignment = raw.get("alignment") or {}
        declared = alignment.get("status")
        quality.apply("audio_integrity", "unverified", EvidenceLabel.SYNTHETIC_FIXTURE)

        if declared == "verified":
            try:
                quality.apply("audio_alignment", "verified",
                              EvidenceLabel.SYNTHETIC_FIXTURE,
                              context={"alignment_evidence_present":
                                       bool(alignment.get("evidence"))})
            except QualityTransitionError as exc:
                problems.append(source_problem(
                    SourceProblemCode.UNVERIFIED_CONTENT, GapScope.ASSET,
                    f"track {native_id!r} claims a verified alignment, but synthetic "
                    f"evidence cannot establish it ({exc}); the alignment is capped at "
                    f"'unverified' and the claim is reported", native_ref=native_id))
                quality.apply("audio_alignment", "unverified",
                              EvidenceLabel.SYNTHETIC_FIXTURE)
        elif declared == "not_applicable":
            quality.apply("audio_alignment", "not_applicable",
                          EvidenceLabel.SYNTHETIC_FIXTURE,
                          context={"no_required_assets": True})
        elif declared == "unknown" or declared is None:
            pass  # stays unknown
        else:  # "unverified" or any other declared state
            quality.apply("audio_alignment", "unverified", EvidenceLabel.SYNTHETIC_FIXTURE)

        segments = []
        for segment in raw.get("segments") or []:
            start, end = segment.get("start"), segment.get("end")
            if start is None or end is None:
                problems.append(source_problem(
                    SourceProblemCode.MISSING_TIME_WINDOW, GapScope.ASSET,
                    f"track {native_id!r} associates question "
                    f"{segment.get('question')!r} but records no time window; no offset is "
                    f"invented", native_ref=native_id))
            segments.append({"question": segment.get("question"),
                             "start": start, "end": end})

        track = AudioTrack(
            native_id=native_id, asset=asset, quality=quality,
            alignment_declared=declared,
            alignment_effective=quality.audio_alignment.value, segments=segments,
            problems=problems)
        return track, problems

    def bundle(self) -> AdapterBundle:
        tracks, problems = self.tracks()
        return AdapterBundle(
            system=self.system,
            source={"fixture": self._path.name, "tracks": len(tracks)},
            assets=[t.asset for t in tracks], problems=problems)


__all__ = [
    "SYNTHETIC_QUESTIONS_SOURCE",
    "SYNTHETIC_AUDIO_SOURCE",
    "COPIED_PRINTED_PAGES_SOURCE",
    "COPIED_PDF_PROVENANCE_SOURCE",
    "IELTSQuestionsAdapter",
    "IELTSPagesAdapter",
    "IELTSRevisionAdapter",
    "IELTSAudioAdapter",
    "PageResolution",
    "AudioTrack",
]
