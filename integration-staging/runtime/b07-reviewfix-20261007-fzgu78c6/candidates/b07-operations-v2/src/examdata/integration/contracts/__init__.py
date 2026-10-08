"""Staged integration contracts (plan section 4): models, identity, quality.

Public surface:

* `enums`         - controlled vocabularies (exam systems, question types, ...);
* `canonical`     - canonicalisation and deterministic public IDs;
* `ids`           - the identity registry (aliases, collisions, native round-trip);
* `models`        - the Section 4.4 entity models and Section 4.5 payloads;
* `quality`       - independent quality dimensions and the transition table;
* `completeness`  - type-specific completeness rules.

Nothing in this package reads the original project, the network, or the live
database; it is pure data handling and is exercised by the staged tests.
"""
from . import canonical, completeness, enums, ids, jsonschema_lite, models, quality
from .base import ContractError, ContractModel, Gap
from .canonical import UNKNOWN, content_revision, digest_for, public_id
from .enums import (
    AnswerMatchingMethod,
    ContainerKind,
    ContentClass,
    EntityKind,
    EvidenceLabel,
    ExamSystem,
    GapCode,
    GapScope,
    ID_TYPE_PREFIX,
    QualityAnswerPresence,
    QualityAnswerVerification,
    QualityAssets,
    QualityAudioAlignment,
    QualityAudioIntegrity,
    QualityContent,
    QualityRegionVerification,
    QuestionType,
)
from .ids import AliasConflictError, IdentityCollisionError, IdentityRecord, IdentityRegistry
from .models import (
    Answer,
    Asset,
    Conflict,
    Container,
    Course,
    Coverage,
    ExaminationSystemModel,
    Gap,
    JobStatus,
    Lineage,
    ManualDecision,
    Material,
    Quality,
    Question,
    Region,
    RequiredAsset,
    SourceRef,
    Syllabus,
    Tag,
    TimetableEvent,
    TimetableWindow,
)

__all__ = [
    "canonical",
    "completeness",
    "enums",
    "ids",
    "jsonschema_lite",
    "models",
    "quality",
    "ContractError",
    "ContractModel",
    "Gap",
    "UNKNOWN",
    "content_revision",
    "digest_for",
    "public_id",
    "IdentityRegistry",
    "IdentityRecord",
    "IdentityCollisionError",
    "AliasConflictError",
    "ExamSystem",
    "ContainerKind",
    "QuestionType",
    "AnswerMatchingMethod",
    "ContentClass",
    "QualityContent",
    "QualityAnswerPresence",
    "QualityAnswerVerification",
    "QualityAssets",
    "QualityAudioIntegrity",
    "QualityAudioAlignment",
    "QualityRegionVerification",
    "GapScope",
    "GapCode",
    "EvidenceLabel",
    "EntityKind",
    "ID_TYPE_PREFIX",
    "Lineage",
    "SourceRef",
    "Conflict",
    "ManualDecision",
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
]
