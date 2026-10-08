#!/usr/bin/env python3
"""Map the A03 synthetic fixtures into the A04 contracts and prove the mapping.

For each synthetic fixture (IELTS questions, CIE paper index, Edexcel subject
index) this tool:

1. builds a deterministic ``IdentityRegistry`` for the entities the fixture
   describes (container, questions, answers, assets, course, timetable events);
2. constructs the contract models, keeping every native identity, alias, missing
   answer slot, question hierarchy, table structure, answer conflict, manual
   decision, required asset, unknown date and lineage record intact;
3. asserts ``from_dict(to_dict(x)) == x`` for every constructed model;
4. records the ``validate()`` problems verbatim (a gap stays visible, it is never
   silently cleared);
5. writes one example JSON per model under ``integration-staging/contracts/examples/``
   plus an ``INDEX.json`` mapping every example to its schema.

Nothing here reads the original project, the network or the live database. The
fixtures are the private A03 synthetic snapshots; the mapping decisions are the
ones recorded in ``docs/integration/execution/A04_IDENTITY_DECISION.md``.

Phase A tool (integration-staging/tools/).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.dont_write_bytecode = True

HERE = Path(__file__).resolve()
STAGING = HERE.parents[1]
WS = STAGING.parent
SRC = STAGING / "src"
sys.path.insert(0, str(SRC))

from examdata_integration.contracts import (  # noqa: E402
    Answer,
    AnswerMatchingMethod,
    Asset,
    Conflict,
    Container,
    ContentClass,
    ContainerKind,
    Course,
    Coverage,
    EntityKind,
    ExaminationSystemModel,
    ExamSystem,
    Gap,
    GapCode,
    GapScope,
    IdentityRegistry,
    JobStatus,
    Lineage,
    ManualDecision,
    Material,
    Quality,
    QualityAnswerPresence,
    QualityAnswerVerification,
    QualityAssets,
    Question,
    QuestionType,
    Region,
    RequiredAsset,
    SourceRef,
    Syllabus,
    Tag,
    TimetableEvent,
    TimetableWindow,
    UNKNOWN,
    completeness,
)

FIXTURES = STAGING / "fixtures" / "synthetic"
EXAMPLES = STAGING / "contracts" / "examples"
EVIDENCE = WS / "docs" / "integration" / "execution" / "evidence" / "A04"

checks: list[tuple[str, bool, str]] = []
examples: dict[str, dict] = {}          # relative file name -> instance
example_schema: dict[str, str] = {}     # relative file name -> schema id


def check(name: str, ok: bool, detail: str = "") -> None:
    checks.append((name, bool(ok), detail))


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def native_number_path(native_id: str, parent_native_id: str | None) -> list[str]:
    """Hierarchy preserved: the declared parent prefix then the id itself."""
    parts: list[str] = []
    if parent_native_id and parent_native_id != native_id:
        parts.append(parent_native_id)
    parts.append(native_id)
    return parts


def add_example(label: str, instance) -> None:
    fname = f"{label}.json"
    examples[fname] = instance.to_dict() if hasattr(instance, "to_dict") else instance
    example_schema[fname] = instance.SCHEMA


def synthetic_source(provider: str, detail: str) -> SourceRef:
    return SourceRef(source_id=f"synthetic-{provider}", provider_id=provider,
                     locator={"fixture": f"synthetic/{provider}", "detail": detail},
                     content_class=ContentClass.SYNTHETIC,
                     retrieved_at="2026-10-05T19:20:00+08:00")


def synthetic_lineage(operation: str, refs: list[str], note: str | None = None) -> Lineage:
    return Lineage(operation=operation, source_refs=refs, parent_refs=[], note=note)


# --------------------------------------------------------------------------- #
# IELTS
# --------------------------------------------------------------------------- #
def build_ielts(fx: dict) -> dict:
    reg = IdentityRegistry()
    provider = "ielts"
    book = fx["book"]
    book_identity = {"native_id": book["native_id"]}

    container_pid = reg.register(
        EntityKind.CONTAINER,
        {"system": provider, "kind": "book", "native_identity": book_identity},
        native_locator={"provider": provider, "kind": "book", "native_id": book["native_id"]},
        aliases=book["alias_ids"],
        content_revision=fx["dataset_revision"],
    ).public_id

    container = Container(
        public_id=container_pid,
        kind=ContainerKind.BOOK,
        native_identity=dict(book_identity),
        sections=[],
        resources=[],
        question_refs=[],
        revision=fx["dataset_revision"],
        coverage="unknown",
        content_class=ContentClass.SYNTHETIC,
        lineage=synthetic_lineage("map_native_fixture", [f"synthetic/{provider}"],
                                  note="native title kept in the fixture, not promoted to a name"),
    )

    assets = []
    for doc in fx.get("documents", []):
        pid = reg.register(
            EntityKind.ASSET,
            {"system": provider, "media_type": None, "sha256": doc["sha256"], "storage_mode": None},
            native_locator={"provider": provider, "role": doc["role"], "sha256": doc["sha256"]},
        ).public_id
        assets.append(Asset(public_id=pid, media_type=None, byte_size=None,
                            sha256=doc["sha256"], storage_mode=None, availability="unknown",
                            content_link=None, range_capable=None, revision=None))

    # pass 1: register every question identity so parent_ref can be resolved.
    q_pids: dict[str, str] = {}
    for q in fx["questions"]:
        pid = reg.register(
            EntityKind.QUESTION,
            {
                "system": provider,
                "container_native_identity": book_identity,
                "native_id": q["native_id"],
                "number_path": native_number_path(q["native_id"], q.get("parent_native_id")),
                "parent_native_id": q.get("parent_native_id"),
            },
            native_locator={"provider": provider, "container_native_id": book["native_id"],
                            "native_id": q["native_id"]},
        ).public_id
        q_pids[q["native_id"]] = pid

    questions: list[Question] = []
    for q in fx["questions"]:
        native_id = q["native_id"]
        parent_native = q.get("parent_native_id")
        number_path = native_number_path(native_id, parent_native)
        kind = q["kind"]
        prompt = q.get("prompt")
        answer_value = q.get("answer")
        alternatives = list(q.get("alternative_answers") or [])
        missing = bool(q.get("missing_answer"))
        conflicts = [
            Conflict(value=c["value"], source=c["source"], evidence=None,
                     decision=c.get("decision"))
            for c in (q.get("answer_conflicts") or [])
        ]
        manual_raw = q.get("manual_decision")
        manual = (ManualDecision(decided_by=manual_raw.get("decided_by"),
                                 decided_at=manual_raw.get("decided_at"),
                                 selected_value=manual_raw.get("selected_value"),
                                 rationale=manual_raw.get("rationale"))
                  if manual_raw else None)

        quality = Quality()
        quality.apply("content", "partial", "synthetic_fixture")
        quality.apply("answer_verification", "unverified", "synthetic_fixture")

        required_assets = [
            RequiredAsset(role=img["role"], sha256=img.get("sha256"), asset_ref=None,
                          required=True)
            for img in (q.get("required_images") or [])
        ]

        if required_assets:
            quality.apply("assets", "external_only", "synthetic_fixture")

        lineage = synthetic_lineage(
            "map_native_fixture",
            [f"synthetic/{provider}", f"native-kind:{kind}"],
            note=q.get("missing_reason"),
        )

        payload = None
        qtype = QuestionType.UNKNOWN
        children: list[Question] = []
        answers: list[Answer] = []

        if kind == "fill_blank":
            qtype = QuestionType.FILL_BLANK
            payload = _text_payload(prompt)
            if answer_value is not None:
                quality.apply("answer_presence", "present", "synthetic_fixture",
                              context={"answer_value_present": True})
                answers.append(_answer(reg, provider, native_id, "primary", answer_value,
                                       [], "exact", "unverified", conflicts, manual))
        elif kind == "grouped_alternatives":
            qtype = QuestionType.SINGLE_CHOICE
            payload = _options_payload([answer_value, *alternatives])
            quality.apply("answer_presence", "present", "synthetic_fixture",
                          context={"answer_value_present": True})
            answers.append(_answer(reg, provider, native_id, "primary", answer_value,
                                   alternatives, "alternative", "unverified", conflicts, manual))
        elif kind == "parent_answer":
            qtype = QuestionType.SHORT_ANSWER
            payload = _text_payload(prompt)
            if answer_value is not None:
                quality.apply("answer_presence", "present", "synthetic_fixture",
                              context={"answer_value_present": True})
                answers.append(_answer(reg, provider, native_id, "parent", answer_value,
                                       [], "ancestor", "unverified", conflicts, manual,
                                       ordering_rule="parent_answer_covers_sub_parts"))
            for child in q.get("children", []):
                child_native = child["native_id"]
                child_pid = reg.register(
                    EntityKind.QUESTION,
                    {
                        "system": provider,
                        "container_native_identity": book_identity,
                        "native_id": child_native,
                        "number_path": native_number_path(child_native, child.get("parent_native_id")),
                        "parent_native_id": child.get("parent_native_id"),
                    },
                    native_locator={"provider": provider, "container_native_id": book["native_id"],
                                    "native_id": child_native},
                ).public_id
                q_pids[child_native] = child_pid
                child_quality = Quality()
                child_quality.apply("content", "partial", "synthetic_fixture")
                child_quality.apply("answer_verification", "unknown", "synthetic_fixture")
                children.append(Question(
                    public_id=child_pid, native_id=child_native, container_ref=container_pid,
                    number_path=native_number_path(child_native, child.get("parent_native_id")),
                    parent_ref=q_pids[native_id], group_ref=q_pids[native_id],
                    question_type=QuestionType.UNKNOWN,
                    stem=child.get("prompt"), payload=None, marks=None, required_assets=[],
                    answers=[], quality=child_quality, content_class=ContentClass.SYNTHETIC,
                    lineage=synthetic_lineage(
                        "map_native_fixture",
                        [f"synthetic/{provider}", "native-kind:parent_answer_child"],
                        note="sub-part type is not declared by the source; kept as unknown"),
                    children=[],
                ))
        elif kind == "table_choice":
            qtype = QuestionType.TABLE_CHOICE
            table = q["table"]
            payload = _table_payload(table)
            if answer_value is not None:
                quality.apply("answer_presence", "present", "synthetic_fixture",
                              context={"answer_value_present": True})
                answers.append(_answer(reg, provider, native_id, "primary", answer_value,
                                       alternatives, "exact", "unverified", conflicts, manual))
        elif kind == "missing_answer_slot":
            qtype = QuestionType.UNKNOWN
            payload = None
            quality.apply("answer_presence", "missing", "synthetic_fixture",
                          context={"missing_slot_marked": True},
                          gap=Gap(code=GapCode.MISSING_ANSWER_SLOT.value,
                                  scope=GapScope.QUESTION.value,
                                  detail=q.get("missing_reason")))
        elif kind == "answer_conflict":
            qtype = QuestionType.FILL_BLANK
            payload = _text_payload(prompt)
            quality.apply("answer_presence", "present", "synthetic_fixture",
                          context={"answer_value_present": True})
            quality.apply("answer_verification", "conflicting", "synthetic_fixture",
                          context={"conflict_candidates_present": bool(conflicts)})
            answers.append(_answer(reg, provider, native_id, "primary", answer_value,
                                   alternatives, "alternative", "conflicting", conflicts, manual))
        else:  # pragma: no cover - the fixtures only contain the kinds above
            raise SystemExit(f"unmapped native kind {kind!r} in the IELTS fixture")

        questions.append(Question(
            public_id=q_pids[native_id],
            native_id=native_id,
            container_ref=container_pid,
            number_path=number_path,
            parent_ref=None,
            group_ref=None,
            question_type=qtype,
            stem=prompt,
            payload=payload,
            marks=None,
            required_assets=required_assets,
            answers=answers,
            quality=quality,
            content_class=ContentClass.SYNTHETIC,
            lineage=lineage,
            children=children,
        ))

    container.question_refs = [q.public_id for q in questions]
    coverage = completeness.evaluate_container(
        container, questions, expected_questions=len(fx["questions"]))
    cov_model = coverage.to_coverage(public_id="cov_synthetic_ielts", computed_at=None,
                                     evidence=["synthetic_fixture"])

    return {
        "registry": reg,
        "containers": [container],
        "questions": questions,
        "assets": assets,
        "coverage": [cov_model],
    }


def _text_payload(stem):
    from examdata_integration.contracts.models import TextPayload
    return TextPayload(stem=stem, word_limit=None)


def _options_payload(keys):
    from examdata_integration.contracts.models import Option, OptionsPayload
    ordered = sorted({k for k in keys if k is not None})
    return OptionsPayload(options=[Option(key=k, label=None) for k in ordered])


def _table_payload(table):
    from examdata_integration.contracts.models import TableCell, TablePayload
    cells = []
    if table.get("answer_cell"):
        cells.append(TableCell(row=table["answer_cell"]["row"],
                               column=table["answer_cell"]["column"], value=None))
    for cell in table.get("answer_cells", []):
        cells.append(TableCell(row=cell["row"], column=cell["column"], value=None))
    return TablePayload(columns=list(table["columns"]),
                        rows=[list(r) for r in table["rows"]],
                        answer_cells=cells)


def _answer(reg, provider, question_native_id, native_answer_key, value, alternatives,
            matching_method, verification, conflicts, manual, ordering_rule=None):
    pid = reg.register(
        EntityKind.ANSWER,
        {"system": provider, "question_native_id": question_native_id,
         "source": f"synthetic-{provider}", "native_answer_key": native_answer_key},
        native_locator={"provider": provider, "question_native_id": question_native_id,
                        "native_answer_key": native_answer_key},
    ).public_id
    return Answer(
        public_id=pid,
        question_ref=None,
        original_value=value,
        normalized_value=None,
        alternatives=list(alternatives),
        ordering_rule=ordering_rule,
        matching_method=AnswerMatchingMethod.coerce(matching_method),
        verification=verification,
        source=synthetic_source(provider, f"answer:{native_answer_key}"),
        conflicts=list(conflicts),
        manual_decision=manual,
        content_class=ContentClass.SYNTHETIC,
        lineage=synthetic_lineage("map_native_fixture",
                                  [f"synthetic/{provider}", f"native-answer-key:{native_answer_key}"]),
    )


# --------------------------------------------------------------------------- #
# CIE
# --------------------------------------------------------------------------- #
def build_cie(fx: dict) -> dict:
    reg = IdentityRegistry()
    provider = "cie"
    ident = fx["identity"]
    subject = ident["subject"]

    course_pid = reg.register(
        EntityKind.COURSE,
        {"system": provider, "qualification": None, "native_code": subject,
         "specification_version": None},
        native_locator={"provider": provider, "subject": subject},
        aliases=[ident["subject_alias"]],
    ).public_id
    course = Course(
        public_id=course_pid, system=ExamSystem.CIE, qualification=None, native_code=subject,
        names=[ident["subject_alias"]], aliases=[],
        specification_version=None, applicable_years=[int(ident["year"])],
        source_refs=[synthetic_source(provider, "subject")],
    )

    paper_identity = {"subject": subject, "year": ident["year"], "season": ident["season"],
                      "paper": ident["paper"]}
    container_pid = reg.register(
        EntityKind.CONTAINER,
        {"system": provider, "kind": "paper", "native_identity": paper_identity},
        native_locator={"provider": provider, "kind": "paper", **paper_identity},
    ).public_id
    container = Container(
        public_id=container_pid, kind=ContainerKind.PAPER, native_identity=dict(paper_identity),
        sections=[], resources=[], question_refs=[], revision=None, coverage="unknown",
        content_class=ContentClass.SYNTHETIC,
        lineage=synthetic_lineage("map_native_fixture", [f"synthetic/{provider}"],
                                  note="paper identity kept verbatim; the source date is unknown"),
    )

    assets = []
    for doc in fx.get("documents", []):
        pid = reg.register(
            EntityKind.ASSET,
            {"system": provider, "media_type": None, "sha256": doc["sha256"], "storage_mode": None},
            native_locator={"provider": provider, "role": doc["role"], "sha256": doc["sha256"]},
        ).public_id
        assets.append(Asset(public_id=pid, media_type=None, byte_size=None, sha256=doc["sha256"],
                            storage_mode=None, availability="unknown", content_link=None,
                            range_capable=None, revision=None))

    events = []
    event_pid = reg.register(
        EntityKind.TIMETABLE_EVENT,
        {"system": provider, "qualification": None, "zone": None, "course_native_code": subject,
         "component": ident["paper"], "date": None, "session": ident["season"]},
        native_locator={"provider": provider, "subject": subject, "paper": ident["paper"]},
    ).public_id
    events.append(TimetableEvent(
        public_id=event_pid, system=ExamSystem.CIE, qualification=None, zone=None,
        course_ref=course_pid, component=ident["paper"], date=None, session=ident["season"],
        timezone=None, duration_minutes=None,
        source=synthetic_source(provider, f"date_unknown_reason:{ident['date_unknown_reason']}"),
        revision=None,
    ))

    q_pids: dict[str, str] = {}
    for q in fx["questions"]:
        pid = reg.register(
            EntityKind.QUESTION,
            {
                "system": provider,
                "container_native_identity": paper_identity,
                "native_id": q["question"],
                "number_path": native_number_path(q["question"], q.get("parent")),
                "parent_native_id": q.get("parent"),
            },
            native_locator={"provider": provider, "paper": ident["paper"],
                            "question": q["question"]},
        ).public_id
        q_pids[q["question"]] = pid
        for part in q.get("parts", []):
            part_pid = reg.register(
                EntityKind.QUESTION,
                {
                    "system": provider,
                    "container_native_identity": paper_identity,
                    "native_id": part["question"],
                    "number_path": native_number_path(part["question"], part.get("parent")),
                    "parent_native_id": part.get("parent"),
                },
                native_locator={"provider": provider, "paper": ident["paper"],
                                "question": part["question"]},
            ).public_id
            q_pids[part["question"]] = part_pid

    questions = []
    for q in fx["questions"]:
        native_id = q["question"]
        children = []
        for part in q.get("parts", []):
            part_native = part["question"]
            child_quality = Quality()
            child_quality.apply("content", "partial", "synthetic_fixture")
            child_quality.apply("answer_presence", "unknown", "synthetic_fixture")
            child_quality.apply("answer_verification", "unknown", "synthetic_fixture")
            children.append(Question(
                public_id=q_pids[part_native], native_id=part_native,
                container_ref=container_pid,
                number_path=native_number_path(part_native, part.get("parent")),
                parent_ref=q_pids[native_id], group_ref=None,
                question_type=QuestionType.UNKNOWN, stem=part.get("text"), payload=None,
                marks=part.get("marks"), required_assets=[], answers=[],
                quality=child_quality, content_class=ContentClass.SYNTHETIC,
                lineage=synthetic_lineage(
                    "map_native_fixture", [f"synthetic/{provider}", "native-kind:part"],
                    note="sub-part type and answer are not declared by the source"),
                children=[],
            ))

        quality = Quality()
        quality.apply("content", "partial", "synthetic_fixture")
        quality.apply("answer_verification", "unverified", "synthetic_fixture")
        payload = None
        qtype = QuestionType.UNKNOWN
        answers = []
        required_assets = [
            RequiredAsset(role=img["role"], sha256=img.get("sha256"), asset_ref=None, required=True)
            for img in (q.get("required_images") or [])
        ]
        if required_assets:
            quality.apply("assets", "external_only", "synthetic_fixture")

        conflicts = [
            Conflict(value=c["value"], source=c["source"], evidence=None, decision=c.get("decision"))
            for c in (q.get("answer_conflicts") or [])
        ]
        manual_raw = q.get("manual_decision")
        manual = (ManualDecision(decided_by=manual_raw.get("decided_by"),
                                 decided_at=manual_raw.get("decided_at"),
                                 selected_value=manual_raw.get("selected_value"),
                                 rationale=manual_raw.get("rationale")) if manual_raw else None)

        if "table" in q:
            qtype = QuestionType.TABLE_CHOICE
            payload = _table_payload(q["table"])
            locator = q["table"]["answer_cells"][0] if q["table"].get("answer_cells") else None
            if locator is not None:
                quality.apply("answer_presence", "present", "synthetic_fixture",
                              context={"answer_value_present": True})
                answers.append(_answer(reg, provider, native_id, "primary",
                                       {"row": locator["row"], "column": locator["column"]},
                                       [], "exact", "unverified", conflicts, manual,
                                       ordering_rule="answer_locator_is_a_table_cell"))
        else:
            qtype = QuestionType.SHORT_ANSWER
            payload = _text_payload(q.get("text"))
            if q.get("answer") is not None:
                quality.apply("answer_presence", "present", "synthetic_fixture",
                              context={"answer_value_present": True})
                if conflicts:
                    quality.apply("answer_verification", "conflicting", "synthetic_fixture",
                                  context={"conflict_candidates_present": True})
                    answers.append(_answer(reg, provider, native_id, "primary", q["answer"],
                                           [], "alternative", "conflicting", conflicts, manual))
                else:
                    answers.append(_answer(reg, provider, native_id, "primary", q["answer"],
                                           [], "exact", "unverified", conflicts, manual))

        questions.append(Question(
            public_id=q_pids[native_id], native_id=native_id, container_ref=container_pid,
            number_path=native_number_path(native_id, q.get("parent")),
            parent_ref=None, group_ref=None, question_type=qtype, stem=q.get("text"),
            payload=payload, marks=q.get("marks"), required_assets=required_assets,
            answers=answers, quality=quality, content_class=ContentClass.SYNTHETIC,
            lineage=synthetic_lineage("map_native_fixture",
                                      [f"synthetic/{provider}",
                                       f"native-document-role:{q['lineage']['document_role']}"],
                                      note=f"native page {q['lineage']['page']}"),
            children=children,
        ))

    container.question_refs = [q.public_id for q in questions]
    coverage = completeness.evaluate_container(container, questions,
                                               expected_questions=len(fx["questions"]))
    cov_model = coverage.to_coverage(public_id="cov_synthetic_cie", computed_at=None,
                                     evidence=["synthetic_fixture"])

    return {"registry": reg, "containers": [container], "courses": [course],
            "questions": questions, "assets": assets, "timetable_events": events,
            "coverage": [cov_model]}


# --------------------------------------------------------------------------- #
# Edexcel
# --------------------------------------------------------------------------- #
def build_edexcel(fx: dict) -> dict:
    reg = IdentityRegistry()
    provider = "edexcel"
    courses, containers, events = [], [], []

    for subject in fx["subjects"]:
        course_pid = reg.register(
            EntityKind.COURSE,
            {"system": provider, "qualification": subject["qualification_level"],
             "native_code": subject["specification_code"],
             "specification_version": subject["specification_code"]},
            native_locator={"provider": provider, "subject": subject["native_id"]},
            aliases=subject["alias_ids"],
        ).public_id
        courses.append(Course(
            public_id=course_pid, system=ExamSystem.EDEXCEL,
            qualification=subject["qualification_level"],
            native_code=subject["specification_code"], names=[subject["title"]],
            aliases=list(subject["alias_ids"]),
            specification_version=subject["specification_code"],
            applicable_years=sorted({int(s["session"].split("-")[0])
                                     for u in subject["units"] for s in u["sessions"]}),
            source_refs=[synthetic_source(provider, f"subject:{subject['native_id']}")],
        ))

        for unit in subject["units"]:
            unit_identity = {"subject": subject["native_id"], "unit": unit["native_id"],
                             "paper": unit["paper_code"]}
            container_pid = reg.register(
                EntityKind.CONTAINER,
                {"system": provider, "kind": "paper", "native_identity": unit_identity},
                native_locator={"provider": provider, "kind": "paper", **unit_identity},
            ).public_id
            containers.append(Container(
                public_id=container_pid, kind=ContainerKind.PAPER,
                native_identity=dict(unit_identity), sections=[], resources=[],
                question_refs=[], revision=None, coverage="unknown",
                content_class=ContentClass.SYNTHETIC,
                lineage=synthetic_lineage("map_native_fixture",
                                          [f"synthetic/{provider}",
                                           f"native-subject:{subject['native_id']}"],
                                          note=f"native unit code {unit['unit_code']}"),
            ))
            for session in unit["sessions"]:
                pid = reg.register(
                    EntityKind.TIMETABLE_EVENT,
                    {"system": provider, "qualification": subject["qualification_level"],
                     "zone": None, "course_native_code": subject["specification_code"],
                     "component": unit["unit_code"], "date": None, "session": session["session"]},
                    native_locator={"provider": provider, "unit": unit["native_id"],
                                    "session": session["session"]},
                ).public_id
                events.append(TimetableEvent(
                    public_id=pid, system=ExamSystem.EDEXCEL,
                    qualification=subject["qualification_level"], zone=None,
                    course_ref=course_pid, component=unit["unit_code"], date=None,
                    session=session["session"], timezone=None, duration_minutes=None,
                    source=synthetic_source(
                        provider, f"date_unknown_reason:{session['date_unknown_reason']}"),
                    revision=None,
                ))

    return {"registry": reg, "containers": containers, "courses": courses,
            "questions": [], "assets": [], "timetable_events": events, "coverage": []}


# --------------------------------------------------------------------------- #
# supporting examples for the entity kinds the fixtures do not describe
# --------------------------------------------------------------------------- #
def build_supporting(reg_ielts: IdentityRegistry) -> dict:
    """One example each for the kinds no fixture describes; all synthetic."""
    system_pid = reg_ielts.register(
        EntityKind.EXAMINATION_SYSTEM, {"system": "ielts"},
        native_locator={"provider": "ielts", "native_id": "ielts"},
        aliases=["IELTS", "International English Language Testing System"],
    ).public_id
    system = ExaminationSystemModel(
        public_id=system_pid, system=ExamSystem.IELTS, names=["IELTS"],
        aliases=["International English Language Testing System"], qualifications=["academic"],
        capabilities=["reading", "listening", "writing", "speaking"], availability="unknown",
        links={},
    )

    syl_pid = reg_ielts.register(
        EntityKind.SYLLABUS,
        {"system": "ielts", "course_native_code": "synthetic-book-1", "version": "rev-synthetic-0001"},
        native_locator={"provider": "ielts", "native_id": "synthetic-book-1"},
    ).public_id
    syllabus = Syllabus(public_id=syl_pid, course_ref=None, title=None,
                        version="rev-synthetic-0001", applicability=None,
                        document_resources=[], content_class=ContentClass.SYNTHETIC)

    tag_pid = reg_ielts.register(
        EntityKind.TAG, {"scheme": "synthetic-scheme", "version": "1", "code": "SYN-1"},
        native_locator={"provider": "ielts", "native_id": "SYN-1"},
    ).public_id
    tag = Tag(public_id=tag_pid, scheme="synthetic-scheme", version="1", code="SYN-1",
              parent=None, label="Synthetic tag", specification_ref=None,
              assignment_method="synthetic_fixture", confidence=None, review="unreviewed")

    mat_pid = reg_ielts.register(
        EntityKind.MATERIAL,
        {"system": "ielts", "kind": "audio", "native_id": "synthetic-audio-1",
         "applicability": "unknown"},
        native_locator={"provider": "ielts", "native_id": "synthetic-audio-1"},
    ).public_id
    material = Material(public_id=mat_pid, kind="audio", applicability=None,
                        candidate_facing="unknown", access_mode="unknown", resources=[],
                        owner=None, content_class=ContentClass.SYNTHETIC)

    region_pid = reg_ielts.register(
        EntityKind.REGION,
        {"system": "ielts", "document_role": "question_paper",
         "document_sha256": "1111111111111111111111111111111111111111111111111111111111111111",
         "page": 1, "bbox": [0.0, 0.0, 100.0, 50.0],
         "coordinate_system": "unrotated_pdf_points_top_left"},
        native_locator={"provider": "ielts", "native_id": "synthetic-region-1"},
    ).public_id
    region = Region(public_id=region_pid, document_role="question_paper",
                    document_sha256="1111111111111111111111111111111111111111111111111111111111111111",
                    page=1, bbox=[0.0, 0.0, 100.0, 50.0],
                    coordinate_system="unrotated_pdf_points_top_left", rotation_transform=None,
                    evidence_status="unverified",
                    lineage=synthetic_lineage("map_native_fixture", ["synthetic/ielts"],
                                              note="synthetic crop region, no real document"))

    window_pid = reg_ielts.register(
        EntityKind.TIMETABLE_WINDOW,
        {"system": "cie", "qualification": None, "zone": None,
         "original_text": "Synthetic window text", "source": "synthetic-cie"},
        native_locator={"provider": "cie", "native_id": "synthetic-window-1"},
    ).public_id
    window = TimetableWindow(public_id=window_pid, original_text="Synthetic window text",
                             parsed_start=None, parsed_end=None, parsing_status="unparsed",
                             components=[], system=ExamSystem.CIE, qualification=None, zone=None,
                             source=synthetic_source("cie", "window"), revision=None)

    job_pid = reg_ielts.register(
        EntityKind.JOB_STATUS,
        {"scope": "synthetic-ielts-book-1",
         "input_revision": "rev-synthetic-0001"},
        native_locator={"provider": "ielts", "native_id": "synthetic-job-1"},
    ).public_id
    job = JobStatus(public_id=job_pid, scope="synthetic-ielts-book-1",
                    input_revision="rev-synthetic-0001", stage="staged", counters={},
                    stop_reason=None, resume_required=False, output_refs=[], evidence_refs=[])

    return {"examination_systems": [system], "syllabi": [syllabus], "tags": [tag],
            "materials": [material], "regions": [region], "timetable_windows": [window],
            "jobs": [job]}


# --------------------------------------------------------------------------- #
def roundtrip(label: str, instance, bucket: list) -> None:
    """Assert from_dict(to_dict(x)) == x and record validate() problems."""
    payload = instance.to_dict()
    try:
        restored = type(instance).from_dict(payload)
    except Exception as exc:  # noqa: BLE001
        check(f"roundtrip.{label}", False, f"from_dict raised {exc!r}")
        return
    check(f"roundtrip.{label}", restored == instance,
          "from_dict(to_dict(x)) != x" if restored != instance else "")
    problems = instance.validate()
    bucket.append({"label": label, "schema": instance.SCHEMA, "problems": problems})


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default=str(EXAMPLES))
    args = ap.parse_args()
    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = (WS / out_dir).resolve()

    lines: list[str] = []

    def emit(s: str = "") -> None:
        lines.append(s)

    emit("=== A04 contract round-trip over the A03 synthetic fixtures ===")
    emit(f"generated_at_local: {datetime.now().astimezone().isoformat(timespec='seconds')}")
    emit(f"fixtures: {FIXTURES.relative_to(WS).as_posix()}")
    emit()

    validate_problems: list[dict] = []

    ielts = build_ielts(load(FIXTURES / "ielts" / "questions-synthetic.json"))
    cie = build_cie(load(FIXTURES / "cie" / "cie-index-synthetic.json"))
    edexcel = build_edexcel(load(FIXTURES / "edexcel" / "index-synthetic.json"))
    supporting = build_supporting(ielts["registry"])

    emit("--- identity registry sizes ---")
    for name, bundle in (("ielts", ielts), ("cie", cie), ("edexcel", edexcel)):
        emit(f"{name}: records={len(bundle['registry'].records())} "
             f"collisions={len(bundle['registry'].collision_events)} "
             f"alias_events={len(bundle['registry'].alias_events)}")
        check(f"registry.{name}.no_collisions", not bundle["registry"].collision_events)
        check(f"registry.{name}.no_alias_conflicts", not bundle["registry"].alias_events)
    emit()

    emit("--- round-trip and validate ---")
    for name, bundle in (("ielts", ielts), ("cie", cie), ("edexcel", edexcel)):
        for key in ("containers", "courses", "questions", "assets", "timetable_events",
                    "coverage"):
            for instance in bundle.get(key, []):
                label = f"{name}.{key}.{instance.public_id}"
                roundtrip(label, instance, validate_problems)
                for child in getattr(instance, "children", []):
                    roundtrip(f"{label}.child.{child.public_id}", child, validate_problems)
                for answer in getattr(instance, "answers", []):
                    roundtrip(f"{label}.answer.{answer.public_id}", answer, validate_problems)
        for kind, items in supporting.items():
            if name != "ielts":
                continue
            for instance in items:
                roundtrip(f"supporting.{kind}.{instance.public_id}", instance, validate_problems)

    for row in validate_problems:
        emit(f"validate {row['label']} [{row['schema']}]: "
             f"{row['problems'] if row['problems'] else 'no problems'}")
    emit()

    # ---- preservation assertions ------------------------------------------------
    emit("--- preservation assertions ---")
    reg = ielts["registry"]
    book_pid = [r.public_id for r in reg.records()
                if r.kind is EntityKind.CONTAINER][0]
    check("ielts.alias_resolves_book",
          reg.resolve_alias("SB1") == book_pid and reg.resolve_alias("synthetic/cambridge-1") == book_pid)
    check("ielts.alias_case_insensitive", reg.resolve_alias("sb1") == book_pid)

    ielts_q = {q.native_id: q for q in ielts["questions"]}
    check("ielts.q41_slot_preserved",
          ielts_q["Q41"].answers == []
          and ielts_q["Q41"].quality.answer_presence is QualityAnswerPresence.MISSING
          and any(g.code == GapCode.MISSING_ANSWER_SLOT.value for g in ielts_q["Q41"].quality.gaps))
    check("ielts.q2_grouped_alternatives_preserved",
          ielts_q["Q2"].answers[0].alternatives == ["A", "C", "D"]
          and ielts_q["Q2"].answers[0].matching_method.value == "alternative")
    check("ielts.q3_parent_and_children_preserved",
          len(ielts_q["Q3"].children) == 2
          and ielts_q["Q3"].answers[0].matching_method.value == "ancestor"
          and all(c.parent_ref == ielts_q["Q3"].public_id for c in ielts_q["Q3"].children)
          and all(c.number_path == ["Q3", c.native_id] for c in ielts_q["Q3"].children))
    table = ielts_q["Q4"].payload
    check("ielts.q4_table_structure_preserved",
          table.SCHEMA == "payload/table/1" and len(table.columns) == 3 and len(table.rows) == 2
          and [(c.row, c.column) for c in table.answer_cells] == [(2, 3)])
    q5 = ielts_q["Q5"]
    check("ielts.q5_conflict_and_manual_decision_preserved",
          len(q5.answers[0].conflicts) == 2 and q5.answers[0].manual_decision is None
          and q5.answers[0].verification == "conflicting"
          and q5.quality.answer_verification is QualityAnswerVerification.CONFLICTING)
    check("ielts.q5_required_image_preserved",
          len(q5.required_assets) == 1 and q5.required_assets[0].role == "diagram"
          and q5.required_assets[0].sha256 == "0" * 64
          and q5.quality.assets is QualityAssets.EXTERNAL_ONLY)
    check("ielts.lineage_preserved",
          all(q.lineage is not None and q.lineage.operation == "map_native_fixture"
              for q in ielts["questions"]))
    check("ielts.native_locator_roundtrip",
          reg.native_locator(ielts_q["Q41"].public_id)["native_id"] == "Q41")

    cie_q = {q.native_id: q for q in cie["questions"]}
    check("cie.hierarchy_preserved",
          len(cie_q["1"].children) == 2
          and [c.native_id for c in cie_q["1"].children] == ["1(a)", "1(b)"]
          and all(c.parent_ref == cie_q["1"].public_id for c in cie_q["1"].children))
    cie_table = cie_q["2"].payload
    check("cie.table_structure_preserved",
          cie_table.SCHEMA == "payload/table/1"
          and [(c.row, c.column) for c in cie_table.answer_cells] == [(2, 2)])
    check("cie.unknown_date_preserved",
          cie["timetable_events"][0].date is None
          and "date unknown" in " ".join(cie["timetable_events"][0].validate()))
    check("cie.conflict_preserved",
          len(cie_q["3"].answers[0].conflicts) == 2
          and cie_q["3"].quality.answer_verification is QualityAnswerVerification.CONFLICTING)
    check("cie.synthetic_never_verified",
          all(a.verification != "source_verified"
              for q in cie["questions"] for a in q.answers))

    check("edexcel.sessions_unknown_dates",
          len(edexcel["timetable_events"]) == 2
          and all(e.date is None for e in edexcel["timetable_events"]))
    check("edexcel.alias_resolves_subject",
          edexcel["registry"].resolve_alias("WMA") == edexcel["courses"][0].public_id)
    check("supporting.region_has_document_hash",
          supporting["regions"][0].document_sha256 == "1" * 64)

    # ---- write examples -----------------------------------------------------------
    emit()
    emit("--- examples written ---")
    written: dict[str, str] = {}
    for name, bundle in (("ielts", ielts), ("cie", cie), ("edexcel", edexcel)):
        registry_name = f"identity-registry__{name}.json"
        examples[registry_name] = bundle["registry"].to_dict()
        example_schema[registry_name] = "identity-registry/1"
    for name, bundle in (("ielts", ielts), ("cie", cie), ("edexcel", edexcel)):
        for key in ("containers", "courses", "questions", "assets", "timetable_events",
                    "coverage"):
            for instance in bundle.get(key, []):
                add_example(f"{key}__{name}__{instance.public_id}", instance)
                for child in getattr(instance, "children", []):
                    add_example(f"questions__{name}__{child.public_id}", child)
                for answer in getattr(instance, "answers", []):
                    add_example(f"answers__{name}__{answer.public_id}", answer)
    for kind, items in supporting.items():
        for instance in items:
            add_example(f"{kind}__synthetic__{instance.public_id}", instance)

    index = []
    for fname, payload in sorted(examples.items()):
        path = out_dir / fname
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8", newline="\n")
        written[fname] = example_schema[fname]
        index.append({"file": fname, "schema": example_schema[fname]})
    (out_dir / "INDEX.json").write_text(
        json.dumps({"schema": "examples-index/1", "examples": index},
                   ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    emit(f"examples: {len(examples)} + INDEX.json -> {out_dir.relative_to(WS).as_posix()}")
    schemas = sorted({v for v in written.values()})
    emit(f"schemas covered ({len(schemas)}): {schemas}")
    required_schemas = {
        "container/1", "course/1", "question/1", "answer/1", "asset/1", "coverage/1",
        "region/1", "timetable-event/1", "timetable-window/1", "syllabus/1", "tag/1",
        "material/1", "examination-system/1", "job-status/1",
    }
    check("examples.every_entity_kind_covered", required_schemas <= set(schemas),
          f"missing={sorted(required_schemas - set(schemas))}")

    # ---- verdict -------------------------------------------------------------------
    emit()
    emit("--- verdict ---")
    failed = [(n, d) for n, ok, d in checks if not ok]
    for n, ok, d in checks:
        emit(f"{n}: {'PASS' if ok else 'FAIL'}{(' (' + d + ')') if d and not ok else ''}")
    ok_all = not failed
    emit(f"A04_ROUNDTRIP_JSON: {'PASS' if ok_all else 'FAIL'}")
    emit(f"ROUNDTRIP: {'PASS' if ok_all else 'FAIL'}")

    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / "roundtrip_stdout.txt").write_text("\n".join(lines) + "\n",
                                                   encoding="utf-8", newline="\n")
    sys.stdout.write("\n".join(lines) + "\n")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
