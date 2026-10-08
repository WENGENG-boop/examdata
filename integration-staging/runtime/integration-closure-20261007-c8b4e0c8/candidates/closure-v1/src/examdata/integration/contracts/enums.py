"""Controlled vocabularies for the staged integration contracts (plan section 4).

Every enum here is part of the frozen A04 contract: values are lower-case,
ASCII, and stable. Unknown or not-yet-classified content must use the explicit
`unknown` member where one exists - never a plausible-looking default, and never
a value inferred from similarity.

Stdlib only. Nothing in this module touches the original project.
"""
from __future__ import annotations

from enum import Enum


class _StrEnum(str, Enum):
    """str-backed enum so values serialise as plain strings."""

    def __str__(self) -> str:  # pragma: no cover - convenience only
        return self.value

    @classmethod
    def coerce(cls, value):
        """Return the member for `value`; raise ValueError for anything else."""
        if isinstance(value, cls):
            return value
        try:
            return cls(value)
        except ValueError as exc:
            raise ValueError(
                f"{cls.__name__}: {value!r} is not an allowed value "
                f"({sorted(m.value for m in cls)})"
            ) from exc


class ExamSystem(_StrEnum):
    CIE = "cie"
    EDEXCEL = "edexcel"
    IELTS = "ielts"
    TOEFL = "toefl"
    GAOKAO = "gaokao"


class ContainerKind(_StrEnum):
    PAPER = "paper"
    TEST = "test"
    SET = "set"
    BOOK = "book"


class QuestionType(_StrEnum):
    SINGLE_CHOICE = "single_choice"
    MULTIPLE_CHOICE = "multiple_choice"
    TABLE_CHOICE = "table_choice"
    MATCHING = "matching"
    FILL_BLANK = "fill_blank"
    SHORT_ANSWER = "short_answer"
    ESSAY = "essay"
    SPEAKING = "speaking"
    DIAGRAM_LABELS = "diagram_labels"
    UNKNOWN = "unknown"


class AnswerMatchingMethod(_StrEnum):
    """How a returned answer relates to the asked question (plan 4.5)."""

    EXACT = "exact"
    NORMALIZED = "normalized"
    ALTERNATIVE = "alternative"
    IN_ANY_ORDER = "in_any_order"
    GROUPED = "grouped"
    ANCESTOR = "ancestor"
    DESCENDANTS = "descendants"
    MANUAL = "manual"
    UNRESOLVED = "unresolved"


class ContentClass(_StrEnum):
    """Provenance class of a piece of content (plan 4.5)."""

    OFFICIAL = "official"
    MANUAL = "manual"
    GENERATED = "generated"
    DERIVED = "derived"
    SYNTHETIC = "synthetic"
    UNKNOWN = "unknown"


class QualityContent(_StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    MISSING = "missing"
    UNKNOWN = "unknown"


class QualityAnswerPresence(_StrEnum):
    PRESENT = "present"
    MISSING = "missing"
    UNKNOWN = "unknown"


class QualityAnswerVerification(_StrEnum):
    SOURCE_VERIFIED = "source_verified"
    MANUAL_ADJUDICATED = "manual_adjudicated"
    CONFLICTING = "conflicting"
    UNVERIFIED = "unverified"
    UNKNOWN = "unknown"


class QualityAssets(_StrEnum):
    EMBEDDED = "embedded"
    EXTERNAL_ONLY = "external_only"
    MISSING = "missing"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


class QualityAudioIntegrity(_StrEnum):
    HASH_VERIFIED = "hash_verified"
    HASH_MISMATCH = "hash_mismatch"
    UNVERIFIED = "unverified"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


class QualityAudioAlignment(_StrEnum):
    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


class QualityRegionVerification(_StrEnum):
    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


class GapScope(_StrEnum):
    SYSTEM = "system"
    COURSE = "course"
    CONTAINER = "container"
    QUESTION = "question"
    ANSWER = "answer"
    ASSET = "asset"
    REGION = "region"
    COVERAGE = "coverage"


class GapCode(_StrEnum):
    MISSING_OPTIONS = "missing_options"
    MISSING_TABLE = "missing_table"
    MISSING_ANSWER = "missing_answer"
    MISSING_ANSWER_SLOT = "missing_answer_slot"
    MISSING_REQUIRED_IMAGE = "missing_required_image"
    MISSING_DOCUMENT_HASH = "missing_document_hash"
    MISSING_REGION = "missing_region"
    UNKNOWN_DATE = "unknown_date"
    UNKNOWN_COVERAGE = "unknown_coverage"
    UNRESOLVED_IDENTITY = "unresolved_identity"
    UNRESOLVED_EDITION = "unresolved_edition"
    ANSWER_CONFLICT = "answer_conflict"
    UNVERIFIED_CONTENT = "unverified_content"
    DEFERRED_SOURCE = "deferred_source"


class EvidenceLabel(_StrEnum):
    """The only evidence labels allowed in Phase A reports (plan 15.6)."""

    STATIC_INSPECTION = "static_inspection"
    SYNTHETIC_FIXTURE = "synthetic_fixture"
    COPIED_SNAPSHOT = "copied_snapshot"
    ISOLATED_REAL_DATA = "isolated_real_data"
    LIVE_LOCAL_SERVICE = "live_local_service"
    LIVE_UPSTREAM_SAMPLE = "live_upstream_sample"
    FULL_SOURCE_VALIDATION = "full_source_validation"
    DEPLOYED_TARGET_VALIDATION = "deployed_target_validation"


class EntityKind(_StrEnum):
    """Entity kinds and their public-ID type prefixes (plan 4.2)."""

    EXAMINATION_SYSTEM = "examination_system"
    COURSE = "course"
    SYLLABUS = "syllabus"
    CONTAINER = "container"
    QUESTION = "question"
    ANSWER = "answer"
    REGION = "region"
    ASSET = "asset"
    TAG = "tag"
    MATERIAL = "material"
    TIMETABLE_EVENT = "timetable_event"
    TIMETABLE_WINDOW = "timetable_window"
    COVERAGE = "coverage"
    JOB_STATUS = "job_status"


ID_TYPE_PREFIX: dict[EntityKind, str] = {
    EntityKind.EXAMINATION_SYSTEM: "es",
    EntityKind.COURSE: "course",
    EntityKind.SYLLABUS: "syl",
    EntityKind.CONTAINER: "container",
    EntityKind.QUESTION: "q",
    EntityKind.ANSWER: "ans",
    EntityKind.REGION: "region",
    EntityKind.ASSET: "asset",
    EntityKind.TAG: "tag",
    EntityKind.MATERIAL: "mat",
    EntityKind.TIMETABLE_EVENT: "tte",
    EntityKind.TIMETABLE_WINDOW: "ttw",
    EntityKind.COVERAGE: "cov",
    EntityKind.JOB_STATUS: "job",
}

__all__ = [
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
]
